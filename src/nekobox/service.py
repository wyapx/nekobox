from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Set, Literal

from lagrange.client.wtlogin.enum import QrCodeResult
from launart import Launart, Service, any_completed
from loguru import logger

from satori.server import Server
from lagrange import version
from lagrange.client.client import Client
from lagrange.info.app import app_list
from lagrange.utils.sign import sign_provider

from .info import InfoManager
from .log import patch_logging
from .provider import ServerProvider
from .events import apply_event_handler
from .apis import apply_api_handlers
from .utils import QRCode


class NekoBoxService(Service):
    @property
    def required(self) -> Set[str]:
        return set()

    id = "lagrange.satori.service"

    def __init__(
        self,
        server: Server,
        uin: int,
        access_token: str,
        sign_url: str | None = None,
        protocol: Literal["linux", "macos", "windows"] = "linux",
        log_level: str = "INFO",
    ):
        self.server = server
        self.uin = uin
        self.sign_url = sign_url
        self.access_token = access_token
        self.protocol = protocol
        self.log_level = log_level.upper()
        super().__init__()

    @property
    def stages(self) -> Set[Literal["preparing", "blocking", "cleanup"]]:
        return {"preparing", "blocking", "cleanup"}

    async def qrlogin(self, client, save_to="./qrcode.png") -> bool:
        logger.info("Login required")
        fetch_rsp = await client.fetch_qrcode()
        if isinstance(fetch_rsp, int):
            raise AssertionError(f"Failed to fetch QR code: {fetch_rsp}")
        else:
            png, link = fetch_rsp
        logger.debug(link[:-34])
        if QRCode:
            qr = QRCode()
            qr.add_data(link[:-34])
            qr.print_tty()
            logger.info("Use Tencent QQ to scan QR code")
        else:
            logger.warning("module 'qrcode' not available, save qrcode image to disk")
            with open(save_to, "wb") as f:
                f.write(png)
            logger.warning(f"save qrcode to {save_to}")
        logger.info("waiting for your operation...")

        try:
            return await client.qrcode_login(3)
        except AssertionError as e:
            logger.error(f"qrlogin error: {e.args[0]}")
            return False

    async def launch(self, manager: Launart):
        queue = asyncio.Queue()

        logger.info(f"Running on '{version.__version__}' for {self.uin}")

        app = app_list[self.protocol]
        with InfoManager(self.uin, "bots") as im:
            client = Client(
                self.uin,
                app,
                im.device,
                im.sig_info,
                sign_provider(self.sign_url) if self.sign_url else None,
            )

            self.server.apply(ServerProvider(client, queue, self.access_token))
            apply_event_handler(client, queue)
            apply_api_handlers(self.server, client)
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

                if not success:
                    if not await self.qrlogin(client):
                        logger.error("login error")
                        return

            im.save_all()

            patch_logging(self.log_level)
            async with self.stage("blocking"):
                await any_completed(
                    manager.status.wait_for_sigexit(),
                    client.wait_closed()
                )

            async with self.stage("cleanup"):
                await client.stop()
