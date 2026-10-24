"""ADB discovery and acknowledged JSON-lines transport to the Android companion."""
import asyncio
import json
import logging
import math
import os
import secrets
import re
import shutil
import sys
import time
from pathlib import Path

from geographiclib.geodesic import Geodesic

from campusroute import __version__
from campusroute.backends import DeviceInfo, InstallationError, SessionError
from campusroute.deadline import wait_for_reply
from campusroute.socketbridge import open_socket_connection

PACKAGE = 'org.campusroute.android'
DEVICE_PORT = 47653
PROTOCOL = 1


class CompanionNotReadyError(SessionError):
    pass


class ReplyTimeoutError(SessionError):
    pass


class LoopProbe:
    def __init__(self):
        self.next_due = time.perf_counter() + 0.1
        self.peak_ms = 0.0

    async def run(self):
        while True:
            await asyncio.sleep(0.1)
            now = time.perf_counter()
            self.peak_ms = max(self.peak_ms, (now - self.next_due) * 1000)
            self.next_due = now + 0.1

    def lag_ms(self):
        return round(max(0, self.peak_ms, (time.perf_counter() - self.next_due) * 1000), 1)


class Adb:
    def __init__(self, executable: str | None = None, root: Path | None = None):
        self.executable = executable
        self.root = root if root is not None else Path.cwd()

    def locate(self):
        if self.executable:
            return self.executable
        local = self.root / 'work' / 'android-sdk' / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')
        if local.is_file():
            self.executable = str(local.resolve())
            return self.executable
        executable = shutil.which('adb')
        if not executable:
            for key in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
                if os.environ.get(key):
                    candidate = Path(os.environ[key]) / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')
                    if candidate.is_file():
                        executable = str(candidate)
                        break
        if not executable:
            raise SessionError('找不到 adb。请安装 Android SDK Platform-Tools 并加入 PATH，或使用 --adb 指定路径。')
        self.executable = executable
        return executable

    async def run(self, *arguments: str, timeout: float = 15):
        try:
            process = await asyncio.create_subprocess_exec(
                self.locate(), *arguments, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                **({'creationflags': 0x08000000} if os.name == 'nt' else {}),
            )
        except OSError as error:
            raise SessionError(f'无法启动 adb：{error}') from error
        try:
            output, errors = await asyncio.wait_for(process.communicate(), timeout)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        if process.returncode:
            detail = errors.decode('utf-8', errors='replace').strip()
            raise SessionError(f'ADB 操作失败：{detail or output.decode("utf-8", errors="replace").strip()}')
        return output.decode('utf-8', errors='replace').strip()


class AndroidBackend:
    name = 'Android'

    def __init__(self, adb: str | None = None, root: Path | None = None):
        self.adb = Adb(adb, root)

    async def devices(self):
        output = await self.adb.run('devices', '-l')
        devices, unavailable = [], []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[0] == 'List' or line.startswith('*'):
                continue
            serial, state = parts[:2]
            if serial.startswith('emulator-') or ':' in serial or serial.endswith('._tcp'):
                continue
            if state != 'device':
                unavailable.append(f'{serial}: {state}')
                continue
            fields = dict(part.split(':', 1) for part in parts[2:] if ':' in part)
            label = fields.get('model', serial).replace('_', ' ')
            devices.append(DeviceInfo(serial, f'{label}（{serial}）'))
        if not devices and unavailable:
            raise SessionError('设备尚未就绪：' + '；'.join(unavailable)
                               + '。请解锁手机、开启 USB 调试，并确认“允许此计算机调试”。')
        return devices

    def connection(self):
        return AndroidConnection(self.adb)

    async def install(self, serial: str, apk: Path):
        if not apk.is_file() or apk.suffix.lower() != '.apk':
            raise ValueError('请选择已构建的 .apk 文件。')
        try:
            result = await self.adb.run('-s', serial, 'install', '-r', str(apk.resolve()), timeout=120)
        except asyncio.TimeoutError as error:
            raise InstallationError('等待 APK 安装确认超时。请解锁手机并检查安装弹窗，然后选择10重试。') from error
        except RuntimeError as error:
            result = str(error)
        else:
            if any(line.strip() == 'Success' for line in result.splitlines()):
                return
        if 'INSTALL_FAILED_ABORTED' in result:
            raise InstallationError(
                '手机取消或拒绝了安装（INSTALL_FAILED_ABORTED）。\n'
                '请保持手机解锁，确认手机上的安装提示，再选择10重试。\n'
                '如果没有弹窗，可将 APK 复制到手机后在文件管理中手动安装，完成后选择1连接。'
            )
        raise InstallationError(f'APK 安装未成功：{result}\n请按手机提示处理后选择10重试。')


