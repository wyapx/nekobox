import asyncio
from typing import List

from loguru import logger
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
            logger.warning("Authentication failed, check upstream token setting.")
            return False
        return True

    async def get_logins(self) -> List[Login]:
        return [Login(
            (LoginStatus.ONLINE if self._client.online.is_set() else LoginStatus.CONNECT)
            if not self._client._network._stop_flag else LoginStatus.DISCONNECT,  # noqa
            self_id=str(self._client.uin),
            platform=PLATFORM,
            user=User(
                str(self._client.uin),
                name=str(self._client.uin),
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
