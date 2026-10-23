import argparse
import asyncio
import logging
import math
import signal
import sys
import time
import webbrowser
from pathlib import Path

from campusroute import __version__
from campusroute.device import DeviceConnection, device_label, usb_devices
from campusroute.mapserver import MapServer
from campusroute.motion import Motion, pace_label, parse_pace
from campusroute.routes import RoutePath, presets, read_route
from campusroute.runtime import AlreadyRunningError, runtime

PHASE_NAMES = {
    'ready': '起点已准备', 'running': '正在移动', 'paused': '移动已暂停',
    'stopped': '本次移动已中止', 'finished': '目标距离已完成',
}


class ConsoleApp:
    def __init__(self, root: Path):
        self.root = root
        self.routes = presets()
        self.route = self.routes[0]
        self.pace_s = 120
        self.target_m = 5000
        self.connection = None
        self.motion = None
        self.commands = asyncio.Queue()
        self.map_server = None
        self.closing = False

    def show_menu(self, message=''):
        print('\033[2J\033[H', end='')
        print(f'CampusRoute {__version__}  |  iPhone 路线调试')
        print('在家里我们就练起来')
        print(f'路线：{self.route.name}')
        print(f'配速：{pace_label(self.pace_s)}／公里；目标：{self.target_m / 1000:g}公里')
        print('状态：' + (PHASE_NAMES[self.motion.phase] if self.motion else '尚未连接'))
        if self.motion:
            print(f'当前累计距离：{self.motion.distance_m / 1000:.3f}公里；移动用时：{self.motion.elapsed_s:.1f}秒')
        if message:
            print('\n' + message)
        print('\n1  连接手机并准备起点')
        print('2  开始／继续移动')
        print('3  暂停移动')
        print('4  中止本次移动，保持当前位置')
        print('5  恢复真实定位并断开连接')
        print('6  刷新当前状态')
        print('7  选择路线／导入自定义路线')
        print('8  设置配速与目标距离')
        print('9  打开操场地图／绘制自定义路线')
        print('0  恢复真实定位并退出')
        print('\n请选择数字并按回车：', end='', flush=True)

    async def answer(self, prompt):
        print(prompt, end='', flush=True)
        return await self.commands.get()

    async def connect(self):
        devices = await usb_devices()
        if not devices:
            raise RuntimeError('未检测到 USB 设备。请连接数据线、解锁手机，并确认 Finder 能够识别 iPhone。')
        selected = 0
        if len(devices) > 1:
            print('\n检测到多台设备，请选择：')
            for index, device in enumerate(devices, 1):
                print(f'{index}  {await device_label(device.serial)}')
            reply = await self.answer('设备编号（输入0取消）：')
            if reply == '0':
                return False
            if not reply.isdecimal() or not 1 <= int(reply) <= len(devices):
                raise ValueError('设备编号无效。')
            selected = int(reply) - 1
        print('\n正在准备开发者服务，请保持手机连接并解锁……', flush=True)
        self.connection = DeviceConnection()
        await self.connection.connect(devices[selected].serial)
        self.motion = Motion(RoutePath(self.route), self.pace_s, self.target_m)
        await self.tick()
        return True

    async def restore(self):
        if self.connection:
            await self.connection.close()
            self.connection = None
        self.motion = None

    async def select_route(self):
        print('\n内置操场路线：')
        for index, route in enumerate(self.routes, 1):
            print(f'{index}  {route.name}')
        print('I  导入 GPX／GeoJSON；输入0返回菜单。')
        print('自定义方法：菜单9打开地图 → 逐点绘制 → 下载路线 → 在这里导入下载文件。')
        print('坐标要求：WGS84；GeoJSON 使用 [经度, 纬度]；GPX 需要一条连续路线。')
        print('闭合路线循环前进；开放路线沿原路往返。')
        reply = await self.answer('请选择路线编号或输入 I：')
        if reply == '0':
            return '路线设置已关闭。'
        if reply.lower() == 'i':
            raw = await self.answer('请粘贴路线文件的完整路径（输入0取消）：')
            if raw == '0':
                return '路线导入已取消。'
            path = Path(raw.strip().strip("\"'")).expanduser()
            route = read_route(path)
            self.route = route
        elif reply.isdecimal() and 1 <= int(reply) <= len(self.routes):
            self.route = self.routes[int(reply) - 1]
        else:
            raise ValueError('路线编号无效。')
        return f'已选择：{self.route.name}。路线全长约{RoutePath(self.route).length_m:.1f}米。'

    async def configure(self):
        print('\n配速格式为 分钟:秒，最快2:00／公里，慢速没有人为上限。')
        reply = await self.answer(f'配速（直接回车保留{pace_label(self.pace_s)}，输入0取消）：')
        if reply == '0':
            return '设置已取消。'
        pace_s = parse_pace(reply) if reply else self.pace_s
        reply = await self.answer(f'目标公里数（直接回车保留{self.target_m / 1000:g}，输入0取消）：')
        if reply == '0':
            return '设置已取消。'
        target_m = float(reply) * 1000 if reply else self.target_m
        if not math.isfinite(target_m) or target_m <= 0:
            raise ValueError('目标公里数必须为有限的正数。')
        self.pace_s, self.target_m = pace_s, target_m
        return '配速与目标距离已设置。'

    async def choose(self, choice):
        if choice == '0':
            return False, ''
        if choice == '1':
            if self.connection:
                return True, '当前已有连接。准备新的一次移动时，请先选择5。'
            if await self.connect():
                return True, '路线起点已准备。输入2开始移动。'
            return True, '设备选择已取消。'
        if choice == '5':
            had_connection = self.connection is not None
            await self.restore()
            return True, '已发送恢复真实定位指令，连接已关闭。' if had_connection else '当前没有设备连接。'
        if choice == '6':
            return True, '状态已刷新。'
        if choice in ('7', '8', '9'):
            if self.connection:
                return True, '修改路线或参数前，请选择5恢复定位并断开连接。'
            if choice == '7':
                return True, await self.select_route()
            if choice == '8':
                return True, await self.configure()
            displayed = list(self.routes)
            if self.route not in displayed:
                displayed.append(self.route)
            if not self.map_server:
                self.map_server = MapServer(displayed)
            else:
                self.map_server.update_routes(displayed)
            url = f'{self.map_server.url}?route={displayed.index(self.route)}'
            opened = await asyncio.to_thread(webbrowser.open, url)
            return True, (('地图已打开。' if opened else '请在浏览器打开地图。')
                          + f'本地地址：{url}\n绘制并下载路线后，输入7，再输入 I 导入文件。')
        if choice not in ('2', '3', '4'):
            return True, '请输入菜单中的数字。'
        if not self.motion:
            return True, '请先输入1连接手机并准备起点。'
        if choice == '2':
            if self.motion.phase not in ('ready', 'paused'):
                return True, '当前状态无法继续移动。准备新的一次移动时，请先选择5。'
            self.motion.start(time.monotonic())
            return True, '正在移动，输入3暂停，输入4中止。'
        if choice == '3':
            if self.motion.phase != 'running':
                return True, '当前没有正在进行的移动。'
            self.motion.pause(time.monotonic())
            return True, '移动已暂停，当前位置持续保持。输入2继续移动。'
        self.motion.stop(time.monotonic())
        return True, '本次移动已中止，当前位置持续保持。输入5恢复定位，输入0退出。'

    async def tick(self):
        if not self.motion:
            return
        previous = self.motion.phase
        self.motion.advance(time.monotonic())
        await self.connection.set(*self.motion.position)
        if previous != 'finished' and self.motion.phase == 'finished':
            self.show_menu('目标距离已完成，当前位置持续保持。输入5恢复定位，输入0退出。')

    async def run(self):
        loop = asyncio.get_running_loop()
        descriptor = sys.stdin.fileno()

        def receive():
            line = sys.stdin.readline()
            if line == '':
                loop.remove_reader(descriptor)
                request_exit()
            else:
                self.commands.put_nowait(line.strip())

        def request_exit():
            self.closing = True
            self.commands.put_nowait('0')

        loop.add_reader(descriptor, receive)
        for event in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            loop.add_signal_handler(event, request_exit)
        pending = asyncio.create_task(self.commands.get())
        self.show_menu()
        try:
            while True:
                started = time.monotonic()
                await self.tick()
                await asyncio.wait({pending}, timeout=max(0, 0.2 - (time.monotonic() - started)))
                if pending.done():
                    choice = pending.result()
                    # 仅输入校验错误允许重新输入；设备及通信错误直接退出并执行清理。
                    if choice in ('7', '8') and not self.connection:
                        try:
                            keep_running, message = await self.choose(choice)
                        except (ValueError, FileNotFoundError) as error:
                            keep_running, message = True, f'输入无效：{error}'
                    else:
                        keep_running, message = await self.choose(choice)
                    if not keep_running or self.closing:
                        break
                    self.show_menu(message)
                    pending = asyncio.create_task(self.commands.get())
        finally:
            pending.cancel()
            loop.remove_reader(descriptor)
            try:
                had_connection = bool(self.connection and self.connection.simulated)
                await self.restore()
                print('\n已发送恢复真实定位指令，程序已退出。' if had_connection else '\n程序已退出。', flush=True)
            finally:
                if self.map_server:
                    self.map_server.close()


def main():
    parser = argparse.ArgumentParser(description='CampusRoute：iPhone 路线与定位调试工具')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='本地工作文件夹')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('设备控制窗口需要在 macOS 上运行。')
    logging.basicConfig(level=logging.WARNING, force=True)
    try:
        with runtime(args.root):
            asyncio.run(ConsoleApp(args.root).run())
    except AlreadyRunningError as error:
        print(str(error), flush=True)
        return 2
    except Exception as error:
        print(f'\n操作已终止：{type(error).__name__}：{error}', flush=True)
        print('连接中断时，请重新连接设备并执行菜单1、5；必要时重启手机恢复定位。', flush=True)
        return 1
    return 0
