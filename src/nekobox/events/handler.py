from typing import Optional
from datetime import datetime, timedelta

from loguru import logger
from launart import Launart
from lagrange.client.client import Client
from lagrange.client.events.friend import FriendMessage
from graia.amnesia.builtins.memcache import MemcacheService
from lagrange.client.events.service import ClientOnline, ClientOffline
from satori import (
    User,
    Event,
    Guild,
    Login,
    Member,
    Channel,
    EventType,
    ChannelType,
    LoginStatus,
    MessageObject,
)
from lagrange.client.events.group import (
    GroupRecall,
    GroupMessage,
    GroupMemberQuit,
    GroupNameChanged,
    GroupMemberJoined,
    GroupMemberJoinRequest,
    GroupReaction,
)

from ..consts import PLATFORM
from ..msgid import encode_msgid
from ..transformer import msg_to_satori
from ..uid import save_uid, resolve_uin


async def on_grp_msg(client: Client, event: GroupMessage) -> Optional[Event]:
    save_uid(event.uin, event.uid)
    content = await msg_to_satori(event.msg_chain)
    msg = "".join(str(i) for i in content)
    logger.info(f"{event.grp_name}[{event.nickname}]: {msg!r}")
    usr = User(
        str(event.uin),
        event.nickname,
        avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640",
        is_bot=event.is_bot,
    )
    return Event(
        0,
        EventType.MESSAGE_CREATED,
        PLATFORM,
        str(client.uin),
        datetime.fromtimestamp(event.time),
        channel=Channel(encode_msgid(1, event.grp_id), ChannelType.TEXT, event.grp_name),
        guild=Guild(
            str(event.grp_id), event.grp_name, f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"
        ),
        user=usr,
        member=Member(usr, event.nickname, avatar=usr.avatar),
        message=MessageObject.from_elements(str(event.seq), content),
    )


async def on_grp_recall(client: Client, event: GroupRecall) -> Optional[Event]:
    uin = resolve_uin(event.uid)
    usr = User(str(uin), str(uin), avatar=f"https://q1.qlogo.cn/g?b=qq&nk={uin}&s=640")
    return Event(
        0,
        EventType.MESSAGE_DELETED,
        PLATFORM,
        str(client.uin),
        datetime.fromtimestamp(event.time),
        channel=Channel(encode_msgid(1, event.grp_id), ChannelType.TEXT),
        guild=Guild(str(event.grp_id)),
        user=usr,
        member=Member(usr),
        message=MessageObject(str(event.seq), event.suffix),
    )


async def on_friend_msg(client: Client, event: FriendMessage) -> Optional[Event]:
    save_uid(event.from_uin, event.from_uid)
    content = await msg_to_satori(event.msg_chain)
    msg = "".join(str(i) for i in content)
    logger.info(f"{event.from_uin}[{event.from_uid}]: {msg!r}")
    return Event(
        0,
        EventType.MESSAGE_CREATED,
        PLATFORM,
        str(client.uin),
        datetime.fromtimestamp(event.timestamp),
        channel=Channel(encode_msgid(2, event.from_uin), ChannelType.DIRECT, event.from_uid),
        user=User(
            str(event.from_uin), event.from_uid, f"https://q1.qlogo.cn/g?b=qq&nk={event.from_uin}&s=640"
        ),
        message=MessageObject.from_elements(str(event.seq), content),
    )


async def on_client_online(client: Client, event: ClientOnline) -> Optional[Event]:
    logger.debug("login-updated: online")
    return Event(
        0,
        EventType.LOGIN_UPDATED,
        PLATFORM,
        str(client.uin),
        datetime.now(),
        login=Login(
            LoginStatus.ONLINE,
            self_id=str(client.uin),
            platform=PLATFORM,
            user=User(
                str(client.uin),
                name=str(client.uin),
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={client.uin}&s=640",
            ),
        ),
    )


