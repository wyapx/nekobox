from typing import Tuple, List

from lagrange.client.client import Client
from satori.server import Api, Server
from .utils import register_api
from .types import API_HANDLER
from .handler import (
    msg_create,
    msg_delete,
    msg_get,
    guild_mute,
    guild_kick,
    guild_get_list,
    guild_member_get,
)

__all__ = ["apply_api_handlers"]

ALL_APIS: List[Tuple[Api, API_HANDLER]] = [
    (Api.MESSAGE_CREATE, msg_create),
    (Api.MESSAGE_DELETE, msg_delete),
    (Api.MESSAGE_GET, msg_get),
    (Api.GUILD_MEMBER_KICK, guild_kick),
    (Api.GUILD_MEMBER_MUTE, guild_mute),
    (Api.GUILD_LIST, guild_get_list),
    (Api.GUILD_MEMBER_GET, guild_member_get),
]


def apply_api_handlers(
    server: Server,
    client: Client,
):
    for api, api_handler in ALL_APIS:
        register_api(api, server, client, api_handler)
