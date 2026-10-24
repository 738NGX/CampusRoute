from dataclasses import dataclass
from pathlib import Path


class InstallationError(RuntimeError):
    """An APK installation failed before any location session was opened."""


class SessionError(RuntimeError):
    """A device session failed; the console can discard it and accept a new one."""


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    label: str


class IosBackend:
    name = 'iPhone'

    def __init__(self):
        try:
            from campusroute import device
        except ModuleNotFoundError as error:
            raise RuntimeError('iPhone 后端需要可选依赖，请执行 python -m pip install -e ".[ios]"。') from error
        self.device = device

    async def devices(self):
        return [DeviceInfo(item.serial, await self.device.device_label(item.serial))
                for item in await self.device.usb_devices()]

    def connection(self):
        return self.device.DeviceConnection()


def get_backend(name: str, adb: str | None = None, root: Path | None = None):
    if name == 'ios':
        return IosBackend()
    from campusroute.android import AndroidBackend
    return AndroidBackend(adb, root)
