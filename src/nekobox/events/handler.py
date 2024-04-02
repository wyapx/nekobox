from datetime import datetime
from typing import Optional

from loguru import logger
from satori import EventType, Event, Channel, ChannelType, Guild, User, MessageObject
from lagrange.client.client import Client
from lagrange.client.events.group import GroupMessage, GroupRecall
from lagrange.client.events.friend import FriendMessage

from nekobox.uid import save_uid, resolve_uin
from nekobox.msgid import encode_msgid
from nekobox.consts import PLATFORM
from nekobox.transformer import msg_to_satori


async def on_grp_msg(client: Client, event: GroupMessage) -> Optional[Event]:
    save_uid(event.uin, event.uid)
    logger.info(f"{event.grp_name}[{event.nickname}]: {event.msg}")
    return Event(
        0,
        EventType.MESSAGE_CREATED,
        PLATFORM,
        str(client.uin),
        datetime.fromtimestamp(event.time),
        channel=Channel(encode_msgid(1, event.grp_id), ChannelType.TEXT, event.grp_name),
        guild=Guild(str(event.grp_id), event.grp_name),
        user=User(str(event.uin), event.nickname, f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640"),
        message=MessageObject.from_elements(str(event.seq), await msg_to_satori(event.msg_chain)),
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
        user=User(str(uin), str(uin), f"https://q1.qlogo.cn/g?b=qq&nk={uin}&s=640"),
        message=MessageObject(str(event.seq), event.suffix)
    )


async def on_friend_msg(client: Client, event: FriendMessage) -> Optional[Event]:
    save_uid(event.from_uin, event.from_uid)
    logger.info(f"{event.from_uin}[{event.from_uid}]: {event.msg}")
    return Event(
        0,
        EventType.MESSAGE_CREATED,
        PLATFORM,
        str(client.uin),
        datetime.fromtimestamp(event.timestamp),
        channel=Channel(encode_msgid(2, event.from_uin), ChannelType.DIRECT, event.from_uid),
        user=User(str(event.from_uin), event.from_uid, f"https://q1.qlogo.cn/g?b=qq&nk={event.from_uin}&s=640"),
        message=MessageObject.from_elements(encode_msgid(2, event.seq), await msg_to_satori(event.msg_chain)),
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