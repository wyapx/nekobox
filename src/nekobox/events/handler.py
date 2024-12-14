import re
from typing import Optional, Union
from datetime import datetime, timedelta

from launart import Launart
from loguru import logger as log
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
    GroupReaction,
    GroupMemberQuit,
    GroupNameChanged,
    GroupMemberJoined,
    GroupMemberJoinedByInvite,
    GroupMemberJoinRequest,
)

from ..msgid import encode_msgid
from ..transformer import msg_to_satori
from ..uid import save_uid, resolve_uin, resolve_uid

logger = log.patch(lambda r: r.update(name="nekobox.events"))


def escape_tag(s: str) -> str:
    """用于记录带颜色日志时转义 `<tag>` 类型特殊标签

    参考: [loguru color 标签](https://loguru.readthedocs.io/en/stable/api/logger.html#color)

    Args:
        s: 需要转义的字符串
    """
    return re.sub(r"</?((?:[fb]g\s)?[^<>\s]*)>", r"\\\g<0>", s)


async def on_grp_msg(client: Client, event: GroupMessage, login: Login) -> Optional[Event]:
    save_uid(event.uin, event.uid)
    content = await msg_to_satori(event.msg_chain, client.uin, gid=event.grp_id)
    msg = "".join(str(i) for i in content)
    logger.info(f"[message-created] {event.nickname}({event.uin})@{event.grp_id}: {escape_tag(msg)!r}")
    usr = User(
        str(event.uin),
        event.nickname,
        avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640",
        is_bot=event.is_bot,
    )
    channel = Channel(encode_msgid(1, event.grp_id), ChannelType.TEXT, event.grp_name)
    guild = Guild(
        str(event.grp_id), event.grp_name, f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"
    )
    member = Member(usr, event.nickname, avatar=usr.avatar)
    cache = Launart.current().get_component(MemcacheService).cache
    await cache.set(f"guild@{guild.id}", guild, timedelta(minutes=5))
    await cache.set(f"channel@{channel.id}", channel, timedelta(minutes=5))
    await cache.set(f"user@{usr.id}", usr, timedelta(minutes=5))
    await cache.set(f"member@{guild.id}#{usr.id}", member, timedelta(minutes=5))
    return Event(
        EventType.MESSAGE_CREATED,
        datetime.fromtimestamp(event.time),
        login,
        channel=channel,
        guild=guild,
        user=usr,
        member=member,
        message=MessageObject.from_elements(str(event.seq), content),
    )


async def on_grp_recall(client: Client, event: GroupRecall, login: Login) -> Optional[Event]:
    uin = resolve_uin(event.uid)
    cache = Launart.current().get_component(MemcacheService).cache
    usr = await cache.get(f"user@{uin}")
    guild = await cache.get(f"guild@{event.grp_id}")
    channel = await cache.get(f"channel@{encode_msgid(1, event.grp_id)}")
    member = await cache.get(f"member@{event.grp_id}#{uin}")
    if not usr or not member:
        info = (await client.get_grp_member_info(event.grp_id, event.uid)).body[0]
        usr = User(
            str(uin),
            info.nickname,
            info.name.string if info.name else None,
            avatar=f"https://q1.qlogo.cn/g?b=qq&nk={uin}&s=640",
        )
        member = Member(usr, info.name.string if info.name else info.nickname, avatar=usr.avatar)
        await cache.set(f"user@{uin}", usr, timedelta(minutes=5))
        await cache.set(f"member@{event.grp_id}#{uin}", member, timedelta(minutes=5))
    if not guild or not channel:
        grp_list = (await client.get_grp_list()).grp_list
        for g in grp_list:
            _guild = Guild(str(g.grp_id), g.info.grp_name, f"https://p.qlogo.cn/gh/{g.grp_id}/{g.grp_id}/640")
            _channel = Channel(encode_msgid(1, g.grp_id), ChannelType.TEXT, g.info.grp_name)
            await cache.set(f"guild@{g.grp_id}", _guild, timedelta(minutes=5))
            await cache.set(f"channel@{_channel.id}", _channel, timedelta(minutes=5))
            if _guild.id == str(event.grp_id):
                guild = _guild
                channel = _channel
        if not guild or not channel:
            guild = Guild(
                str(event.grp_id),
                str(event.grp_id),
                f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640",
            )
            channel = Channel(encode_msgid(1, event.grp_id), ChannelType.TEXT, str(event.grp_id))

    logger.info(f"[message-deleted] {usr.nick}({usr.id})@{guild.id}: {event.seq}")
    return Event(
        EventType.MESSAGE_DELETED,
        datetime.fromtimestamp(event.time),
        login,
        channel=channel,
        guild=guild,
        user=usr,
        member=member,
        message=MessageObject(str(event.seq), event.suffix),
    )


