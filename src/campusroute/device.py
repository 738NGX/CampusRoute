import asyncio
import sys
from contextlib import AsyncExitStack

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.usbmux import list_devices


async def usb_devices():
    return [device for device in await list_devices() if device.is_usb]


async def device_label(serial: str):
    async with await create_using_usbmux(serial=serial, connection_type='USB') as lockdown:
        values = lockdown.all_values
        return f"{values['DeviceName']}（{values['ProductType']}，iOS {values['ProductVersion']}）"


class DeviceConnection:
    def __init__(self):
        self.resources = AsyncExitStack()
        self.location = None
        self.simulated = False

    async def connect(self, serial: str):
        async with await create_using_usbmux(serial=serial, connection_type='USB') as lockdown:
            version = lockdown.all_values['ProductVersion']
            parts = tuple(int(part) for part in version.split('.')[:2])
            if parts < (17, 4):
                raise RuntimeError('本版本要求 iOS 17.4 或更新版本。')
            enabled = await lockdown.get_value(
                domain='com.apple.security.mac.amfi', key='DeveloperModeStatus'
            )
            if not enabled:
                raise RuntimeError('请在 iPhone 设置 → 隐私与安全性中开启开发者模式，并完成重启确认。')
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-B', '-m', 'pymobiledevice3', 'mounter', 'auto-mount',
            '--udid', serial, '--userspace', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        try:
            async with asyncio.timeout(120):
                output, _ = await process.communicate()
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()
        if process.returncode != 0:
            detail = output.decode('utf-8', errors='replace').strip()
            raise RuntimeError(f'开发者服务准备失败。\n{detail}')
        rsd = await self.resources.enter_async_context(UserspaceRsdTunnel(serial=serial))
        dvt = await self.resources.enter_async_context(DvtProvider(rsd))
        self.location = await self.resources.enter_async_context(LocationSimulation(dvt))

    async def set(self, latitude: float, longitude: float):
        if self.location is None:
            raise RuntimeError('设备连接尚未建立。')
        # 在发送前标记，确保发送途中出错时也会尝试清理定位。
        self.simulated = True
        await asyncio.wait_for(self.location.set(latitude, longitude), timeout=5)

    async def close(self):
        if self.simulated and self.location is None:
            raise RuntimeError('恢复真实定位未能确认，请重新连接设备或重启手机。')
        try:
            if self.location is not None and self.simulated:
                await asyncio.wait_for(self.location.clear(), timeout=10)
                self.simulated = False
        finally:
            await self.resources.aclose()
            self.location = None
