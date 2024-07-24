from lagrange.client.client import Client
from satori import Api
from satori.server import Request, Adapter

from .types import API_HANDLER


def register_api(
    api: Api,
    adapter: Adapter,
    client: Client,
    handler: API_HANDLER,
):
    @adapter.route(api)
    async def handler_wrapper(request: Request):
        return await handler(client, request)
