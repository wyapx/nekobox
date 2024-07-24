from datetime import datetime
from typing import Optional

from loguru import logger
from satori import EventType, Event, Channel, ChannelType, Guild, User, MessageObject, Login, LoginStatus, Member
from lagrange.client.client import Client
from lagrange.client.events.service import ClientOnline, ClientOffline
from lagrange.client.events.group import GroupMessage, GroupRecall, GroupMemberJoined, GroupMemberQuit
from lagrange.client.events.friend import FriendMessage

from ..uid import save_uid, resolve_uin
from ..msgid import encode_msgid
from ..consts import PLATFORM
from ..transformer import msg_to_satori


async def on_grp_msg(client: Client, event: GroupMessage) -> Optional[Event]:
    save_uid(event.uin, event.uid)
    content = await msg_to_satori(event.msg_chain)
    msg = "".join(str(i) for i in content)
    logger.info(f"{event.grp_name}[{event.nickname}]: {msg!r}")
    return Event(
        0,
        EventType.MESSAGE_CREATED,
        PLATFORM,
        str(client.uin),
        datetime.fromtimestamp(event.time),
        channel=Channel(encode_msgid(1, event.grp_id), ChannelType.TEXT, event.grp_name),
        guild=Guild(str(event.grp_id), event.grp_name),
        user=User(
            str(event.uin),
            event.nickname,
            avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640",
            is_bot=event.is_bot
        ),
        message=MessageObject.from_elements(str(event.seq), content),
    )


async def on_grp_recall(client: Client, event: GroupRecall) -> Optional[Event]:
    uin = resolve_uin(event.uid)
    return Event(
        0,
        EventType.MESSAGE_DELETED,
        PLATFORM,
        str(client.uin),
        datetime.fromtimestamp(event.time),
        channel=Channel(encode_msgid(1, event.grp_id), ChannelType.TEXT),
        user=User(str(uin), str(uin), avatar=f"https://q1.qlogo.cn/g?b=qq&nk={uin}&s=640"),
        message=MessageObject(str(event.seq), event.suffix)
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
        user=User(str(event.from_uin), event.from_uid, f"https://q1.qlogo.cn/g?b=qq&nk={event.from_uin}&s=640"),
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
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={client.uin}&s=640"
            )
        )
    )


async def on_client_offline(client: Client, event: ClientOffline) -> Optional[Event]:
    logger.debug(
        f"login-updated: {'reconnect' if event.recoverable else 'disconnect'}"
    )
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
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={client.uin}&s=640"
            )
        )
    )


async def on_member_joined(client: Client, event: GroupMemberJoined) -> Event:
    rsp = (await client.get_grp_member_info(event.grp_id, event.uid)).body[0]
    nickname = rsp.name.string if rsp.name else None
    user = User(
        str(event.uin),
        str(rsp.nickname),
        nickname,
        avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640"
    )
    return Event(
        0,
        EventType.GUILD_MEMBER_ADDED,
        PLATFORM,
        str(client.uin),
        datetime.now(),
        guild=Guild(str(event.grp_id), str(event.grp_id), f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"),
        member=Member(
            user,
            user.nick or user.name,
            avatar=user.avatar,
            joined_at=datetime.fromtimestamp(rsp.joined_time)
        ),
        user=user
    )


async def on_member_quit(client: Client, event: GroupMemberQuit) -> Optional[Event]:
    user = User(
        str(event.uin),
        avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640"
    )
    return Event(
        0,
        EventType.GUILD_MEMBER_REMOVED,
        PLATFORM,
        str(client.uin),
        datetime.now(),
        guild=Guild(str(event.grp_id), str(event.grp_id), f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"),
        member=Member(
            user,
            user.nick or user.name,
            avatar=user.avatar
        ),
        user=user
    )


# async def on_grp_request(client: Client, event: GroupMemberJoinRequest) -> Optional[Event]:
#     reqs = await client.fetch_grp_request(4)
#     for req in reqs.requests:
#         if req.group.grp_id == event.grp_id and req.target.uid == event.uid:
#             break
#     else:
#         raise AssertionError("Unknown request")
#     return Event(
#         0,
#         EventType.GUILD_MEMBER_REQUEST,
#         PLATFORM,
#         str(client.uin),
#         datetime.now(),
#         guild=Guild(str(event.grp_id)),
#         member=Member(User(str(resolve_uin(event.uid))))
#     )