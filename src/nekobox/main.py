from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List, Set, Literal
from pathlib import Path
from contextlib import suppress

from launart import Launart, any_completed
from loguru import logger
from qrcode.main import QRCode
from graia.amnesia.builtins.memcache import MemcacheService

from satori import Login, LoginStatus, User
from satori.server import Adapter
from lagrange import version
from lagrange.client.client import Client
from lagrange.info import InfoManager
from lagrange.info.app import app_list
from lagrange.utils.sign import sign_provider

from .log import patch_logging
from .events import apply_event_handler
from .apis import apply_api_handlers
from .consts import PLATFORM


class NekoBoxAdapter(Adapter):
    def ensure_manager(self, manager: Launart):
        super().ensure_manager(manager)
        with suppress(ValueError):
            manager.add_component(MemcacheService())

    def get_platform(self) -> str:
        return PLATFORM

    @staticmethod
    def proxy_urls() -> List[str]:
        return [
            "http://thirdqq.qlogo.cn",
            "https://p.qlogo.cn/",
            "https://q1.qlogo.cn",
            "https://gchat.qpic.cn",
            "https://multimedia.nt.qq.com.cn/"
        ]

    async def publisher(self):
        seq = 0
        while True:
            ev = await self.queue.get()
            ev.id = seq
            yield ev
            seq += 1

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform == PLATFORM and self_id == str(self.uin)

    def authenticate(self, token: str) -> bool:
        if token != self.access_token:
            logger.warning("Authentication failed, check upstream token setting.")
            return False
        return True

    async def download_uploaded(self, platform: str, self_id: str, path: str) -> bytes:
        raise NotImplementedError

    async def get_logins(self) -> List[Login]:
        return [
            Login(
                (LoginStatus.ONLINE if self.client.online.is_set() else LoginStatus.CONNECT)
                if not self.client._network._stop_flag else LoginStatus.DISCONNECT,  # noqa
                self_id=str(self.client.uin),
                platform=PLATFORM,
                user=User(
                    str(self.client.uin),
                    name=str(self.client.uin),
                    avatar=f"https://q1.qlogo.cn/g?b=qq&nk={self.client.uin}&s=640"
                )
            )
        ]

    @property
    def required(self) -> Set[str]:
        return set()

    def __init__(
        self,
        uin: int,
        access_token: str,
        sign_url: str | None = None,
        protocol: Literal["linux", "macos", "windows"] = "linux",
        log_level: str = "INFO",
    ):
        self.access_token = access_token
        self.log_level = log_level.upper()

        scope = Path.cwd() / "bots" / str(uin)
        scope.mkdir(exist_ok=True, parents=True)

        self.im = InfoManager(uin, scope / "device.json", scope / "sig.bin")
        self.uin = uin
        self.info = app_list[protocol]
        self.sign = sign_provider(sign_url) if sign_url else None
        self.queue = asyncio.Queue()
        super().__init__()

    client: Client

    @property
    def stages(self) -> Set[Literal["preparing", "blocking", "cleanup"]]:
        return {"preparing", "blocking", "cleanup"}

    async def qrlogin(self, client) -> bool:
        fetch_rsp = await client.fetch_qrcode()
        if isinstance(fetch_rsp, int):
            raise AssertionError(f"Failed to fetch QR code: {fetch_rsp}")
        _, link = fetch_rsp
        logger.debug(link[:-34])
        qr = QRCode()
        qr.add_data(link)
        logger.info("Please use Tencent QQ to scan QR code")
        qr.print_ascii()

        try:
            return await client.qrcode_login(3)
        except AssertionError as e:
            logger.error(f"qrlogin error: {e.args[0]}")
            return False

    async def launch(self, manager: Launart):
        logger.info(f"Running on '{version.__version__}' for {self.uin}")
        with self.im as im:
            self.client = client = Client(
                self.uin,
                self.info,
                im.device,
                im.sig_info,
                self.sign,
            )
            apply_event_handler(client, self.queue)
            apply_api_handlers(self, client)
            async with self.stage("preparing"):
                client.connect()
                success = True
                if (datetime.fromtimestamp(im.sig_info.last_update) + timedelta(14)) > datetime.now():
                    logger.info("try to fast login")
                    if not await client.register():
                        logger.error("fast login failed, try to re-login...")
                        success = await client.easy_login()
                elif im.sig_info.last_update:
                    logger.warning("Refresh siginfo")
                    success = await client.easy_login()
                else:
                    success = False

            patch_logging(self.log_level)
            if not success:
                if not await self.qrlogin(client):
                    logger.error("login error")
                else:
                    success = True

            async with self.stage("blocking"):
                if success:
                    im.save_all()
                    await any_completed(
                        manager.status.wait_for_sigexit(),
                        client._network.wait_closed()
                    )

            async with self.stage("cleanup"):
                logger.debug("stopping client...")
                await client.stop()

            logger.success("Client stopped")
