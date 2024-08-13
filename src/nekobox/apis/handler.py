from datetime import datetime, timedelta

from launart import Launart
from satori.parser import parse
from satori.server import Request, route
from lagrange.client.client import Client
from lagrange.pb.service.group import FetchGrpRspBody
from graia.amnesia.builtins.memcache import MemcacheService
from satori import (
    User,
    Guild,
    Login,
    Member,
    Channel,
    PageResult,
    ChannelType,
    LoginStatus,
    MessageObject,
    transform,
)

from ..consts import PLATFORM
from ..uid import resolve_uid
from ..msgid import decode_msgid, encode_msgid
from ..transformer import msg_to_satori, satori_to_msg


async def login_get(client: Client, _request: Request[route.Login]):
    return Login(
        LoginStatus.ONLINE if client.online.is_set() else LoginStatus.OFFLINE,
        self_id=str(client.uin),
        platform=PLATFORM,
        user=User(
            str(client.uin), name=str(client.uin), avatar=f"https://q1.qlogo.cn/g?b=qq&nk={client.uin}&s=640"
        ),
    ).dump()


async def channel_list(client: Client, request: Request[route.ChannelListParam]):
    guild_id = int(request.params["guild_id"])
    guilds = await guild_get_list(client, request)  # type: ignore

    # _next = request.params.get("next")
    guild = next((i for i in guilds.data if i.id == str(guild_id)), None)
    return {
        "data": [Channel(encode_msgid(1, guild_id), ChannelType.TEXT, guild.name if guild else None).dump()]
    }


async def msg_create(client: Client, req: Request[route.MessageParam]):
    typ, uin = decode_msgid(req.params["channel_id"])
    tp = transform(parse(req.params["content"]))

    if typ == 1:
        rsp = await client.send_grp_msg(await satori_to_msg(client, tp, grp_id=uin), uin)
    elif typ == 2:
        rsp = await client.send_friend_msg(
            await satori_to_msg(client, tp, uid=resolve_uid(uin)), resolve_uid(uin)
        )
    else:
        raise NotImplementedError(typ)
    return [MessageObject.from_elements(str(rsp), tp)]


async def msg_delete(client: Client, req: Request[route.MessageOpParam]):
    typ, grp_id = decode_msgid(req.params["channel_id"])
    seq = int(req.params["message_id"])
    if typ == 1:
        rsp = await client.recall_grp_msg(grp_id, seq)
    else:
        raise NotImplementedError(typ)

    return [{"id": str(rsp), "content": "ok"}]


async def msg_get(client: Client, req: Request[route.MessageOpParam]):
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
        user=User(str(rsp.uin), rsp.nickname, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={rsp.uin}&s=640"),
    )


async def guild_member_kick(client: Client, req: Request[route.GuildMemberKickParam]):
    grp_id = int(req.params["guild_id"])
    user_id = int(req.params["user_id"])
    permanent = req.params.get("permanent", False)

    await client.kick_grp_member(grp_id, user_id, permanent)

    return [{"content": "ok"}]


async def guild_member_mute(client: Client, req: Request[route.GuildMemberMuteParam]):
    grp_id = int(req.params["guild_id"])
    user_id = int(req.params["user_id"])
    duration = int(req.params["duration"]) * 1000  # ms to s

    await client.set_mute_member(grp_id, user_id, duration)

    return [{"content": "ok"}]


async def guild_member_list(client: Client, req: Request[route.GuildXXXListParam]):
    grp_id = int(req.params["guild_id"])
    next_key = req.params.get("next")

    rsp = await client.get_grp_members(grp_id, next_key=next_key)

    data = [
        Member(
            user=User(
                id=str(body.account.uin),
                name=body.nickname,
                avatar=f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={body.account.uin}&spec=640",
            ),
            nick=body.name.string if body.name else body.nickname,
            avatar=f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={body.account.uin}&spec=640",
            joined_at=datetime.fromtimestamp(body.joined_time),
        ).dump()
        for body in rsp.body
    ]

    return {
        "data": data,
        "next": rsp.next_key,
    }


async def guild_member_get(client: Client, req: Request[route.GuildMemberGetParam]):
    grp_id = int(req.params["guild_id"])
    user_id = int(req.params["user_id"])

    rsp = (await client.get_grp_member_info(grp_id, resolve_uid(user_id))).body[0]

    return [
        Member(
            user=User(
                id=str(rsp.account.uin),
                name=rsp.nickname,
                avatar=f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={rsp.account.uin}&spec=640",
            ),
            nick=rsp.name.string if rsp.name else rsp.nickname,
            avatar=f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={rsp.account.uin}&spec=640",
            joined_at=datetime.fromtimestamp(rsp.joined_time),
        ).dump()
    ]


async def guild_get_list(client: Client, req: Request[route.GuildListParam]) -> PageResult[Guild]:
    _next_key = req.params.get("next")
    cache = Launart.current().get_component(MemcacheService).cache

    if data := await cache.get("guild_list"):
        return PageResult(data, None)

    rsp = await client.get_grp_list()
    data = [
        Guild(str(i.grp_id), i.info.grp_name, f"https://p.qlogo.cn/gh/{i.grp_id}/{i.grp_id}/640")
        for i in rsp.grp_list
    ]

    await cache.set("guild_list", data, timedelta(minutes=5))

    return PageResult(data, None)


async def friend_channel(client: Client, req: Request[route.UserChannelCreateParam]):
    user_id = int(req.params["user_id"])
    try:
        pid = resolve_uid(user_id)
    except ValueError:
        pid = req.params.get("guild_id", None)
    return Channel(
        encode_msgid(2, user_id),
        ChannelType.DIRECT,
        str(user_id),
        pid,
    )


async def guild_member_req_approve(client: Client, req: Request[route.ApproveParam]):
    cache = Launart.current().get_component(MemcacheService).cache
    data: FetchGrpRspBody = await cache.get(f"grp_mbr_req#{req.params['message_id']}")
    await client.set_grp_request(
        data.group.grp_id,
        int(req.params["message_id"]),
        data.event_type,
        1 if req.params["approve"] else 2,
        req.params["comment"],
    )
    return [{"content": "ok"}]
