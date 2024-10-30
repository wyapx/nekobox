from datetime import datetime, timedelta

from launart import Launart
from satori.parser import parse
from loguru import logger as log
from satori.server import Request, route
from lagrange.client.client import Client
from lagrange.pb.service.group import FetchGrpRspBody
from graia.amnesia.builtins.memcache import MemcacheService
from satori import (
    User,
    Guild,
    Member,
    Channel,
    PageResult,
    ChannelType,
    MessageObject,
    transform,
)

from ..uid import resolve_uid, save_uid
from ..msgid import decode_msgid, encode_msgid
from ..transformer import msg_to_satori, satori_to_msg

logger = log.patch(lambda r: r.update(name="nekobox.apis"))


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
    if req.params["content"]:
        tp = transform(parse(req.params["content"]))

        if typ == 1:
            rsp = await client.send_grp_msg(await satori_to_msg(client, tp, grp_id=uin), uin)
        elif typ == 2:
            try:
                uid = resolve_uid(uin)
            except ValueError:  # Cache miss
                logger.warning(f"uin {uin} not in cache, fetching from server")
                friends = await client.get_friend_list()
                for friend in friends:
                    if friend.uid:
                        save_uid(friend.uin, friend.uid)
                uid = resolve_uid(uin)
            rsp = await client.send_friend_msg(
                await satori_to_msg(client, tp, uid=uid), uid
            )
        else:
            raise NotImplementedError(typ)
        return [MessageObject.from_elements(str(rsp), tp)]
    else:
        logger.warning("Empty message, ignore")
        return []


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
        await msg_to_satori(rsp.msg_chain, client.uin, gid=grp_id),
        channel=Channel(encode_msgid(1, rsp.grp_id), ChannelType.TEXT, rsp.grp_name),
        user=User(str(rsp.uin), rsp.nickname, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={rsp.uin}&s=640"),
    )


async def msg_list(client: Client, req: Request[route.MessageListParam]):
    typ, grp_id = decode_msgid(req.params["channel_id"])
    seq = 0

    if typ == 1:
        rsp = await client.get_grp_msg(grp_id, seq)
    else:
        raise NotImplementedError(typ)

    return [
        MessageObject.from_elements(
            str(r),
            await msg_to_satori(r.msg_chain, client.uin, gid=grp_id),
            channel=Channel(encode_msgid(1, r.grp_id), ChannelType.TEXT, r.grp_name),
            user=User(str(r.uin), r.nickname, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={r.uin}&s=640"),
        )
        for r in rsp
    ]


async def guild_member_kick(client: Client, req: Request[route.GuildMemberKickParam]):
    grp_id = int(req.params["guild_id"])
    user_id = int(req.params["user_id"])
    permanent = req.params.get("permanent", False)

    await client.kick_grp_member(grp_id, user_id, permanent)

    return [{"content": "ok"}]


async def guild_member_mute(client: Client, req: Request[route.GuildMemberMuteParam]):
    grp_id = int(req.params["guild_id"])
    user_id = int(req.params["user_id"])
    duration = int(req.params["duration"]) // 1000  # ms to s

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

    try:
        uid = resolve_uid(user_id)
    except ValueError:
        logger.warning(f"uin {user_id} not in cache, fetching from server")
        next_key = None
        uid = None
        while True:
            rsp = await client.get_grp_members(grp_id, next_key=next_key)
            for body in rsp.body:
                if body.account.uin is not None and body.account.uin == user_id:
                    save_uid(body.account.uin, body.account.uid)
                    uid = body.account.uid
                    break
            else:
                if rsp.next_key is not None:
                    next_key = rsp.next_key.decode()
            if not uid and not next_key:
                raise ValueError(f"uin {user_id} not found in {grp_id}")
            elif uid:
                break

    rsp = (await client.get_grp_member_info(grp_id, uid)).body[0]

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


async def friend_list(client: Client, req: Request[route.FriendListParam]):
    cache = Launart.current().get_component(MemcacheService).cache

    if data := await cache.get("friend_list"):
        return PageResult(data, None)

    friends = await client.get_friend_list()
    data = [
        User(
            id=str(f.uin),
            name=f.nickname,
            avatar=f"http://thirdqq.qlogo.cn/headimg_dl?dst_uin={f.uin}&spec=640",
        )
        for f in friends
    ]

    await cache.set("friend_list", data, timedelta(minutes=5))
    return PageResult(data, None)


async def _reaction_process(client: Client, req: Request, is_del: bool):
    typ, grp_id = decode_msgid(req.params["channel_id"])
    seq = int(req.params["message_id"])
    emoji = req.params["emoji"]

    if len(emoji) == 1:
        pass
    elif emoji.find("face:") == 0 and emoji[5:].isdigit():
        emoji = int(emoji[5:])
    else:
        raise ValueError(f"Invalid emoji value '{emoji}'")

    if typ == 1:
        await client.send_grp_reaction(grp_id, seq, emoji, is_cancel=is_del)
    else:
        raise TypeError("Guild only")

    return [{"content": "ok"}]


async def reaction_create(client: Client, req: Request[route.ReactionCreateParam]):
    return await _reaction_process(client, req, False)


async def reaction_delete(client: Client, req: Request[route.ReactionDeleteParam]):
    if "user_id" in req.params and req.params.get("user_id") != client.uin:
        raise ValueError("Cannot delete other user's reaction")
    return await _reaction_process(client, req, True)


async def reaction_clear(client: Client, req: Request[route.ReactionClearParam]):
    return await _reaction_process(client, req, True)
