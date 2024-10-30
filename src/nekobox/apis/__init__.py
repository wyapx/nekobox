from typing import List, Tuple

from satori.server import Api, Adapter
from lagrange.client.client import Client

from .types import API_HANDLER
from .utils import register_api
from .handler import (
    msg_get,
    msg_create,
    msg_delete,
    friend_list,
    channel_list,
    friend_channel,
    guild_get_list,
    reaction_clear,
    reaction_create,
    reaction_delete,
    guild_member_get,
    guild_member_kick,
    guild_member_list,
    guild_member_mute,
    guild_member_req_approve,
)

__all__ = ["apply_api_handlers"]

ALL_APIS: List[Tuple[Api, API_HANDLER]] = [
    (Api.MESSAGE_CREATE, msg_create),
    (Api.MESSAGE_DELETE, msg_delete),
    (Api.MESSAGE_GET, msg_get),
    (Api.GUILD_MEMBER_KICK, guild_member_kick),
    (Api.GUILD_MEMBER_MUTE, guild_member_mute),
    (Api.GUILD_LIST, guild_get_list),
    (Api.GUILD_MEMBER_GET, guild_member_get),
    (Api.GUILD_MEMBER_LIST, guild_member_list),
    (Api.CHANNEL_LIST, channel_list),
    (Api.USER_CHANNEL_CREATE, friend_channel),
    (Api.GUILD_MEMBER_APPROVE, guild_member_req_approve),
    (Api.FRIEND_LIST, friend_list),
    (Api.REACTION_CREATE, reaction_create),
    (Api.REACTION_DELETE, reaction_delete),
    (Api.REACTION_CLEAR, reaction_clear),
]


def apply_api_handlers(adapter: Adapter, client: Client):
    for api, api_handler in ALL_APIS:
        register_api(api, adapter, client, api_handler)
