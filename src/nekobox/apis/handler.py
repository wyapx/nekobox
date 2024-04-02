import struct

from lagrange.client.client import Client

from satori import transform, MessageObject, Channel, ChannelType, User
from satori.parser import parse
from satori.server import Request, route

from nekobox.uid import resolve_uid
from nekobox.transformer import satori_to_msg, msg_to_satori
from nekobox.msgid import decode_msgid, encode_msgid


async def msg_create(client: Client, req: Request[route.MessageParam]):
    typ, uin = decode_msgid(req.params["channel_id"])
    tp = transform(parse(req.params["content"]))

    if typ == 1:
        rsp = await client.send_grp_msg(
            await satori_to_msg(client, tp, grp_id=uin), uin
        )
    elif typ == 2:
        rsp = await client.send_friend_msg(
            await satori_to_msg(client, tp, uid=resolve_uid(uin)),
            resolve_uid(uin)
        )
    else:
        raise NotImplementedError(typ)
    return [MessageObject.from_elements(str(rsp), tp)]


async def msg_delete(client: Client, req: Request):
    typ, grp_id = decode_msgid(req.params["channel_id"])
    seq = int(req.params["message_id"])
    if typ == 1:
        rsp = await client.recall_grp_msg(grp_id, seq)
    else:
        raise NotImplementedError(typ)

    return [{"id": str(rsp), "content": "ok"}]


async def msg_get(client: Client, req: Request):
    typ, grp_id = decode_msgid(req.params["channel_id"])
    seq = int(req.params["message_id"])
    if typ == 1:
        rsp = (await client.get_grp_msg(grp_id, seq))[0]
    else:
        raise NotImplementedError(typ)

    return MessageObject.from_elements(
        str(rsp),
        await msg_to_satori(rsp.msg_chain),
        channel=Channel(encode_msgid(1, rsp.grp_id), ChannelType.TEXT, rsp.grp_name),
        user=User(str(rsp.uin), rsp.nickname, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={rsp.uin}&s=640")
    )


async def guild_mute(client: Client, req: Request):
    typ, grp_id = decode_msgid(req.params["channel_id"])
    user_id = int(req.params["user_id"])
    duration = int(req.params["duration"]) * 1000  # ms to s

    if typ == 1:
        rsp = await client.set_mute_member(grp_id, user_id, duration)
        if rsp.ret_code:
            raise AssertionError(rsp.ret_code, rsp.err_msg)
    else:
        raise NotImplementedError(typ)

    return [{"content": "ok"}]