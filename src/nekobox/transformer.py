import os
import sys
import json
import time
import base64
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, unquote, unquote_to_bytes
from typing import TYPE_CHECKING, List, Tuple, Union, Optional

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
from starlette.responses import FileResponse
from satori.element import Style as SatoriStyle
from lagrange.client.message.types import Element
from satori.element import Custom as SatoriCustom
from satori.element import Paragraph as SatoriParagraph
from lagrange.client.message.elems import (
    At,
    Json,
    Text,
    AtAll,
    Audio,
    Image,
    Quote,
    MulitMsg,
    MarketFace,
    ForwardNode,
)

from .consts import PLATFORM, get_server
from .utils import get_public_ip, transform_audio, download_resource

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
    if url.startswith("internal:"):
        server = get_server()
        if not server:
            raise ValueError("No server found")
        resp = await server.fetch_proxy(url)
        if isinstance(resp, FileResponse):
            with open(resp.path, "rb") as f:
                return f.read()
        return bytes(resp.body)
    if url.find("http") == 0:
        return await download_resource(url)
    elif url.find("data") == 0:
        _, data = decode_data_url(url)
        return data
    elif url.find("file://") == 0:
        if sys.version_info >= (3, 13):
            path = Path.from_uri(url)
        else:
            decoded = os.fsdecode(unquote_to_bytes(url[8:] if sys.platform == "win32" else url[7:]))
            path = Path(decoded)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path.absolute()}")
        with open(path, "rb") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported URL: {url}")


async def msg_to_satori(
    msgs: List[Element],
    self_uin: int,
    gid=None,
    uid=None,
    client: "Client | None" = None,
) -> List[SatoriElement]:
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
                if server := get_server():
                    url = URL(server.url_base) / "proxy" / str(url)
                    if url.host == "0.0.0.0":
                        url = url.with_host(get_public_ip())
            new_msg.append(SatoriImage.of(str(url), extra={"width": m.width, "height": m.height}))
        elif isinstance(m, Audio):
            assert gid or uid, "gid or uid must be specified"
            new_msg.append(
                SatoriAudio(
                    f"internal:{PLATFORM}/{self_uin}"
                    f"/audio/{'gid' if gid else 'uid'}/{gid or uid}/{m.file_key}",
                    title=m.text,
                    duration=m.time,
                )
            )
        elif isinstance(m, Text):
            new_msg.append(SatoriText(m.text))
        elif isinstance(m, MulitMsg):
            new_msg.append(await _forward_to_satori(m, self_uin, gid=gid, uid=uid, client=client))
        elif isinstance(m, Json):
            try:
                payload = m.to_dict()
            except (UnicodeDecodeError, json.JSONDecodeError):
                logger.warning("cannot parse json message to satori " + repr(m)[:100])
                continue
            if forward_msg := _multimsg_from_json_payload(payload):
                new_msg.append(
                    await _forward_to_satori(
                        forward_msg,
                        self_uin,
                        gid=gid,
                        uid=uid,
                        client=client,
                    )
                )
            else:
                logger.warning("cannot parse json message to satori " + repr(m)[:100])
        else:
            logger.warning("cannot parse message to satori " + repr(m)[:100])
    return new_msg


def _multimsg_from_json_payload(payload: object) -> Optional[MulitMsg]:
    if not isinstance(payload, dict) or payload.get("app") != "com.tencent.multimsg":
        return None

    meta = payload.get("meta", {})
    detail = meta.get("detail", {}) if isinstance(meta, dict) else {}
    if not isinstance(detail, dict):
        return None

    resid = detail.get("resid")
    if not resid:
        logger.warning("forward json message has no resid")
        return None

    file_name = str(detail.get("uniseq") or "")
    extra = payload.get("extra")
    if isinstance(extra, str) and extra.strip():
        try:
            extra_payload = json.loads(extra)
        except json.JSONDecodeError:
            extra_payload = {}
        if isinstance(extra_payload, dict) and extra_payload.get("filename"):
            file_name = str(extra_payload["filename"])

    return MulitMsg(resid=str(resid), file_name=file_name)


