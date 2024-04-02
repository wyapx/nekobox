import struct

from lagrange.client.client import Client

from satori import transform, MessageObject, Channel, ChannelType, User, Guild
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
        raise TypeError(typ)

    return [{"content": "ok"}]


async def guild_kick(client: Client, req: Request):
    typ, grp_id = decode_msgid(req.params["channel_id"])
    user_id = int(req.params["user_id"])
    permanent = bool(req.params["permanent"])

    if typ == 1:
        await client.kick_grp_member(grp_id, user_id, permanent)
    else:
        raise TypeError(typ)

    return [{"content": "ok"}]


async def guild_member_get(client: Client, req: Request):
    typ, grp_id = decode_msgid(req.params["channel_id"])
    user_id = int(req.params["user_id"])

    if typ == 1:
        return [{
            "user": {
                "id": str(user_id),
                "avatar": f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
            },
            "avatar": f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
        }]
    else:
        raise TypeError(typ)


async def guild_get_list(client: Client, req: Request):
    typ, grp_id = decode_msgid(req.params["channel_id"])

    if typ == 1:
        rsp = await client.get_grp_list()
        return [
            Guild(str(i.grp_id), i.info.grp_name, f"https://p.qlogo.cn/gh/{i.grp_id}/{i.grp_id}/640").dump()
            for i in rsp.grp_list
        ]
    else:
        raise TypeError(typ)
