import asyncio
import ssl
import sys
from urllib.request import getproxies

from loguru import logger
from lagrange.utils.httpcat import HttpCat, HttpResponse

try:
    from qrcode.main import QRCode as _QRCode

    class QRCode(_QRCode):
        def print_tty(self, out=None):
            if not out:
                out = sys.stdout
            if not self.data_cache:
                self.make()

            modcount = self.modules_count
            b = "  "
            w = "▇▇"

            out.write("\n")
            out.write(w * (modcount + 2))
            out.write("\n")
            for r in range(modcount):
                out.write(w)
                for c in range(modcount):
                    if self.modules[r][c]:
                        out.write(b)
                    else:
                        out.write(w)
                out.write(f"{w}\n")
            out.write(w * (modcount + 2))
            out.write("\n")
            out.flush()

except ImportError:
    QRCode = None


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
                k, v = head_block.split(": ")  # type: str
                if k.title() == "Set-Cookie":
                    name, value = v[: v.find(";")].split("=", 1)
                    cookies[name] = value
                else:
                    header[k.title()] = v
            else:
                break
        return HttpResponse(int(code), status, header, b"", cookies)

    async def connect_http_proxy(self, url: str, conn_timeout=0):
        address, path, ssl = self._parse_url(url)
        if conn_timeout:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(*address, ssl=ssl), conn_timeout
            )
        else:
            reader, writer = await asyncio.open_connection(*address, ssl=ssl)
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
        self,
        method: str,
        path: str,
        body=None,
        follow_redirect=True,
        conn_timeout=0
    ) -> HttpResponse:
        if not (self._reader and self._writer):
            proxies = getproxies()
            if "http" in proxies:
                await self.connect_http_proxy(proxies.get("http"))
                if self.ssl:
                    loop = asyncio.get_running_loop()
                    self._writer._protocol._over_ssl = True  # noqa, suppress warning
                    _transport = await loop.start_tls(
                        self._writer.transport,
                        self._writer.transport.get_protocol(),
                        ssl.create_default_context(),
                        server_side=False,
                        server_hostname=self.host
                    )
                    self._writer._transport = _transport
        return await super().send_request(method, path, body, follow_redirect, conn_timeout)


async def download_resource(url: str, retry=3, timeout=10) -> bytes:
    if retry > 0:
        try:
            address, path, ssl = HttpCatProxies._parse_url(url)
            async with HttpCatProxies(*address, ssl=ssl) as req:
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
        return await download_resource(url, retry - 1, timeout=timeout)
    else:
        raise ConnectionError(f"Request failed after many tries")
