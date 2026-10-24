import asyncio
import json
import io
import os
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from campusroute.android import AndroidBackend, AndroidConnection, Adb, LoopProbe
from campusroute.backends import InstallationError
from campusroute.socketbridge import open_socket_connection


class FakeAdb:
    def __init__(self, output=''):
        self.output = output
        self.calls = []
    async def run(self, *arguments, **kwargs):
        self.calls.append(arguments)
        return self.output


class AdbLocationTests(unittest.TestCase):
    def test_project_adb_preferred_over_path_but_explicit_choice_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / 'work' / 'android-sdk' / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')
            local.parent.mkdir(parents=True)
            local.touch()
            with patch('campusroute.android.shutil.which', return_value='old-adb') as which:
                self.assertEqual(Adb(root=root).locate(), str(local.resolve()))
                self.assertEqual(Adb('chosen-adb', root).locate(), 'chosen-adb')
                which.assert_not_called()

    def test_path_remains_fallback_without_project_adb(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('campusroute.android.shutil.which', return_value='path-adb'):
                self.assertEqual(Adb(root=Path(directory)).locate(), 'path-adb')


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_version_context_excludes_unrelated_server_fields(self):
        connection = AndroidConnection(FakeAdb())
        connection.serial = 'USB123'
        connection.adb.run = AsyncMock(side_effect=[
            'Android Debug Bridge version 1.0.41\nVersion 37.0.1-build\n',
            'version: "37.0.1"\nusb_backend: LIBADBUSB\nkeystore_path: private-key\nlog_absolute_path: private-log',
        ])
        await connection.collect_versions()
        self.assertEqual(connection.client_version, '37.0.1-build')
        self.assertEqual(connection.server_info, {'version': '37.0.1', 'usb_backend': 'LIBADBUSB'})

    async def test_loop_probe_records_event_loop_stall(self):
        probe = LoopProbe()
        monitor = asyncio.create_task(probe.run())
        try:
            await asyncio.sleep(0.01)
            time.sleep(0.14)
            self.assertGreater(probe.lag_ms(), 25)
        finally:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)

    async def test_device_selection_ignores_network_and_emulator(self):
        backend = AndroidBackend()
        backend.adb = FakeAdb('List of devices attached\n'
            'USB123 device product:phone model:Test_Phone transport_id:1\n'
            'USB456 unauthorized\n'
            'emulator-5554 device model:Emulator\n'
            '192.168.0.1:5555 device model:Network\n')
        devices = await backend.devices()
        self.assertEqual([item.serial for item in devices], ['USB123'])
        self.assertIn('Test Phone', devices[0].label)

    async def test_unauthorized_device_has_actionable_error(self):
        backend = AndroidBackend()
        backend.adb = FakeAdb('List of devices attached\nUSB123 unauthorized\n')
        with self.assertRaisesRegex(RuntimeError, 'USB 调试'):
            await backend.devices()

    async def test_install_missing_apk_never_calls_adb(self):
        backend = AndroidBackend()
        backend.adb = FakeAdb()
        with self.assertRaises(ValueError):
            await backend.install('USB123', Path('missing.apk'))
        self.assertFalse(backend.adb.calls)

    async def test_install_rejection_has_retry_instructions(self):
        detail = 'Failure [INSTALL_FAILED_ABORTED: User rejected permissions]'
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / 'test.apk'
            apk.touch()
            for failed_exit in (True, False):
                with self.subTest(failed_exit=failed_exit):
                    backend = AndroidBackend()
                    backend.adb.run = AsyncMock(side_effect=RuntimeError(detail)) if failed_exit else AsyncMock(return_value=detail)
                    with self.assertRaises(InstallationError) as caught:
                        await backend.install('USB123', apk)
                    self.assertIn('INSTALL_FAILED_ABORTED', str(caught.exception))
                    self.assertIn('手机解锁', str(caught.exception))
                    self.assertIn('选择10重试', str(caught.exception))
                    self.assertEqual(backend.adb.run.await_count, 1)

    async def test_install_timeout_is_recoverable(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / 'test.apk'
            apk.touch()
            backend = AndroidBackend()
            backend.adb.run = AsyncMock(side_effect=asyncio.TimeoutError)
            with self.assertRaisesRegex(InstallationError, '超时'):
                await backend.install('USB123', apk)

    async def test_install_success_requires_explicit_success_line(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / 'test.apk'
            apk.touch()
            backend = AndroidBackend()
            backend.adb.run = AsyncMock(return_value='Performing Streamed Install\nSuccess')
            await backend.install('USB123', apk)
            backend.adb.run.assert_awaited_once()
            backend.adb.run = AsyncMock(return_value='Success was not reported by the installer')
            with self.assertRaises(InstallationError):
                await backend.install('USB123', apk)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.messages = []
        self.tasks = set()
        self.bad_sequence = False
        self.bad_coordinates = False
        self.deny_clear = False
        self.drop_set = False
        self.stale_hellos = 0
        self.reply_delay = 0
        self.partial_reply = False
        self.server = await asyncio.start_server(self.accept, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.adb = FakeAdb()
        self.connection = AndroidConnection(self.adb)
        self.connection.serial = 'USB123'
        self.connection.port = self.port
        self.connection.reader, self.connection.writer = await asyncio.open_connection('127.0.0.1', self.port)

    async def accept(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            while raw := await reader.readline():
                request = json.loads(raw)
                self.messages.append(request)
                command = request['command']
                response = {'id': request['id'] + (1 if self.bad_sequence else 0), 'ok': True, 'protocol': 1}
                if command == 'hello' and self.stale_hellos:
                    self.stale_hellos -= 1
                    response.update(ok=False, code='session_not_ready', error='restart receiver')
                if command == 'set':
                    if self.reply_delay:
                        await asyncio.sleep(self.reply_delay)
                    if self.drop_set:
                        break
                    response.update(latitude=request['latitude'], longitude=request['longitude'])
                    if self.bad_coordinates:
                        response['latitude'] += 1
                if command == 'clear':
                    response['cleared'] = not self.deny_clear
                if self.partial_reply:
                    writer.write(b'{"id":')
                    await writer.drain()
                    await reader.read()
                    return
                writer.write((json.dumps(response) + '\n').encode())
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            self.tasks.discard(task)

    async def asyncTearDown(self):
        await self.connection.disconnect_socket()
        self.server.close()
        await self.server.wait_closed()
        if self.tasks:
            await asyncio.gather(*self.tasks)

    async def test_acknowledged_location_and_cleanup(self):
        await self.connection.request('hello', token='test', protocol=1)
        await self.connection.set(31.3, 121.5)
        self.assertTrue(self.connection.simulated)
        self.assertEqual(self.connection.last_position, (31.3, 121.5))
        await self.connection.close()
        self.assertFalse(self.connection.simulated)
        self.assertIsNone(self.connection.port)
        self.assertEqual([m['command'] for m in self.messages], ['hello', 'set', 'clear'])
        self.assertEqual(self.adb.calls[-1], ('-s', 'USB123', 'forward', '--remove', f'tcp:{self.port}'))

    async def test_connect_uses_selected_usb_device_and_session(self):
        await self.connection.disconnect_socket()
        self.stale_hellos = 1
        port = self.port
        class ConnectedAdb(FakeAdb):
            async def run(self, *arguments, **kwargs):
                self.calls.append(arguments)
                if arguments[2:5] == ('shell', 'pm', 'list'):
                    return 'package:org.campusroute.android'
                if arguments[2:4] == ('forward', 'tcp:0'):
                    return str(port)
                return 'Starting: Intent'
        self.connection = AndroidConnection(ConnectedAdb())
        with patch('sys.stdout', io.StringIO()):
            await self.connection.connect('USB123')
        self.assertEqual(self.messages[0]['command'], 'hello')
        self.assertEqual(len(self.messages), 2)
        self.assertEqual(self.messages[0]['token'], self.messages[1]['token'])
        self.assertRegex(self.messages[0]['token'], r'^[0-9a-f]{48}$')
        self.assertTrue(all(call[:2] == ('-s', 'USB123') for call in self.connection.adb.calls))
        await self.connection.close()

    async def test_cleanup_preserves_primary_error_when_adb_also_fails(self):
        await self.connection.set(31.3, 121.5)
        self.deny_clear = True
        class BrokenAdb(FakeAdb):
            async def run(self, *arguments, **kwargs):
                raise RuntimeError('device offline')
        self.connection.adb = BrokenAdb()
        with self.assertLogs(level='WARNING'), self.assertRaisesRegex(RuntimeError, '未确认'):
            await self.connection.close()

    async def test_wrong_ack_sequence_rejected(self):
        self.bad_sequence = True
        with self.assertRaisesRegex(RuntimeError, '序号'):
            await self.connection.set(31.3, 121.5)
        self.assertTrue(self.connection.simulated)

    async def test_late_reply_cannot_be_consumed_as_cleanup_ack(self):
        self.reply_delay = 0.08
        self.adb.output = 'unrelated private data\n  CR received_id=1 replied_id=0\n  CR phase=applying_gps phase_ms=3000'
        with patch.object(self.connection, 'reply_timeout_s', 0.03):
            with self.assertRaisesRegex(RuntimeError, '等待 Android.*set.*超时') as caught:
                await self.connection.set(31.3, 121.5)
        self.assertIn('phase=applying_gps', str(caught.exception))
        self.assertIn('PC diagnostics=4', str(caught.exception))
        self.assertIn('PC request_motion={"speed": 0.0, "bearing": 0.0}', str(caught.exception))
        self.assertIn('event_loop_peak_lag_ms=', str(caught.exception))
        self.assertNotIn('private data', str(caught.exception))
        self.assertIsNone(self.connection.writer)
        with self.assertRaisesRegex(RuntimeError, '恢复定位未收到确认'):
            await self.connection.close()
        self.assertEqual([message['command'] for message in self.messages], ['set'])

    async def test_diagnostic_failure_preserves_original_reply_timeout(self):
        self.reply_delay = 0.08
        self.adb.run = AsyncMock(side_effect=RuntimeError('device offline'))
        with patch.object(self.connection, 'reply_timeout_s', 0.03):
            with self.assertRaisesRegex(RuntimeError, '等待 Android.*set.*超时') as caught:
                await self.connection.set(31.3, 121.5)
        self.assertIn('device offline', str(caught.exception))
        self.assertIsNone(self.connection.writer)

    async def test_diagnostic_dump_is_scoped_and_bounded(self):
        self.adb.output = 'hidden token\n' + '\n'.join('  CR ' + 'x' * 500 for _ in range(100))
        result = await self.connection.diagnostic_status()
        self.assertNotIn('hidden token', result)
        self.assertEqual(len(result.splitlines()), 34)
        self.assertLess(len(result), 8000)
        self.assertEqual(self.adb.calls[-1], ('-s', 'USB123', 'shell', 'dumpsys', 'activity', 'service',
                                             'org.campusroute.android/.MockLocationService'))

    async def test_diagnostic_distinguishes_missing_service_from_old_apk(self):
        self.adb.output = 'No services match: org.campusroute.android/.MockLocationService'
        self.assertIn('已不在运行', await self.connection.diagnostic_status())
        self.adb.output = 'SERVICE org.campusroute.android/.MockLocationService'
        self.assertIn('更新至诊断版', await self.connection.diagnostic_status())

    async def test_wrong_ack_reports_expected_and_received_ids(self):
        self.bad_sequence = True
        with self.assertRaisesRegex(RuntimeError, 'set.*期望1.*收到2'):
            await self.connection.set(31.3, 121.5)
        self.assertIsNone(self.connection.writer)

    async def test_wrong_ack_coordinates_rejected(self):
        self.bad_coordinates = True
        with self.assertRaisesRegex(RuntimeError, '坐标'):
            await self.connection.set(31.3, 121.5)
        self.assertIsNone(self.connection.last_position)

    async def test_cleanup_failure_not_reported_as_success(self):
        await self.connection.set(31.3, 121.5)
        self.deny_clear = True
        with self.assertRaisesRegex(RuntimeError, '未确认'):
            await self.connection.close()
        self.assertTrue(self.connection.simulated)
        self.assertIsNone(self.connection.writer)
        self.assertIsNone(self.connection.port)

    async def test_dropped_ack_still_marks_possible_injection(self):
        self.drop_set = True
        with self.assertRaises(ConnectionError):
            await self.connection.set(31.3, 121.5)
        self.assertTrue(self.connection.simulated)

    async def test_invalid_location_never_sent(self):
        with self.assertRaises(ValueError):
            await self.connection.set(float('nan'), 121.5)
        self.assertFalse(self.messages)

    async def test_stationary_speed_is_zero(self):
        await self.connection.set(31.3, 121.5)
        await self.connection.set(31.3, 121.5)
        self.assertEqual(self.messages[-1]['speed'], 0)

    async def test_explicit_velocity_overrides_displacement_inference(self):
        await self.connection.set_motion(31.3, 121.5, speed=8.33, bearing=179)
        await self.connection.set_motion(31.3001, 121.5, speed=0, bearing=0)
        self.assertEqual((self.messages[0]['speed'], self.messages[0]['bearing']), (8.33, 179))
        self.assertEqual((self.messages[1]['speed'], self.messages[1]['bearing']), (0, 0))
        self.assertEqual(self.connection.last_motion, (0, 0))

    async def test_invalid_velocity_never_sent(self):
        for speed, bearing in ((float('nan'), 0), (-1, 0), (101, 0), (0, float('inf')), (0, 360)):
            with self.subTest(speed=speed, bearing=bearing), self.assertRaises(ValueError):
                await self.connection.set_motion(31.3, 121.5, speed=speed, bearing=bearing)
        self.assertFalse(self.messages)
        self.assertFalse(self.connection.simulated)


class ThreadedTransportTests(TransportTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.connection.disconnect_socket()
        self.connection.reader, self.connection.writer = await open_socket_connection('127.0.0.1', self.port)

    async def test_cancelled_read_closes_socket_instead_of_leaving_worker_blocked(self):
        self.reply_delay = 0.1
        operation = asyncio.create_task(self.connection.set(31.3, 121.5))
        while not self.messages:
            await asyncio.sleep(0)
        operation.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(operation, 1)
        self.assertIsNone(self.connection.writer)
        self.assertTrue(self.connection.simulated)

    async def test_timeout_report_identifies_partial_frame_without_exposing_contents(self):
        self.partial_reply = True
        with patch.object(self.connection, 'reply_timeout_s', 0.05):
            with self.assertRaisesRegex(RuntimeError, '等待 Android.*超时') as caught:
                await self.connection.set(31.3, 121.5)
        lines = str(caught.exception).splitlines()
        before = json.loads(next(line.removeprefix('PC before_close=') for line in lines if line.startswith('PC before_close=')))
        after = json.loads(next(line.removeprefix('PC after_close=') for line in lines if line.startswith('PC after_close=')))
        self.assertEqual(before['transport'], 'threaded-socket-v3')
        self.assertEqual(before['read']['bytes'], len(b'{"id":'))
        self.assertFalse(before['read']['newline'])
        self.assertTrue(before['read_active'])
        self.assertTrue(after['closed'])
        self.assertFalse(after['read_active'])
        self.assertNotIn('31.3', str(caught.exception))
        self.assertNotIn('121.5', str(caught.exception))


class BoundaryReplyTests(unittest.IsolatedAsyncioTestCase):
    async def check_boundary_reply(self, wrong_id=False, wrong_coordinates=False):
        """A worker completes but its coroutine notification misses the deadline."""
        class Stream:
            closed = False
            frame = None
            def write(self, payload):
                command = json.loads(payload)
                response = {'id': command['id'] + int(wrong_id), 'ok': True,
                            'latitude': command['latitude'] + int(wrong_coordinates),
                            'longitude': command['longitude']}
                self.frame = (json.dumps(response).encode() + b'\n', time.perf_counter())
            async def drain(self):
                pass
            async def readline(self):
                await asyncio.Event().wait()
            def completed_frame(self):
                return self.frame
            def close(self):
                self.closed = True
            async def wait_closed(self):
                pass
        connection = AndroidConnection(FakeAdb())
        connection.reader = connection.writer = Stream()
        connection.reply_timeout_s = 0.02
        if wrong_id or wrong_coordinates:
            with self.assertRaisesRegex(RuntimeError, '序号' if wrong_id else '坐标'):
                await connection.set(31.3, 121.5)
            self.assertIsNone(connection.last_position)
        else:
            await connection.set(31.3, 121.5)
            self.assertEqual(connection.last_position, (31.3, 121.5))
            self.assertEqual(connection.boundary_recoveries, 1)
            self.assertTrue(connection.last_ack['deadline_boundary_recovered'])
            self.assertFalse(connection.writer.closed)

    async def test_complete_on_time_frame_survives_queued_future_notification(self):
        await self.check_boundary_reply()

    async def test_recovered_reply_still_requires_matching_sequence(self):
        await self.check_boundary_reply(wrong_id=True)

    async def test_recovered_reply_still_requires_matching_coordinates(self):
        await self.check_boundary_reply(wrong_coordinates=True)


if __name__ == '__main__':
    unittest.main()