class AndroidConnection:
    def __init__(self, adb: Adb):
        self.adb = adb
        self.serial = None
        self.port = None
        self.reader = None
        self.writer = None
        self.simulated = False
        self.last_position = None
        self.last_motion = None
        self.sequence = 0
        self.last_sent_at = None
        self.last_ack = None
        self.peer_version = 'unknown'
        self.client_version = 'unknown'
        self.server_info = {}
        self.reply_timeout_s = 3.0
        self.boundary_recoveries = 0

    async def collect_versions(self):
        # Cache only version/backend fields. Never echo the full server-status,
        # which also contains paths to private ADB pairing keys and logs.
        try:
            output = await self.adb.run('-s', self.serial, 'version', timeout=3)
            found = re.search(r'^Version (\S+)', output, re.MULTILINE)
            self.client_version = found.group(1) if found else 'unknown'
        except (OSError, RuntimeError, asyncio.TimeoutError):
            self.client_version = 'unavailable'
        try:
            output = await self.adb.run('-s', self.serial, 'server-status', timeout=3)
            for line in output.splitlines():
                key, separator, value = line.partition(':')
                if separator and key.strip() in ('version', 'usb_backend'):
                    self.server_info[key.strip()] = value.strip().strip('"')[:100]
        except (OSError, RuntimeError, asyncio.TimeoutError):
            pass

    async def connect(self, serial: str):
        self.serial = serial
        await self.collect_versions()
        installed = await self.adb.run('-s', serial, 'shell', 'pm', 'list', 'packages', PACKAGE)
        if f'package:{PACKAGE}' not in installed.splitlines():
            raise SessionError('手机尚未安装 CampusRoute 配套 APK，请先使用菜单10安装。')
        token = secrets.token_hex(24)
        self.port = int(await self.adb.run('-s', serial, 'forward', 'tcp:0', f'tcp:{DEVICE_PORT}'))
        launched = await self.adb.run('-s', serial, 'shell', 'am', 'start', '-n',
                                     f'{PACKAGE}/.MainActivity', '--es', 'session', token)
        if 'Error:' in launched or 'Exception' in launched:
            raise SessionError(f'无法打开手机端：{launched}')
        print('请在手机中选择 CampusRoute 为模拟位置应用，允许定位权限，再点击“启动接收”。等待最多90秒……', flush=True)
        deadline = asyncio.get_running_loop().time() + 90
        while True:
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    open_socket_connection('127.0.0.1', self.port, limit=8192), timeout=3)
                await self.request('hello', token=token, protocol=PROTOCOL)
                return
            except (OSError, asyncio.TimeoutError, CompanionNotReadyError, ReplyTimeoutError):
                await self.disconnect_socket()
                if asyncio.get_running_loop().time() >= deadline:
                    raise SessionError('连接手机端超时。请打开配套应用、完成授权并启动接收后重试。') from None
                await asyncio.sleep(0.5)
            except BaseException:
                # A rejected/cancelled handshake has not injected a location. Do not send clear
                # to an unauthenticated peer during outer cleanup and hide the original error.
                await self.disconnect_socket()
                raise

    async def request(self, command: str, **values):
        if self.writer is None or self.reader is None:
            raise SessionError('Android 连接尚未建立。')
        self.sequence += 1
        sequence = self.sequence
        request = {'id': sequence, 'command': command, **values}
        started_at = time.perf_counter()
        written_ms = None
        payload = (json.dumps(request, allow_nan=False) + '\n').encode('utf-8')
        probe = LoopProbe()
        probe_task = asyncio.create_task(probe.run())

        async def exchange():
            nonlocal written_ms
            self.writer.write(payload)
            await self.writer.drain()
            written_ms = (time.perf_counter() - started_at) * 1000
            return await self.reader.readline()

        completed_frame = getattr(self.reader, 'completed_frame', None)

        def completed_current_reply():
            return completed_frame() if completed_frame and written_ms is not None else None

        try:
            raw, recovered = await wait_for_reply(
                exchange(), started_at + self.reply_timeout_s,
                completed=completed_current_reply)
            if not raw:
                raise ConnectionError('Android 连接已关闭，请检查手机端状态。')
            try:
                response = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as error:
                raise SessionError('Android 返回了无效数据。') from error
            if not isinstance(response, dict):
                raise SessionError('Android 返回了无效数据。')
            if type(response.get('id')) is not int or response['id'] != sequence:
                raise SessionError(f'Android 回复序号不匹配：指令{command}，期望{sequence}，收到{response.get("id")}。')
        except asyncio.TimeoutError as error:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            loop_lag_ms = probe.lag_ms()
            probe_task.cancel()
            stream = self.writer
            before_close = self.stream_snapshot(stream, started_at)
            # A late reply must never be mistaken for the subsequent clear ACK.
            await self.disconnect_socket()
            after_close = self.stream_snapshot(stream, started_at)
            context = self.timeout_context(command, sequence, len(payload), started_at,
                                           loop_lag_ms, before_close, after_close, values)
            diagnostic = await self.diagnostic_status() if command != 'hello' else ''
            raise ReplyTimeoutError(f'等待 Android 的{command}指令回复超时（{self.reply_timeout_s:g}秒，序号{sequence}）。'
                               '连接已关闭，请在手机点击“停止并恢复”后重新连接。'
                               + f'\n电脑等待耗时：{elapsed_ms:.0f}毫秒；'
                               + (f'本机写入耗时：{written_ms:.0f}毫秒。' if written_ms is not None else '本机写入尚未完成。')
                               + context + diagnostic) from error
        except ValueError as error:
            await self.disconnect_socket()
            raise SessionError('Android 回执超过长度限制或格式无效。') from error
        except BaseException:
            await self.disconnect_socket()
            raise
        finally:
            probe_task.cancel()
            await asyncio.gather(probe_task, return_exceptions=True)
        if response.get('ok') is not True:
            if response.get('code') == 'session_not_ready':
                raise CompanionNotReadyError('请在手机点击启动接收，更新本次会话。')
            raise SessionError('手机端：' + str(response.get('error', '未知错误')))
        if command == 'hello' and response.get('protocol') != PROTOCOL:
            raise SessionError('手机 APK 与电脑端协议版本不兼容，请重新安装配套 APK。')
        if command == 'hello':
            self.peer_version = str(response.get('app_version', 'unknown'))[:40]
        now = time.perf_counter()
        self.boundary_recoveries += int(recovered)
        self.last_ack = {'id': sequence, 'command': command, 'at': now,
                         'round_trip_ms': round((now - started_at) * 1000, 1),
                         'deadline_boundary_recovered': recovered,
                         'apply_ms': response.get('apply_ms') if type(response.get('apply_ms')) in (int, float) else None}
        return response

    @staticmethod
    def stream_snapshot(stream, started_at):
        snapshot = getattr(stream, 'diagnostic_snapshot', None)
        return snapshot(started_at) if snapshot else {'transport': type(stream).__name__}

    def timeout_context(self, command, sequence, payload_bytes, started_at, lag_ms, before, after, values):
        previous = dict(self.last_ack) if self.last_ack else None
        if previous:
            previous['age_ms'] = round((time.perf_counter() - previous.pop('at')) * 1000, 1)
        lines = [
            f'PC diagnostics=4 desktop={__version__} python={sys.version.split()[0]} bits={64 if sys.maxsize > 2**32 else 32} '
            f'platform={sys.platform} loop={type(asyncio.get_running_loop()).__name__}',
            'PC interpreter=' + sys.executable,
            f'PC adb_client={self.client_version} adb_server={self.server_info.get("version", "unknown")} '
            f'usb_backend={self.server_info.get("usb_backend", "unknown")} peer_app={self.peer_version}',
            'PC adb_path=' + str(getattr(self.adb, 'executable', 'unknown')),
            f'PC command={command} id={sequence} payload_bytes={payload_bytes} event_loop_peak_lag_ms={lag_ms}',
            f'PC timeout_policy=perf-counter-ready-first timeout_s={self.reply_timeout_s:g} boundary_recoveries={self.boundary_recoveries}',
            'PC motion_policy=route-velocity-hold-zero',
            'PC request_motion=' + json.dumps({key: values[key] for key in ('speed', 'bearing') if key in values}),
            'PC last_successful_ack=' + json.dumps(previous, ensure_ascii=False),
            'PC before_close=' + json.dumps(before, ensure_ascii=False),
            'PC after_close=' + json.dumps(after, ensure_ascii=False),
        ]
        return '\n电脑收发诊断（时间均相对本条指令开始，单位毫秒；不包含坐标或令牌）：\n' + '\n'.join(lines)

    async def diagnostic_status(self):
        """Read only this service's bounded, coordinate-free debug snapshot via ADB."""
        if self.serial is None:
            return ''
        try:
            async with asyncio.timeout(4):
                output = await self.adb.run('-s', self.serial, 'shell', 'dumpsys', 'activity', 'service',
                                            f'{PACKAGE}/.MockLocationService', timeout=3)
        except (OSError, RuntimeError, asyncio.TimeoutError) as error:
            return '\n手机服务诊断读取失败：' + str(error)[:300]
        lines = [line.strip()[:240] for line in output.splitlines() if line.strip().startswith('CR ')][:32]
        if lines:
            return '\n手机接收端诊断（断开后读取；写回完成不等于电脑已收到）：\n' + '\n'.join(lines)
        if 'No services match' in output:
            return '\n诊断时手机接收服务已不在运行。'
        return '\n未读取到手机线程诊断；请用菜单10更新至诊断版 APK（1.1.2）后重试。'

    async def set_motion(self, latitude: float, longitude: float, *, speed: float, bearing: float):
        """Send the route's velocity, including zero immediately when holding a point."""
        await self.set(latitude, longitude, speed=speed, bearing=bearing)

    async def set(self, latitude: float, longitude: float, *, speed=None, bearing=None):
        if not (math.isfinite(latitude) and math.isfinite(longitude)
                and -90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError('定位坐标无效。')
        now = time.monotonic()
        inferred_speed = inferred_bearing = 0.0
        if self.last_position is not None and self.last_sent_at is not None:
            line = Geodesic.WGS84.Inverse(*self.last_position, latitude, longitude)
            inferred_speed = min(100.0, line['s12'] / max(now - self.last_sent_at, 0.001))
            inferred_bearing = line['azi1'] % 360 if line['s12'] > 0.01 else 0.0
        speed = inferred_speed if speed is None else speed
        bearing = inferred_bearing if bearing is None else bearing
        if not (math.isfinite(speed) and 0 <= speed <= 100
                and math.isfinite(bearing) and 0 <= bearing < 360):
            raise ValueError('定位速度或朝向无效。')
        self.simulated = True
        response = await self.request('set', latitude=latitude, longitude=longitude, speed=speed, bearing=bearing)
        if response.get('latitude') != latitude or response.get('longitude') != longitude:
            raise SessionError('手机端确认的坐标与发送值不一致。')
        self.last_position = (latitude, longitude)
        self.last_motion = (speed, bearing)
        self.last_sent_at = now

    async def disconnect_socket(self):
        if self.writer:
            self.writer.close()
            try:
                await asyncio.wait_for(self.writer.wait_closed(), 1)
            except (OSError, asyncio.TimeoutError):
                pass
        self.reader = self.writer = None

    async def close(self):
        failure = None
        try:
            if self.writer:
                response = await self.request('clear')
                if response.get('cleared') is not True:
                    raise SessionError('手机端未确认移除模拟位置。')
                self.simulated = False
            elif self.simulated:
                raise SessionError('恢复定位未收到确认，请使用手机端“停止并恢复”或重新连接。')
        except Exception as error:
            failure = error
        finally:
            await self.disconnect_socket()
            if self.port is not None:
                try:
                    await self.adb.run('-s', self.serial, 'forward', '--remove', f'tcp:{self.port}')
                except Exception as error:
                    if failure is None:
                        failure = error
                    else:
                        logging.warning('ADB 转发清理失败：%s', error)
                finally:
                    self.port = None
        if failure is not None:
            raise failure
