import base64
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, unquote
from typing import List, TYPE_CHECKING, Union, Tuple

from lagrange.client.message.elems import Text, Image, At, Audio, Quote, MarketFace
from lagrange.client.message.types import Element

from loguru import logger
from satori.element import (
    Style as SatoriStyle,
    Br as SatoriBr,
    Paragraph as SatoriParagraph,
)
from satori import (
    Element as SatoriElement,
    At as SatoriAt,
    Text as SatoriText,
    Quote as SatoriQuote,
    Image as SatoriImage,
    Audio as SatoriAudio,
    Message as SatoriMessage,
    Link as SatoriLink,
)
from .utils import download_resource, transform_audio

if TYPE_CHECKING:
    from lagrange.client.client import Client


def encode_data_url(data: Union[str, bytes], mime_type=""):
    if isinstance(data, str):
        encoded = quote(data)
    elif isinstance(data, bytes):
        encoded = base64.b64encode(data)
        mime_type += ";base64"
    else:
        raise TypeError(f"Type {type(data)} not supported")
    return f"data:{mime_type},{encoded}"


def decode_data_url(url: str) -> Tuple[str, bytes]:
    if url.find("data:") != 0:
        raise ValueError("Not a valid Data URL")
    head, data = url[5:].split(",", 1)
    if head.find(";") != -1:
        mime, enc_type = head.split(";", 1)
        if enc_type == "base64":
            decoded = base64.b64decode(data)
        else:
            raise TypeError(f"Type {enc_type} not supported")
    else:
        mime = head
        decoded = unquote(data).encode()
    return mime, decoded


async def parse_resource(url: str) -> bytes:
    logger.debug(f"loading resource: {url[:80]}")
    if url.find("http") == 0:
        return await download_resource(url)
    elif url.find("data") == 0:
        _, data = decode_data_url(url)
        return data
    elif url.find("file://") == 0:
        if sys.platform == "win32":
            path = Path(url[8:])
        else:
            path = Path(url[7:])
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path.absolute()}")
        with open(path, "rb") as f:
            return f.read()
    else:
        raise ValueError("Unsupported URL: %s" % url)


async def msg_to_satori(msgs: List[Element]) -> List[SatoriElement]:
    new_msg: List[SatoriElement] = []
    for m in msgs:
        if isinstance(m, At):
            new_msg.append(SatoriAt(str(m.uin), m.text))
        elif isinstance(m, Quote):
            new_msg.append(SatoriQuote(str(m.seq), False))
        elif isinstance(m, (Image, MarketFace)):
            new_msg.append(SatoriImage(str(m.url), width=m.width, height=m.height))
        elif isinstance(m, Audio):
            new_msg.append(SatoriAudio(m.name))
        elif isinstance(m, Text):
            new_msg.append(SatoriText(m.text))
        else:
            logger.warning("cannot parse message to satori " + repr(m)[:100])
    return new_msg


async def satori_to_msg(client: "Client", msgs: List[SatoriElement], *, grp_id=0, uid="") -> List[Element]:
    new_msg: List[Element] = []
    for m in msgs:
        if isinstance(m, SatoriAt):
            new_msg.append(At(f"@{m.name}", int(m.id or 0), ""))
        elif isinstance(m, SatoriQuote):
            target = await client.get_grp_msg(grp_id, int(m.id or 0))
            new_msg.append(Quote.build(target[0]))
        elif isinstance(m, SatoriImage):
            data = await parse_resource(m.src)
            if grp_id:
                new_msg.append(
                    await client.upload_grp_image(BytesIO(data), grp_id)
                )
            elif uid:
                new_msg.append(
                    await client.upload_friend_image(BytesIO(data), uid)
                )
            else:
                raise AssertionError
        elif isinstance(m, SatoriText):
            new_msg.append(Text(m.text))
        elif isinstance(m, SatoriLink):
            parsed = await satori_to_msg(client, m._children, grp_id=grp_id, uid=uid)
            new_msg.extend(parsed)
            new_msg.append(Text(f"{': ' if parsed else ''}{m.url}"))
        elif isinstance(m, (SatoriMessage, SatoriStyle)):
            if isinstance(m, SatoriBr):
                new_msg.append(Text("\n"))
            else:
                new_msg.extend(
                    await satori_to_msg(client, m._children, grp_id=grp_id, uid=uid)
                )
                if isinstance(m, SatoriParagraph):
                    new_msg.append(Text("\n"))
        elif isinstance(m, SatoriAudio):
            data = await transform_audio(
                BytesIO(await parse_resource(m.src))
            )
            if grp_id:
                new_msg.append(
                    await client.upload_grp_audio(data, grp_id)
                )
            elif uid:
                new_msg.append(
                    await client.upload_friend_audio(data, uid)
                )
            else:
                raise AssertionError
        else:
            logger.warning("cannot trans message to lag " + repr(m)[:100])
    return new_msg
