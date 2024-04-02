import asyncio
from typing import List

from lagrange.client.client import Client
from satori import Login, LoginStatus, User
from satori.server import Provider, Event

from .consts import PLATFORM


class ServerProvider(Provider):
    def __init__(self, client: Client, event_queue: asyncio.Queue[Event], token: str):
        self._client = client
        self._token = token
        self._event_queue = event_queue

    def authenticate(self, token: str) -> bool:
        if token != self._token:
            return False
        return True

    async def get_logins(self) -> List[Login]:
        return [Login(
            LoginStatus.ONLINE,
            self_id=str(self._client.uin),
            platform=PLATFORM,
            user=User(
                str(self._client.uin),
                nick=str(self._client.uin),
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={self._client.uin}&s=640"
            )
        )]

    async def publisher(self):
        seq = 0
        while True:
            ev = await self._event_queue.get()
            ev.id = seq
            yield ev
            seq += 1
