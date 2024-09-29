import os
import ssl
import socket
import asyncio
import warnings
from io import BytesIO
from shutil import which
from typing import BinaryIO
from contextvars import ContextVar
from urllib.request import getproxies
from tempfile import TemporaryDirectory

from lagrange.utils.audio.enum import AudioType
from loguru import logger
from satori.server import Server
from lagrange.utils.audio.decoder import decode
from lagrange.utils.httpcat import HttpCat, HttpResponse

try:
    from pysilk import async_encode_file, async_decode
except ImportError:
    async_encode_file = None
    async_decode = None


def get_public_ip():
    st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        st.connect(("10.255.255.255", 1))
        IP = st.getsockname()[0]
    except Exception:
        IP = "localhost"
    finally:
        st.close()
    return IP


class HttpCatProxies(HttpCat):
    @classmethod
    async def _parse_proxy_response(cls, reader: asyncio.StreamReader) -> HttpResponse:
        stat = await cls._read_line(reader)
        if not stat:
            raise ConnectionResetError
        _, code, status = stat.split(" ", 2)
        header = {}
        cookies = {}
        while True:
            head_block = await cls._read_line(reader)
            if head_block:
                k, v = head_block.split(": ")
                if k.title() == "Set-Cookie":
                    name, value = v[: v.find(";")].split("=", 1)
                    cookies[name] = value
                else:
                    header[k.title()] = v
            else:
                break
        return HttpResponse(int(code), status, header, b"", cookies)

    async def connect_http_proxy(self, url: str, conn_timeout=0):
        address, path, with_ssl = self._parse_url(url)
        if conn_timeout:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(*address, ssl=with_ssl), conn_timeout
            )
        else:
            reader, writer = await asyncio.open_connection(*address, ssl=with_ssl)
        addr = f"{self.host}:{self.port}"
        await self._request(addr, reader, writer, "CONNECT", addr, header=self.header, wait_rsp=False)
        rsp = await self._parse_proxy_response(reader)

        logger.debug(f"open_tunnel[{rsp.code}]: {rsp.status}")
        if rsp.code == 200:
            self._reader = reader
            self._writer = writer
        else:
            raise ConnectionError(f"proxy error: {rsp.code}")

    async def send_request(
        self, method: str, path: str, body=None, follow_redirect=True, conn_timeout=0
    ) -> HttpResponse:
        if not (self._reader and self._writer):
            proxies = getproxies()
            if "http" in proxies:
                await self.connect_http_proxy(proxies.get("http"), conn_timeout)
                if self.ssl:
                    loop = asyncio.get_running_loop()
                    self._writer._protocol._over_ssl = True  # noqa, suppress warning
                    _transport = await loop.start_tls(
                        self._writer.transport,
                        self._writer.transport.get_protocol(),
                        ssl.create_default_context(),
                        server_side=False,
                        server_hostname=self.host,
                    )
                    self._writer._transport = _transport
        return await super().send_request(method, path, body, follow_redirect, conn_timeout)


async def download_resource(url: str, retry=5, timeout=10) -> bytes:
    if retry > 0:
        try:
            address, path, with_ssl = HttpCatProxies._parse_url(url)
            async with HttpCatProxies(*address, ssl=with_ssl) as req:
                rsp = await req.send_request("GET", path, conn_timeout=timeout)
            length = int(rsp.header.get("Content-Length", 0))
            if length and length != len(rsp.body):
                raise BufferError(f"Content-Length mismatch: {length} != {len(rsp.body)}")
            elif rsp.code != 200:
                raise LookupError(f"Request failed with status {rsp.code}:{rsp.status} {rsp.text()}")
            else:
                return rsp.decompressed_body
        except (asyncio.TimeoutError, BufferError, ConnectionError) as e:
            logger.error(f"Request failed: {repr(e)}")
        except ssl.SSLError as e:
            # Suppress SSL Error
            # like: [SSL: APPLICATION_DATA_AFTER_CLOSE_NOTIFY] application data after close notify (_ssl.c:2706)
            logger.error(f"SSL error: {repr(e)}")
        return await download_resource(url, retry - 1, timeout=timeout)
    else:
        raise ConnectionError(f"Request failed after many tries")


async def transform_audio(audio: BinaryIO) -> BinaryIO:
    try:
        typ = decode(audio)
    except ValueError:
        typ = None

    if typ:
        return audio
    elif not typ and async_encode_file:
        ffmpeg = which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found, transform fail")

        with TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, f"{os.urandom(16).hex()}.tmp")
            with open(input_path, "wb") as f:
                f.write(audio.read())

            out_path = os.path.join(temp_dir, f"{os.urandom(16).hex()}.tmp")
            proc = await asyncio.create_subprocess_exec(
                ffmpeg, "-i", input_path, "-f", "s16le", "-ar", "24000", "-ac", "1", "-y", out_path
            )
            if await proc.wait() != 0:
                raise ProcessLookupError(proc.returncode)

            data = await async_encode_file(out_path)
        return BytesIO(data)
    else:
        raise RuntimeError("module 'pysilk-mod' not install, transform fail")


async def decode_audio(typ: AudioType, audio: bytes) -> bytes:
    """audio to wav"""
    if async_decode and (typ == AudioType.tx_silk or typ == AudioType.silk_v3):
        return await async_decode(audio, to_wav=True)
    elif typ == AudioType.amr and (ffmpeg := which("ffmpeg")):
        with TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, f"{os.urandom(16).hex()}.tmp")
            with open(input_path, "wb") as f:
                f.write(audio)

            out_path = os.path.join(temp_dir, f"{os.urandom(16).hex()}.tmp")
            proc = await asyncio.create_subprocess_exec(
                ffmpeg, "-i", input_path, "-ab", "12.2k", "-ar", "16000", "-ac", "1", "-y", "-f", "wav", out_path
            )
            if await proc.wait() != 0:
                raise ProcessLookupError(proc.returncode)

            with open(out_path, "rb") as f:
                return f.read()
    raise NotImplementedError(typ)


def decode_audio_available(typ: AudioType) -> bool:
    if typ == AudioType.tx_silk or typ == AudioType.silk_v3:
        if not async_decode:
            warnings.warn("module 'pysilk-mod' not install, decode fail")
        else:
            return True
    elif typ == AudioType.amr:
        if not which("ffmpeg"):
            warnings.warn("ffmpeg not found, decode fail")
        else:
            return True
    return False


cx_server: ContextVar[Server] = ContextVar("server")
