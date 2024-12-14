import asyncio

from satori import Event
from lagrange.client.client import Client
from lagrange.client.events.friend import FriendMessage
from lagrange.client.events.service import ClientOnline, ClientOffline
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

from .utils import event_register, LOGIN_GETTER
from .handler import (
    on_grp_msg,
    on_friend_msg,
    on_grp_recall,
    on_member_quit,
    on_grp_reaction,
    on_client_online,
    on_member_joined,
    on_client_offline,
    on_grp_name_changed,
    on_grp_member_request,
)

__all__ = ["apply_event_handler"]
ALL_EVENT_HANDLERS = [
    (GroupMessage, on_grp_msg),
    (FriendMessage, on_friend_msg),
    (GroupRecall, on_grp_recall),
    (ClientOnline, on_client_online),
    (ClientOffline, on_client_offline),
    (GroupMemberJoined, on_member_joined),
    (GroupMemberJoinedByInvite, on_member_joined),
    (GroupMemberQuit, on_member_quit),
    (GroupNameChanged, on_grp_name_changed),
    (GroupMemberJoinRequest, on_grp_member_request),
    (GroupReaction, on_grp_reaction),
]


def apply_event_handler(client: Client, queue: asyncio.Queue[Event], login_getter: LOGIN_GETTER):
    for event, ev_handler in ALL_EVENT_HANDLERS:
        event_register(client, queue, event, ev_handler, login_getter)