async def _forward_to_satori(
    forward_msg: MulitMsg,
    self_uin: int,
    *,
    gid=None,
    uid=None,
    client: "Client | None" = None,
) -> SatoriMessage:
    if not forward_msg.messages and forward_msg.resid and client:
        try:
            forward_msg = await client.get_forward_msg(forward_msg.resid, is_group=gid is not None)
        except Exception:
            logger.exception("cannot fetch forward message %s", forward_msg.resid)

    nodes = []
    for node in forward_msg.messages:
        author = SatoriAuthor(
            str(node.sender_uin),
            node.sender_nick or None,
            node.sender_avatar_url or None,
        )
        message = SatoriMessage(
            content=[
                author,
                *await msg_to_satori(node.content, self_uin, gid=gid, uid=uid, client=client),
            ]
        )
        message._attrs["timestamp"] = node.timestamp
        nodes.append(message)

    forward = SatoriMessage(id=forward_msg.resid, forward=True, content=nodes)
    if forward_msg.file_name:
        forward._attrs["file_name"] = forward_msg.file_name
    return forward


def _author_name(author: SatoriAuthor) -> str:
    if author.name:
        return author.name
    if author._children:
        return "".join(
            child.text if isinstance(child, SatoriText) else str(child) for child in author._children
        )
    return author.id


def _node_timestamp(message: SatoriMessage) -> int:
    timestamp = message._attrs.get("timestamp")
    if timestamp is None:
        return int(time.time())
    try:
        return int(timestamp)
    except (TypeError, ValueError):
        logger.warning("invalid forward node timestamp: %r", timestamp)
        return 0


async def _message_to_forward_node(
    client: "Client", message: SatoriMessage, *, grp_id=0, uid=""
) -> ForwardNode:
    author = next((child for child in message._children if isinstance(child, SatoriAuthor)), None)
    if author:
        try:
            sender_uin = int(author.id)
        except (TypeError, ValueError):
            logger.warning("invalid forward author id: %r", author.id)
            sender_uin = client.uin
        sender_nick = _author_name(author)
        content = [child for child in message._children if child is not author]
    else:
        sender_uin = client.uin
        sender_nick = str(client.uin)
        content = list(message._children)

    return ForwardNode(
        content=await satori_to_msg(client, content, grp_id=grp_id, uid=uid),
        sender_uin=sender_uin,
        sender_nick=sender_nick,
        sender_avatar_url=author.avatar if author and author.avatar else "",
        timestamp=_node_timestamp(message),
    )


async def _forward_to_msg(
    client: "Client", message: SatoriMessage, *, grp_id=0, uid=""
) -> Optional[MulitMsg]:
    nodes = []
    inline_children = []

    async def flush_inline_children() -> None:
        if not inline_children:
            return
        nodes.append(
            await _message_to_forward_node(
                client,
                SatoriMessage(content=list(inline_children)),
                grp_id=grp_id,
                uid=uid,
            )
        )
        inline_children.clear()

    for child in message._children:
        if isinstance(child, SatoriMessage):
            await flush_inline_children()
            nodes.append(await _message_to_forward_node(client, child, grp_id=grp_id, uid=uid))
        elif isinstance(child, SatoriCustom) and child.type == "message":
            await flush_inline_children()
            nodes.append(
                await _message_to_forward_node(
                    client,
                    SatoriMessage(
                        id=child._attrs.get("id"),
                        forward=child._attrs.get("forward"),
                        content=child._children,
                    ),
                    grp_id=grp_id,
                    uid=uid,
                )
            )
        elif isinstance(child, SatoriCustom) and child.type == "template":
            await flush_inline_children()
            nodes.append(
                await _message_to_forward_node(
                    client,
                    SatoriMessage(content=child._children),
                    grp_id=grp_id,
                    uid=uid,
                )
            )
        else:
            inline_children.append(child)
    await flush_inline_children()
    if not nodes:
        resid = message.id or message._attrs.get("id")
        if resid:
            return MulitMsg(resid=str(resid), file_name=str(message._attrs.get("file_name") or ""))
        logger.warning("ignore empty forward message without resid: attrs={!r}", message._attrs)
        return None
    return MulitMsg(messages=nodes)


async def satori_to_forward_msg(
    client: "Client",
    msgs: List[SatoriElement],
    *,
    grp_id=0,
    uid="",
) -> Optional[MulitMsg]:
    if len(msgs) != 1:
        return None
    message = msgs[0]
    if not isinstance(message, SatoriMessage) or not message.forward:
        return None
    return await _forward_to_msg(client, message, grp_id=grp_id, uid=uid)


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
            elif isinstance(m, SatoriMessage) and m.forward:
                forward_msg = await _forward_to_msg(client, m, grp_id=grp_id, uid=uid)
                if forward_msg:
                    new_msg.append(forward_msg)
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
