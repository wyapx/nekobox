from typing import Union

from satori import Api
from lagrange.client.client import Client
from satori.server import Adapter, Request

from .types import API_HANDLER


def register_api(
    api: Union[Api, str],
    adapter: Adapter,
    client: Client,
    handler: API_HANDLER,
):
    @adapter.route(api)
    async def handler_wrapper(request: Request):
        return await handler(client, request)
