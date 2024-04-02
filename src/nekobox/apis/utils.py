from lagrange.client.client import Client
from satori import Api
from satori.server import Request, Server

from .types import API_HANDLER


def register_api(
        api: Api,
        server: Server,
        client: Client,
        handler: API_HANDLER,
):
    @server.route(api)
    async def handler_wrapper(request: Request):
        return await handler(client, request)
