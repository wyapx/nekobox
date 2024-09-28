import sys
import base64
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, unquote
from typing import TYPE_CHECKING, List, Tuple, Union

from yarl import URL
from loguru import logger
from satori import At as SatoriAt
from satori import Link as SatoriLink
from satori import Text as SatoriText
from satori import Audio as SatoriAudio
from satori import Image as SatoriImage
from satori import Quote as SatoriQuote
from satori import Author as SatoriAuthor
from satori.element import Br as SatoriBr
from satori import Element as SatoriElement
from satori import Message as SatoriMessage
from satori.element import Style as SatoriStyle
from lagrange.client.message.types import Element
from satori.element import Custom as SatoriCustom
from satori.element import Paragraph as SatoriParagraph
from lagrange.client.message.elems import At, Text, AtAll, Audio, Image, Quote, MarketFace

from .consts import PLATFORM
from .utils import cx_server, get_public_ip, transform_audio, download_resource

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


async def msg_to_satori(msgs: List[Element], self_uin: int, gid=None, uid=None) -> List[SatoriElement]:
    new_msg: List[SatoriElement] = []
    for m in msgs:
        if isinstance(m, At):
            new_msg.append(SatoriAt(str(m.uin), m.text))
        elif isinstance(m, AtAll):
            new_msg.append(SatoriAt.all())
        elif isinstance(m, Quote):
            new_msg.append(SatoriQuote(str(m.seq))(SatoriAuthor(str(m.uin)), m.msg))
        elif isinstance(m, (Image, MarketFace)):
            url = URL(m.url.replace("&amp;", "&"))
            if "rkey" in url.query:
                url = url.with_query({k: v for k, v in url.query.items() if k != "rkey"})
                if server := cx_server.get(None):
                    url = URL(server.url_base) / "proxy" / str(url)
                    if url.host == "0.0.0.0":
                        url = url.with_host(get_public_ip())
            new_msg.append(SatoriImage.of(str(url), extra={"width": m.width, "height": m.height}))
        elif isinstance(m, Audio):
            assert gid or uid, "gid or uid must be specified"
            new_msg.append(
                SatoriAudio(
                    f"upload://{PLATFORM}/{self_uin}"
                    f"/audio/{'gid' if gid else 'uid'}/{gid or uid}/{m.file_key}",
                    title=m.text,
                    duration=m.time
                )
            )
        elif isinstance(m, Text):
            new_msg.append(SatoriText(m.text))
        else:
            logger.warning("cannot parse message to satori " + repr(m)[:100])
    return new_msg


async def satori_to_msg(client: "Client", msgs: List[SatoriElement], *, grp_id=0, uid="") -> List[Element]:
    new_msg: List[Element] = []
    for m in msgs:
        if isinstance(m, SatoriAt):
            if m.type:
                new_msg.append(AtAll("@全体成员"))
            elif m.id:
                new_msg.append(At(f"@{m.name or m.id}", int(m.id), ""))
        elif isinstance(m, SatoriQuote):
            target = await client.get_grp_msg(grp_id, int(m.id or 0))
            new_msg.append(Quote.build(target[0]))
        elif isinstance(m, SatoriImage):
            data = await parse_resource(m.src)
            if grp_id:
                new_msg.append(await client.upload_grp_image(BytesIO(data), grp_id))
            elif uid:
                new_msg.append(await client.upload_friend_image(BytesIO(data), uid))
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
                new_msg.extend(await satori_to_msg(client, m._children, grp_id=grp_id, uid=uid))
                if isinstance(m, SatoriParagraph):
                    new_msg.append(Text("\n"))
        elif isinstance(m, SatoriAudio):
            data = await transform_audio(BytesIO(await parse_resource(m.src)))
            if grp_id:
                new_msg.append(await client.upload_grp_audio(data, grp_id))
            elif uid:
                new_msg.append(await client.upload_friend_audio(data, uid))
            else:
                raise AssertionError
        elif isinstance(m, SatoriCustom):
            if m.type == "template":
                new_msg.extend(await satori_to_msg(client, m._children, grp_id=grp_id, uid=uid))
            else:
                logger.warning("unknown message type on Custom: %s", m.type)
        else:
            logger.warning("cannot trans message to lag " + repr(m)[:100])
    return new_msg
