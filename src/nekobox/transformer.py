import base64
from io import BytesIO
from urllib.parse import quote, unquote
from typing import List, TYPE_CHECKING, Union, Tuple

from lagrange.client.message.elems import Text, Image, At, Audio, Quote
from lagrange.client.message.types import T
from lagrange.utils.httpcat import HttpCat

from loguru import logger
from satori import (
    Element as SatoriElement,
    At as SatoriAt,
    Text as SatoriText,
    Quote as SatoriQuote,
    Image as SatoriImage,
    Audio as SatoriAudio,
)

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
    if url.startswith("http"):
        rsp = await HttpCat.request("GET", url)
        return rsp.decompressed_body
    elif url.startswith("data"):
        _, data = decode_data_url(url)
        return data
    else:
        raise ValueError("Unsupported URL: %s" % url)


async def msg_to_satori(msgs: List[T]) -> List[SatoriElement]:
    new_msg: List[SatoriElement] = []
    for m in msgs:
        if isinstance(m, At):
            new_msg.append(SatoriAt(str(m.uin), m.text))
        elif isinstance(m, Quote):
            new_msg.append(SatoriQuote(str(m.seq), False))
        elif isinstance(m, Image):
            new_msg.append(SatoriImage(str(m.url), width=m.width, height=m.height))
        elif isinstance(m, Audio):
            new_msg.append(SatoriAudio(m.name))
        elif isinstance(m, Text):
            new_msg.append(SatoriText(m.text))
        else:
            logger.warning("cannot parse message to satori", repr(m)[:100])
    return new_msg


async def satori_to_msg(client: "Client", msgs: List[SatoriElement], *, grp_id=0, uid="") -> List[T]:
    new_msg: List[T] = []
    for m in msgs:
        if isinstance(m, SatoriAt):
            new_msg.append(At(f"@{m.name}", int(m.id), ""))
        elif isinstance(m, SatoriQuote):
            target = await client.get_grp_msg(grp_id, int(m.id))
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
        else:
            logger.warning("cannot trans message to lag" + repr(m)[:100])
    return new_msg
