from typing import Tuple, List

from lagrange.client.client import Client
from satori.server import Api, Server
from .utils import register_api
from .types import API_HANDLER
from .handler import msg_create, msg_delete, msg_get

__all__ = ["apply_api_handlers"]

ALL_APIS: List[Tuple[Api, API_HANDLER]] = [
    (Api.MESSAGE_CREATE, msg_create),
    (Api.MESSAGE_DELETE, msg_delete),
    (Api.MESSAGE_GET, msg_get),
]


def apply_api_handlers(
    server: Server,
    client: Client,
):
    for api, api_handler in ALL_APIS:
        register_api(api, server, client, api_handler)
