import asyncio

from lagrange.client.client import Client
from lagrange.client.events.service import ClientOnline, ClientOffline
from lagrange.client.events.group import GroupMessage, GroupRecall, GroupMemberJoined, GroupMemberQuit
from lagrange.client.events.friend import FriendMessage
from satori import Event

from .handler import (
    on_grp_msg,
    on_friend_msg,
    on_grp_recall,
    on_client_online,
    on_client_offline,
    on_member_joined,
    on_member_quit
)
from .utils import event_register


__all__ = ["apply_event_handler"]
ALL_EVENT_HANDLERS = [
    (GroupMessage, on_grp_msg),
    (FriendMessage, on_friend_msg),
    (GroupRecall, on_grp_recall),
    (ClientOnline, on_client_online),
    (ClientOffline, on_client_offline),
    (GroupMemberJoined, on_member_joined),
    (GroupMemberQuit, on_member_quit),
]


def apply_event_handler(
        client: Client,
        queue: asyncio.Queue[Event],
):
    for event, ev_handler in ALL_EVENT_HANDLERS:
        event_register(client, queue, event, ev_handler)