async def on_friend_msg(client: Client, event: FriendMessage, login: Login) -> Optional[Event]:
    save_uid(event.from_uin, event.from_uid)
    content = await msg_to_satori(event.msg_chain, client.uin, uid=event.from_uid)
    msg = "".join(str(i) for i in content)
    cache = Launart.current().get_component(MemcacheService).cache
    user = await cache.get(f"user@{event.from_uin}")
    if not user:
        frd_list = await client.get_friend_list()
        for frd in frd_list:
            _user = User(
                str(frd.uin),
                frd.nickname,
                frd.remark,
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={frd.uin}&s=640",
            )
            await cache.set(f"user@{frd.uin}", _user, timedelta(minutes=5))
            if frd.uin == event.from_uin:
                user = _user
    if not user:
        info = await client.get_user_info(event.from_uid)
        user = User(
            str(event.from_uin), info.name, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.from_uin}&s=640"
        )
    logger.info(f"[message-created] {user.nick or user.name}({user.id}): {escape_tag(msg)!r}")
    return Event(
        EventType.MESSAGE_CREATED,
        datetime.fromtimestamp(event.timestamp),
        login,
        user=user,
        channel=Channel(encode_msgid(2, event.from_uin), ChannelType.DIRECT, user.name),
        message=MessageObject.from_elements(str(event.seq), content),
    )


async def on_client_online(client: Client, event: ClientOnline, login: Login) -> Optional[Event]:
    logger.debug("[login-updated]: online")
    login.status = LoginStatus.ONLINE
    return Event(
        EventType.LOGIN_UPDATED,
        datetime.now(),
        login,
    )


async def on_client_offline(client: Client, event: ClientOffline, login: Login) -> Optional[Event]:
    logger.debug(f"[login-updated]: {'reconnect' if event.recoverable else 'disconnect'}")
    login.status = LoginStatus.RECONNECT if event.recoverable else LoginStatus.DISCONNECT
    return Event(
        EventType.LOGIN_UPDATED,
        datetime.now(),
        login,
    )


async def on_grp_name_changed(client: Client, event: GroupNameChanged, login: Login) -> Event:
    operator_id = resolve_uin(event.operator_uid)
    cache = Launart.current().get_component(MemcacheService).cache
    guild = Guild(
        str(event.grp_id), event.name_new, f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"
    )
    await cache.set(f"guild@{guild.id}", guild, timedelta(minutes=5))
    operator = await cache.get(f"member@{event.grp_id}#{operator_id}")
    if not operator:
        info = (await client.get_grp_member_info(event.grp_id, event.operator_uid)).body[0]
        info1 = await client.get_user_info(event.operator_uid)
        operator = Member(
            User(
                str(operator_id),
                info1.name,
                info.nickname,
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={operator_id}&s=640",
            ),
            info.name.string if info.name else info.nickname,
            avatar=f"https://q1.qlogo.cn/g?b=qq&nk={operator_id}&s=640",
        )
        await cache.set(f"member@{event.grp_id}#{operator_id}", operator, timedelta(minutes=5))
    logger.info(f"[guild-updated] {operator.nick} changed the group name to {event.name_new}")
    return Event(
        EventType.GUILD_UPDATED,
        datetime.now(),
        login,
        guild=guild,
        user=User(
            str(client.uin), str(client.uin), avatar=f"https://q1.qlogo.cn/g?b=qq&nk={client.uin}&s=640"
        ),
        operator=operator.user,
    )