async def on_client_offline(client: Client, event: ClientOffline) -> Optional[Event]:
    logger.debug(f"login-updated: {'reconnect' if event.recoverable else 'disconnect'}")
    return Event(
        0,
        EventType.LOGIN_UPDATED,
        PLATFORM,
        str(client.uin),
        datetime.now(),
        login=Login(
            LoginStatus.RECONNECT if event.recoverable else LoginStatus.DISCONNECT,
            self_id=str(client.uin),
            platform=PLATFORM,
            user=User(
                str(client.uin),
                name=str(client.uin),
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={client.uin}&s=640",
            ),
        ),
    )


async def on_grp_name_changed(client: Client, event: GroupNameChanged) -> Event:
    operator_id = resolve_uin(event.operator_uid)
    return Event(
        0,
        EventType.GUILD_UPDATED,
        PLATFORM,
        str(client.uin),
        datetime.now(),
        guild=Guild(
            str(event.grp_id), event.name_new, f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"
        ),
        operator=User(
            str(operator_id), str(operator_id), f"https://q1.qlogo.cn/g?b=qq&nk={operator_id}&s=640"
        ),
    )


async def on_member_joined(client: Client, event: GroupMemberJoined) -> Event:
    rsp = (await client.get_grp_member_info(event.grp_id, event.uid)).body[0]
    nickname = rsp.name.string if rsp.name else None
    user = User(
        str(event.uin), str(rsp.nickname), nickname, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640"
    )
    return Event(
        0,
        EventType.GUILD_MEMBER_ADDED,
        PLATFORM,
        str(client.uin),
        datetime.now(),
        guild=Guild(
            str(event.grp_id), str(event.grp_id), f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"
        ),
        member=Member(
            user,
            user.nick or user.name,
            avatar=user.avatar,
            joined_at=datetime.fromtimestamp(rsp.joined_time),
        ),
        user=user,
    )


async def on_member_quit(client: Client, event: GroupMemberQuit) -> Optional[Event]:
    user = User(str(event.uin), str(event.uin), avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640")
    operator = None
    if event.is_kicked and event.operator_uid:
        operator_id = resolve_uin(event.operator_uid)
        operator = User(
            str(operator_id), str(operator_id), avatar=f"https://q1.qlogo.cn/g?b=qq&nk={operator_id}&s=640"
        )
    return Event(
        0,
        EventType.GUILD_MEMBER_REMOVED,
        PLATFORM,
        str(client.uin),
        datetime.now(),
        guild=Guild(
            str(event.grp_id), str(event.grp_id), f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"
        ),
        member=Member(user, user.nick or user.name, avatar=user.avatar),
        user=user,
        operator=operator,
    )


async def on_grp_member_request(client: Client, event: GroupMemberJoinRequest) -> Optional[Event]:
    reqs = await client.fetch_grp_request(4)
    for req in reqs.requests:
        if req.group.grp_id == event.grp_id and req.target.uid == event.uid:
            break
    else:
        return
    cache = Launart.current().get_component(MemcacheService).cache
    await cache.set(f"grp_mbr_req#{req.seq}", req, timedelta(minutes=30))
    user_id = resolve_uin(event.uid)
    user = User(str(user_id), req.target.name, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640")
    return Event(
        0,
        EventType.GUILD_MEMBER_REQUEST,
        PLATFORM,
        str(client.uin),
        datetime.now(),
        guild=Guild(
            str(event.grp_id), req.group.grp_name, f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"
        ),
        user=user,
        member=Member(user),
        message=MessageObject(id=str(req.seq), content=req.comment),
    )


async def on_grp_reaction(client: Client, event: GroupReaction) -> Optional[Event]:
    user_id = resolve_uin(event.uid)

    if event.is_emoji:
        emoji = chr(event.emoji_id)
    else:
        emoji = f"face:{event.emoji_id}"

    return Event(
        0,
        EventType.REACTION_ADDED if event.is_increase else EventType.REACTION_REMOVED,
        PLATFORM,
        str(client.uin),
        datetime.now(),
        guild=Guild(
            str(event.grp_id), str(event.grp_id), avatar=f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"
        ),
        user=User(str(user_id), str(user_id), avatar=f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"),
        _type="reaction",
        _data={"message_id": event.seq, "emoji": emoji, "count": event.emoji_count}
    )
