import asyncio
import sys

from loguru import logger
from lagrange.utils.httpcat import HttpCat

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


async def download_resource(url: str, retry=3, timeout=5) -> bytes:
    if retry > 0:
        try:
            rsp = await asyncio.wait_for(
                HttpCat.request("GET", url),
                timeout=timeout
            )
            length = int(rsp.header.get("Content-Length", 0))
            if length and length != len(rsp.body):
                raise BufferError(f"Content-Length mismatch: {length} != {len(rsp.body)}")
            elif rsp.code != 200:
                raise LookupError(f"Request failed with status {rsp.code}:{rsp.status}")
            else:
                return rsp.decompressed_body
        except (asyncio.TimeoutError, BufferError, ConnectionError) as e:
            logger.error(f"Request failed: {repr(e)}")
        return await download_resource(url, retry - 1, timeout=timeout)
    else:
        raise ConnectionError(f"Request failed after many tries")
