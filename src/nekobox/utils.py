import sys

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