async def on_member_joined(client: Client, event: Union[GroupMemberJoined, GroupMemberJoinedByInvite], login: Login) -> Event:
    cache = Launart.current().get_component(MemcacheService).cache
    try:
        if isinstance(event, GroupMemberJoined):
            uid = event.uid
            uin = resolve_uin(event.uid)
        else:
            uin = event.uin
            uid = resolve_uid(event.uin)
        member = await cache.get(f"member@{event.grp_id}#{uin}")
        if not member:
            info = (await client.get_grp_member_info(event.grp_id, uid)).body[0]
            user = User(str(uin), info.nickname, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={uin}&s=640")
            member = Member(
                user,
                info.name.string if info.name else info.nickname,
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={uin}&s=640",
            )
            await cache.set(f"member@{event.grp_id}#{uin}", member, timedelta(minutes=5))
    except ValueError:
        uin = str(getattr(event, "uin", getattr(event, "uid", "0")))
        user = User(uin, uin, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={uin}&s=640")
        member = Member(user, user.name, avatar=user.avatar)
    guild = await cache.get(f"guild@{event.grp_id}")
    if not guild:
        grp_list = (await client.get_grp_list()).grp_list
        for g in grp_list:
            _guild = Guild(str(g.grp_id), g.info.grp_name, f"https://p.qlogo.cn/gh/{g.grp_id}/{g.grp_id}/640")
            await cache.set(f"guild@{g.grp_id}", _guild, timedelta(minutes=5))
            if _guild.id == str(event.grp_id):
                guild = _guild
        if not guild:
            guild = Guild(
                str(event.grp_id),
                str(event.grp_id),
                f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640",
            )
    logger.info(f"[guild-member-added] {member.nick}({uin}) joined {guild.name}({guild.id})")
    return Event(
        EventType.GUILD_MEMBER_ADDED,
        datetime.now(),
        login,
        guild=guild,
        member=member,
        user=member.user,
    )


async def on_member_quit(client: Client, event: GroupMemberQuit, login: Login) -> Optional[Event]:
    cache = Launart.current().get_component(MemcacheService).cache
    member = await cache.get(f"member@{event.grp_id}#{event.uin}")
    if not member:
        info = (await client.get_grp_member_info(event.grp_id, event.uid)).body[0]
        user = User(str(event.uin), info.nickname, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640")
        member = Member(
            user,
            info.name.string if info.name else info.nickname,
            avatar=f"https://q1.qlogo.cn/g?b=qq&nk={event.uin}&s=640",
        )
        await cache.set(f"member@{event.grp_id}#{event.uin}", member, timedelta(minutes=5))
    guild = await cache.get(f"guild@{event.grp_id}")
    if not guild:
        grp_list = (await client.get_grp_list()).grp_list
        for g in grp_list:
            _guild = Guild(str(g.grp_id), g.info.grp_name, f"https://p.qlogo.cn/gh/{g.grp_id}/{g.grp_id}/640")
            await cache.set(f"guild@{g.grp_id}", _guild, timedelta(minutes=5))
            if _guild.id == str(event.grp_id):
                guild = _guild
        if not guild:
            guild = Guild(
                str(event.grp_id),
                str(event.grp_id),
                f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640",
            )
    operator = None
    if event.is_kicked and event.operator_uid:
        operator_id = resolve_uin(event.operator_uid)
        operator = await cache.get(f"member@{event.grp_id}#{operator_id}")
        if not operator:
            info = (await client.get_grp_member_info(event.grp_id, event.operator_uid)).body[0]
            info1 = await client.get_user_info(event.operator_uid)
            operator = Member(
                User(
                    str(operator_id),
                    info1.name,
                    info.nickname,
                    avatar=f"https://q1.qlogo.cn/g?b=qq&nk={operator_id}&s=640",
                ),
                info.name.string if info.name else info.nickname,
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={operator_id}&s=640",
            )
            await cache.set(f"member@{event.grp_id}#{operator_id}", operator, timedelta(minutes=5))
    logger.info(
        f"[guild-member-removed] {member.nick}({event.uin}) left {guild.name}({guild.id}) "
        f"{f'by {operator.nick}({operator.user.id})' if operator else ''}"  # type: ignore
    )
    return Event(
        EventType.GUILD_MEMBER_REMOVED,
        datetime.now(),
        login,
        guild=guild,
        member=member,
        user=member.user,
        operator=operator.user if operator else None,
    )


async def on_grp_member_request(client: Client, event: GroupMemberJoinRequest, login: Login) -> Optional[Event]:
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
    await cache.set(f"user@{user_id}", user, timedelta(minutes=5))
    guild = Guild(
        str(event.grp_id), req.group.grp_name, f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640"
    )
    await cache.set(f"guild@{event.grp_id}", guild, timedelta(minutes=5))
    logger.info(f"[guild-member-request] {user.nick}({user.id}) requested to join {guild.name}({guild.id})")
    return Event(
        EventType.GUILD_MEMBER_REQUEST,
        datetime.now(),
        login,
        guild=guild,
        user=user,
        member=Member(user, user.name),
        message=MessageObject(id=str(req.seq), content=req.comment),
    )


async def on_grp_reaction(client: Client, event: GroupReaction, login: Login) -> Optional[Event]:
    user_id = resolve_uin(event.uid)

    if event.is_emoji:
        emoji = chr(event.emoji_id)
    else:
        emoji = f"face:{event.emoji_id}"

    cache = Launart.current().get_component(MemcacheService).cache
    member = await cache.get(f"member@{event.grp_id}#{user_id}")
    if not member:
        info = (await client.get_grp_member_info(event.grp_id, event.uid)).body[0]
        user = User(str(user_id), info.nickname, avatar=f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640")
        member = Member(
            user,
            info.name.string if info.name else info.nickname,
            avatar=f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640",
        )
        await cache.set(f"member@{event.grp_id}#{user_id}", member, timedelta(minutes=5))
    guild = await cache.get(f"guild@{event.grp_id}")
    if not guild:
        grp_list = (await client.get_grp_list()).grp_list
        for g in grp_list:
            _guild = Guild(str(g.grp_id), g.info.grp_name, f"https://p.qlogo.cn/gh/{g.grp_id}/{g.grp_id}/640")
            await cache.set(f"guild@{g.grp_id}", _guild, timedelta(minutes=5))
            if _guild.id == str(event.grp_id):
                guild = _guild
        if not guild:
            guild = Guild(
                str(event.grp_id),
                str(event.grp_id),
                f"https://p.qlogo.cn/gh/{event.grp_id}/{event.grp_id}/640",
            )
    if event.is_increase:
        action = "added"
    else:
        action = "removed"
    logger.info(f"[reaction-{action}] {member.nick}({user_id}) reacted {emoji} to message {event.seq}")
    return Event(
        EventType.REACTION_ADDED if event.is_increase else EventType.REACTION_REMOVED,
        datetime.now(),
        login,
        guild=guild,
        user=member.user,
        member=member,
        _type="reaction",
        _data={"message_id": event.seq, "emoji": emoji, "count": event.emoji_count},
    )
