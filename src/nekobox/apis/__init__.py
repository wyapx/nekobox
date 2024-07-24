from typing import Tuple, List

from lagrange.client.client import Client
from satori.server import Api, Adapter
from .utils import register_api
from .types import API_HANDLER
from .handler import (
    msg_create,
    msg_delete,
    msg_get,
    guild_member_kick,
    guild_member_mute,
    guild_get_list,
    guild_member_get,
    guild_member_list,
    login_get,
    channel_list,
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
    (Api.LOGIN_GET, login_get),
    (Api.CHANNEL_LIST, channel_list),
]


def apply_api_handlers(adapter: Adapter, client: Client):
    for api, api_handler in ALL_APIS:
        register_api(api, adapter, client, api_handler)
