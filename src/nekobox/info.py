from pathlib import Path
from loguru import logger
from lagrange.info import DeviceInfo, SigInfo


class InfoManager:
    def __init__(self, uin: int, save_path="bots"):
        root = Path.cwd() / save_path / str(uin)
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)

        self.uin: int = uin
        self._device_info_path: Path = root / "device.json"
        self._sig_info_path: Path = root / "sig.bin"
        self._device = None
        self._sig = None

    @property
    def device(self) -> DeviceInfo:
        assert self._device, "Device not initialized"
        return self._device

    @property
    def sig_info(self) -> SigInfo:
        assert self._sig, "SigInfo not initialized"
        return self._sig

    def renew_sig_info(self):
        self._sig = SigInfo.new()

    def save_all(self):
        with self._sig_info_path.open("wb") as f:
            f.write(self._sig.dump())

        with self._device_info_path.open("wb") as f:
            f.write(self._device.dump())

        logger.info("device info saved")

    def __enter__(self):
        if self._device_info_path.exists() and self._device_info_path.is_file():
            with self._device_info_path.open("rb") as f:
                self._device = DeviceInfo.load(f.read())
        else:
            logger.warning(f"{self._device_info_path} not found, generating...")
            self._device = DeviceInfo.generate(self.uin)

        if self._sig_info_path.exists() and self._sig_info_path.is_file():
            with self._sig_info_path.open("rb") as f:
                self._sig = SigInfo.load(f.read())
        else:
            logger.warning(f"{self._sig_info_path} not found, generating...")
            self._sig = SigInfo.new()
        return self

    def __exit__(self, *_):
        #self.save_all()
        pass
