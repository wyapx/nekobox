import struct
from datetime import datetime
from typing import List

from lagrange.client.client import Client
from lagrange.pb.service.group import GetGrpMemberInfoRspBody

from satori import transform, MessageObject, Channel, ChannelType, User, Guild, Member
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
    grp_id = int(req.params["guild_id"])
    user_id = int(req.params["user_id"])
    duration = int(req.params["duration"]) * 1000  # ms to s

    rsp = await client.set_mute_member(grp_id, user_id, duration)
    if rsp.ret_code:
        raise AssertionError(rsp.ret_code, rsp.err_msg)

    return [{"content": "ok"}]


async def guild_kick(client: Client, req: Request):
    grp_id = int(req.params["guild_id"])
    user_id = int(req.params["user_id"])
    permanent = bool(req.params["permanent"])

    await client.kick_grp_member(grp_id, user_id, permanent)

    return [{"content": "ok"}]


async def guild_member_list(client: Client, req: Request):
    grp_id = int(req.params["guild_id"])
    next_key = req.params.get("next")

    rsp = await client.get_grp_members(grp_id, next_key=next_key)

    data = [
        Member(
            user=User(
                id=str(body.account.uin),
                name=body.nickname,
                avatar=f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={body.account.uin}&spec=640"
            ),
            nick=body.name.string if body.name else body.nickname,
            avatar=f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={body.account.uin}&spec=640",
            joined_at=datetime.fromtimestamp(body.joined_time)
        ).dump() for body in rsp.body
    ]

    return {
        "data": data,
        "next": rsp.next_key,
    }


async def guild_member_get(client: Client, req: Request):
    grp_id = int(req.params["guild_id"])
    user_id = int(req.params["user_id"])

    rsp = (await client.get_grp_member_info(grp_id, resolve_uid(user_id))).body[0]

    return [
        Member(
            user=User(
                id=str(rsp.account.uin),
                name=rsp.nickname,
                avatar=f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={rsp.account.uin}&spec=640"
            ),
            nick=rsp.name.string if rsp.name else rsp.nickname,
            avatar=f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={rsp.account.uin}&spec=640",
            joined_at=datetime.fromtimestamp(rsp.joined_time)
        ).dump()
    ]


async def guild_get_list(client: Client, req: Request):
    _next_key = req.params.get("next")

    rsp = await client.get_grp_list()
    data = [
        Guild(str(i.grp_id), i.info.grp_name, f"https://p.qlogo.cn/gh/{i.grp_id}/{i.grp_id}/640").dump()
        for i in rsp.grp_list
    ]

    return {
        "data": data,
        "next": None,
    }
