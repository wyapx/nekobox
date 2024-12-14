from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from contextlib import suppress
from typing import Set, List, Literal, Optional
from datetime import datetime, timedelta

from loguru import logger
from lagrange import version
from qrcode.main import QRCode
from satori.server import Adapter
from lagrange.info import InfoManager
from lagrange.info.app import app_list
from lagrange.client.client import Client
from launart import Launart, any_completed
from satori import User, LoginStatus, Api
from satori.model import Login
from satori.server import Request
from lagrange.utils.sign import sign_provider
from lagrange.utils.audio.decoder import decode
from starlette.responses import Response
from graia.amnesia.builtins.memcache import MemcacheService

from .consts import PLATFORM
from .utils import cx_server, HttpCatProxies, decode_audio_available, decode_audio
from .log import patch_logging
from .apis import apply_api_handlers
from .events import apply_event_handler


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
            "https://multimedia.nt.qq.com.cn/",
        ]

    async def publisher(self):
        seq = 0
        while True:
            ev = await self.queue.get()
            ev.id = seq
            yield ev
            seq += 1

    def ensure(self, platform: str, self_id: str) -> bool:
        # upload://{platform}/{self_id}/{path}...
        return platform == PLATFORM and self_id == str(self.uin)

    async def handle_internal(self, request: Request, path: str) -> Response:
        if not path.startswith("_raw"):
            res_typ, src_typ, src, key = path.split("/", 3)
            if res_typ == "audio":
                if src_typ == "gid":
                    link = await self.client.fetch_audio_url(key, gid=int(src))
                elif src_typ == "uid":
                    link = await self.client.fetch_audio_url(key, uid=src)
                else:
                    raise ValueError(f"Unknown source type: {src_typ}")
                raw = await HttpCatProxies.request(
                    "GET",
                    link.replace("https", "http"),  # multimedia server certificate check failure
                    conn_timeout=15
                )
                if raw.code != 200:
                    raise ConnectionError(raw.code, raw.text())
                data = raw.decompressed_body
                typ = decode(BytesIO(data))
                if decode_audio_available(typ.type):
                    return Response(await decode_audio(typ.type, data))
                else:
                    return Response(data)
        raise NotImplementedError(path)

    async def handle_proxied(self, prefix: str, url: str) -> Optional[Response]:
        url = url.replace("&amp;", "&")
        if prefix == "https://multimedia.nt.qq.com.cn/":
            _, rkey = await self.client.get_rkey()
            url = f"{url}{rkey}"
        elif prefix == "https://gchat.qpic.cn":
            if url.startswith("https://gchat.qpic.cn/download"):
                _, rkey = await self.client.get_rkey()
                url = f"{url}{rkey}"
        return await super().handle_proxied(prefix, url)

    def _get_login(self):
        return Login(
            str(self.client.uin),
            (
                (LoginStatus.ONLINE if self.client.online.is_set() else LoginStatus.CONNECT)
                if not self.client._network._stop_flag
                else LoginStatus.DISCONNECT
            ),
            "nekobox",
            PLATFORM,
            User(
                str(self.client.uin),
                name=self.name or str(self.client.uin),
                avatar=f"https://q1.qlogo.cn/g?b=qq&nk={self.client.uin}&s=640",
            ),
            features=[
                "message.delete",
                "guild.plain",
            ],
        )

    async def get_logins(self) -> List[Login]:
        return [self._get_login()]

    @property
    def required(self) -> Set[str]:
        return set()

    def __init__(
        self,
        uin: int,
        sign_url: str | None = None,
        protocol: Literal["linux", "macos", "windows"] = "linux",
        log_level: str = "INFO",
        use_png: bool = False,
    ):
        self.log_level = log_level.upper()

        scope = Path.cwd() / "bots" / str(uin)
        scope.mkdir(exist_ok=True, parents=True)

        self.im = InfoManager(uin, scope / "device.json", scope / "sig.bin")
        self.uin = uin
        self.name = ""
        self.info = app_list[protocol]
        self.sign = sign_provider(sign_url) if sign_url else None
        self.queue = asyncio.Queue()
        self.use_png = use_png
        super().__init__()

    client: Client

    @property
    def stages(self) -> Set[Literal["preparing", "blocking", "cleanup"]]:
        return {"preparing", "blocking", "cleanup"}

    async def qrlogin(self, client: Client) -> bool:
        fetch_rsp = await client.fetch_qrcode()
        if isinstance(fetch_rsp, int):
            raise AssertionError(f"Failed to fetch QR code: {fetch_rsp}")
        png, link = fetch_rsp
        if self.use_png:
            path = Path.cwd() / "login_qrcode.png"
            logger.info(f"save QRCode to '{path.resolve()}'")
            with open(path, "wb+") as f:
                f.write(png)
        else:
            logger.debug(f"QR code link: <link>{link}</link>")
            qr = QRCode()
            qr.add_data(link)
            qr.print_ascii()
        logger.info("Please use Tencent QQ to scan QR code")
        try:
            return await client.qrcode_login(3)
        except AssertionError as e:
            logger.error(f"qrlogin error: {e.args[0]}")
            return False

    async def launch(self, manager: Launart):
        logger.info(f"Running on '{version.__version__}' for {self.uin}")
        tk = cx_server.set(self.server)

        with self.im as im:
            if (
                im.sig_info.last_update
                and (datetime.fromtimestamp(im.sig_info.last_update) + timedelta(30)) < datetime.now()
            ):
                logger.warning("siginfo expired")
                im.renew_sig_info()

            self.client = client = Client(
                self.uin,
                self.info,
                im.device,
                im.sig_info,
                self.sign,
            )
            apply_event_handler(client, self.queue, self._get_login)
            apply_api_handlers(self, client)

            # special api handling
            @self.route(Api.LOGIN_GET)
            async def login_get(request: Request):
                logins = await self.get_logins()
                return logins[0]

            patch_logging(self.log_level)

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
                    else:
                        await self.client.register()
                        success = True

            async with self.stage("blocking"):
                if success:
                    im.save_all()
                    self.name = (await client.get_user_info(client.uin)).name
                    await any_completed(manager.status.wait_for_sigexit(), client._network.wait_closed())

            async with self.stage("cleanup"):
                logger.debug("stopping client...")
                await client.stop()

            logger.success("Client stopped")

        cx_server.reset(tk)
