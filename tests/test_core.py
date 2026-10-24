import asyncio
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from urllib.request import urlopen

from campusroute.backends import DeviceInfo, InstallationError, get_backend
from campusroute.android import ReplyTimeoutError
from campusroute.console import ConsoleApp
from campusroute.mapserver import MapServer
from campusroute.motion import Motion, parse_pace
from campusroute.routes import RoutePath, pending_venues, presets, read_route
from campusroute.runtime import AlreadyRunningError, instance_lock, runtime
from campusroute.variation import Variation

ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def test_sufe_preset_preserves_generated_route_provenance(self):
        route = next(item for item in presets() if item.properties['id'] == 'sufe-wudong')
        self.assertTrue(route.closed)
        self.assertEqual(len(route.coordinates), 209)
        self.assertTrue(route.properties['estimated'])
        self.assertEqual(route.properties['generator'], 'football_pitch_stadium_v1')
        self.assertEqual(route.properties['source_file'], 'custom-route.geojson')
        self.assertEqual(len(route.properties['football_corners']), 4)
        self.assertAlmostEqual(RoutePath(route).length_m, 412.444, delta=0.001)
        self.assertNotIn('sufe-wudong', [item['id'] for item in pending_venues()])

    def test_presets_and_round_trip(self):
        routes = presets()
        self.assertGreaterEqual(len(routes), 7)
        self.assertEqual(len({route.properties['id'] for route in routes}), len(routes))
        self.assertEqual(len({route.properties['order'] for route in routes}), len(routes))
        with tempfile.TemporaryDirectory() as directory:
            for route in routes:
                path = RoutePath(route)
                self.assertTrue(route.closed)
                self.assertGreater(path.length_m, 100)
                self.assertLess(path.length_m, 1000)
                self.assertEqual(route.properties['coordinate_system'], 'WGS84')
                source_url = route.properties.get('source_url')
                self.assertTrue(source_url or route.properties.get('source_file'))
                if source_url:
                    self.assertTrue(source_url.startswith('https://'))
                file = Path(directory) / 'route.geojson'
                file.write_text(json.dumps(route.feature()), encoding='utf-8')
                restored = read_route(file)
                self.assertEqual(restored.coordinates, route.coordinates)
                self.assertAlmostEqual(RoutePath(restored).length_m, path.length_m)

    def test_motion_pause_resume_and_finish(self):
        motion = Motion(RoutePath(presets()[0]), parse_pace('6:00'), 1000)
        motion.start(0)
        motion.advance(180)
        self.assertAlmostEqual(motion.distance_m, 500)
        motion.pause(180)
        motion.advance(360)
        self.assertAlmostEqual(motion.distance_m, 500)
        motion.start(360)
        motion.advance(540)
        self.assertEqual(motion.phase, 'finished')
        self.assertAlmostEqual(motion.distance_m, 1000)
        self.assertAlmostEqual(motion.elapsed_s, 360)

    def test_hold_does_not_advance_over_delayed_ack_and_resume_excludes_wait(self):
        for operation in ('pause', 'stop'):
            with self.subTest(operation=operation):
                motion = Motion(RoutePath(presets()[0]))
                motion.start(0)
                motion.advance(1)
                position = motion.position
                distance = motion.distance_m
                self.assertAlmostEqual(motion.velocity[0], 1000 / 120)
                getattr(motion, operation)(4)
                motion.advance(20)
                self.assertEqual(motion.position, position)
                self.assertEqual(motion.distance_m, distance)
                self.assertEqual(motion.velocity, (0, 0))
                if operation == 'pause':
                    motion.start(21)
                    motion.advance(22)
                    self.assertAlmostEqual(motion.distance_m, 2 * distance)

    def test_lock_released_and_temporary_environment_restored(self):
        before = {key: os.environ.get(key) for key in ('TMPDIR', 'TEMP', 'TMP')}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with runtime(root):
                temporary = Path(tempfile.gettempdir())
                self.assertTrue(temporary.is_relative_to(root))
                with self.assertRaises(AlreadyRunningError):
                    with instance_lock(root):
                        pass
            self.assertFalse(temporary.exists())
            with instance_lock(root):
                pass
        self.assertEqual(before, {key: os.environ.get(key) for key in before})

    def test_map_server_assets_and_payload(self):
        server = MapServer(presets())
        try:
            with urlopen(server.url + 'routes.json', timeout=3) as response:
                collection = json.load(response)
                self.assertEqual(len(collection['features']), len(presets()))
            with urlopen(server.url, timeout=3) as response:
                self.assertIn('viewport', response.read().decode('utf-8'))
                self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
        finally:
            server.close()

    def test_android_import_does_not_load_ios(self):
        result = subprocess.run([sys.executable, '-B', '-c',
            'import sys; from campusroute.backends import get_backend; '
            'get_backend("android"); assert "pymobiledevice3" not in sys.modules; '
            'import campusroute.console'], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_cli_starts_and_exits_on_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', '-m', 'campusroute', '--backend', 'android',
                '--root', directory], input='0\n', text=True, encoding='utf-8', capture_output=True,
                timeout=15, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Android', result.stdout)


class ConsoleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    async def test_variation_menu_persists_and_is_passed_to_new_motion(self):
        app = ConsoleApp(self.root)
        app.pace_s = 360
        for reply in ('1', '7.5', '0.8'):
            app.commands.put_nowait(reply)
        with patch('sys.stdout', io.StringIO()):
            keep, message = await app.choose('11')
        self.assertTrue(keep)
        self.assertIn('7.5%', message.replace('％', '%'))
        self.assertEqual(app.variation, Variation(True, 7.5, 0.8))
        restored = ConsoleApp(self.root)
        self.assertEqual(restored.variation, app.variation)
        connection = type('Connection', (), {'connect': AsyncMock(), 'set_motion': AsyncMock()})()
        restored.backend.devices = AsyncMock(return_value=[DeviceInfo('USB123', 'test')])
        restored.backend.connection = lambda: connection
        with patch('sys.stdout', io.StringIO()):
            await restored.connect()
        self.assertEqual(restored.motion.variation, app.variation)
        connection.set_motion.assert_awaited_once_with(*restored.motion.position, speed=0, bearing=0)
        self.assertIn('静止', '\n'.join(restored.status_lines()))
        keep, message = await restored.choose('11')
        self.assertTrue(keep)
        self.assertIn('选择5', message)

    async def test_variation_invalid_input_returns_to_menu_without_saving(self):
        app = ConsoleApp(self.root)
        with patch('sys.stdin', io.StringIO('11\n1\nnan\n0.6\n6\n0\n')), \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            await app.run()
        self.assertEqual(app.variation, Variation())
        self.assertIn('输入无效', output.getvalue())
        self.assertIn('状态已刷新', output.getvalue())
        self.assertFalse(app.settings_store.path.exists())

    async def test_variation_cancel_disable_and_zero_amplitudes(self):
        app = ConsoleApp(self.root)
        app.variation = Variation(True, 7, 0.8)
        app.save_settings()
        before = app.settings_store.path.read_bytes()
        for reply in ('1', '10', 'q'):
            app.commands.put_nowait(reply)
        with patch('sys.stdout', io.StringIO()):
            await app.choose('11')
        self.assertEqual(app.settings_store.path.read_bytes(), before)
        app.commands.put_nowait('2')
        with patch('sys.stdout', io.StringIO()):
            await app.choose('11')
        self.assertEqual(app.variation, Variation(False, 7, 0.8))
        for reply in ('1', '0', '0'):
            app.commands.put_nowait(reply)
        with patch('sys.stdout', io.StringIO()):
            await app.choose('11')
        self.assertEqual(app.variation, Variation(True, 0, 0))

    async def test_install_rejection_keeps_console_usable(self):
        app = ConsoleApp(self.root)
        app.backend.devices = AsyncMock(return_value=[DeviceInfo('USB123', 'test')])
        app.backend.install = AsyncMock(side_effect=InstallationError('手机拒绝安装，请选择10重试。'))
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO('10\n\n6\n0\n')), patch('sys.stdout', output):
            await app.run()
        app.backend.install.assert_awaited_once()
        self.assertIn('手机拒绝安装', output.getvalue())
        self.assertIn('状态已刷新', output.getvalue())
        self.assertNotIn('操作已终止', output.getvalue())
        self.assertIsNone(app.connection)

    async def test_cancel_during_connection_still_restores(self):
        started = asyncio.Event()
        class Connection:
            simulated = False
            closed = False
            async def connect(self, serial):
                started.set()
                await asyncio.Event().wait()
            async def close(self):
                self.closed = True
        class Backend:
            name = 'test'
            def connection(self):
                return connection
            async def devices(self):
                from campusroute.backends import DeviceInfo
                return [DeviceInfo('USB123', 'test')]
        connection = Connection()
        app = ConsoleApp(self.root)
        app.backend = Backend()
        with patch('sys.stdin', io.StringIO('1\n')), patch('sys.stdout', io.StringIO()):
            task = asyncio.create_task(app.run())
            await asyncio.wait_for(started.wait(), 2)
            app.closing = True
            task.cancel()
            await asyncio.wait_for(task, 2)
        self.assertTrue(connection.closed)

    async def test_menu_route_selection_without_adb(self):
        app = ConsoleApp(self.root, 'android', 'missing-adb')
        app.commands.put_nowait(str(len(app.routes)))
        with patch('sys.stdout', io.StringIO()):
            keep, message = await app.choose('7')
        self.assertTrue(keep)
        self.assertEqual(app.route, app.routes[-1])
        self.assertIn(app.route.name, message)

    async def test_cleanup_when_initial_tick_fails(self):
        class Connection:
            simulated = True
            closed = False
            async def set(self, *position):
                raise ConnectionError('lost')
            async def close(self):
                self.closed = True
        app = ConsoleApp(self.root)
        connection = Connection()
        app.connection = connection
        app.motion = Motion(RoutePath(app.route))
        with patch('sys.stdin', io.StringIO('6\n0\n')), patch('sys.stdout', new_callable=io.StringIO) as output:
            await app.run()
        self.assertTrue(connection.closed)
        self.assertIsNone(app.connection)
        self.assertIsNone(app.motion)
        self.assertIn('ConnectionError：lost', output.getvalue())
        self.assertIn('状态已刷新', output.getvalue())

    async def test_timeout_and_failed_cleanup_keep_menu_and_allow_fresh_connection(self):
        class BrokenConnection:
            simulated = True
            async def set(self, *position):
                raise ReplyTimeoutError('原始超时\nPC diagnostic detail\nCR diagnostic detail')
            async def close(self):
                raise RuntimeError('恢复定位未收到确认')
        class FreshConnection:
            simulated = False
            connect = AsyncMock()
            set_motion = AsyncMock()
            close = AsyncMock()
        app = ConsoleApp(self.root)
        original_route, original_pace, original_target = app.route, app.pace_s, app.target_m
        app.connection = BrokenConnection()
        app.motion = Motion(RoutePath(app.route))
        fresh = FreshConnection()
        app.backend.devices = AsyncMock(return_value=[DeviceInfo('USB123', 'test')])
        app.backend.connection = lambda: fresh
        with patch('sys.stdin', io.StringIO('6\n1\n6\n0\n')), patch('sys.stdout', new_callable=io.StringIO) as output:
            await app.run()
        text = output.getvalue()
        for expected in ('原始超时', 'PC diagnostic detail', 'CR diagnostic detail',
                         '清理未确认', '电脑端仍在运行', '路线起点已准备'):
            self.assertIn(expected, text)
        self.assertNotIn('操作已终止', text)
        fresh.connect.assert_awaited_once_with('USB123')
        fresh.close.assert_awaited_once()
        self.assertTrue(fresh.set_motion.await_args_list)
        self.assertTrue(all(call.kwargs['speed'] == 0 for call in fresh.set_motion.await_args_list))
        self.assertEqual((app.route, app.pace_s, app.target_m), (original_route, original_pace, original_target))

    async def test_pause_and_stop_send_zero_at_last_point_before_reporting_success(self):
        for choice in ('3', '4'):
            with self.subTest(choice=choice):
                app = ConsoleApp(self.root)
                entered, release = asyncio.Event(), asyncio.Event()
                async def send(*position, **velocity):
                    entered.set()
                    await release.wait()
                app.connection = type('Connection', (), {'set_motion': AsyncMock(side_effect=send)})()
                app.motion = Motion(RoutePath(app.route))
                app.motion.start(0)
                app.motion.advance(1)
                last_position = app.motion.position
                with patch('campusroute.console.time', SimpleNamespace(monotonic=lambda: 4)):
                    operation = asyncio.create_task(app.choose(choice))
                    await asyncio.wait_for(entered.wait(), 1)
                    self.assertFalse(operation.done())
                    app.connection.set_motion.assert_awaited_once_with(*last_position, speed=0, bearing=0)
                    release.set()
                    keep, message = await asyncio.wait_for(operation, 1)
                self.assertTrue(keep)
                self.assertIn('持续保持', message)
                self.assertEqual(app.motion.position, last_position)

    async def test_target_completion_sends_zero_velocity(self):
        app = ConsoleApp(self.root)
        app.connection = type('Connection', (), {'set_motion': AsyncMock()})()
        app.motion = Motion(RoutePath(app.route), target_m=1)
        app.motion.start(0)
        with patch('campusroute.console.time.monotonic', return_value=1), patch('sys.stdout', io.StringIO()):
            await app.tick()
        self.assertEqual(app.motion.phase, 'finished')
        app.connection.set_motion.assert_awaited_once_with(*app.motion.position, speed=0, bearing=0)

    async def test_stop_queued_during_ack_precedes_next_moving_update(self):
        app = ConsoleApp(self.root)
        speeds = []
        class Connection:
            simulated = True
            async def set_motion(self, *position, speed, bearing):
                speeds.append(speed)
                app.commands.put_nowait('4' if speed else '0')
                # A menu command arrives while the location ACK is in flight.
                await asyncio.sleep(0)
            async def close(self):
                pass
        app.connection = Connection()
        app.motion = Motion(RoutePath(app.route))
        app.motion.start(0)
        with patch('campusroute.console.time', SimpleNamespace(monotonic=lambda: 1)), \
             patch('campusroute.console.threading.Thread'), patch('sys.stdout', io.StringIO()):
            await asyncio.wait_for(app.run(), 2)
        self.assertEqual(sum(speed > 0 for speed in speeds), 1)
        self.assertEqual(speeds[1], 0)

    async def test_cleanup_failure_does_not_hide_initial_transport_error(self):
        class Connection:
            simulated = True
            async def set(self, *position):
                raise RuntimeError('原始位置回执超时')
            async def close(self):
                raise RuntimeError('Android 回复序号不匹配。')
        app = ConsoleApp(self.root)
        app.connection = Connection()
        app.motion = Motion(RoutePath(app.route))
        with patch('sys.stdin', io.StringIO('')), patch('sys.stdout', new_callable=io.StringIO) as output:
            with self.assertRaisesRegex(RuntimeError, '原始位置回执超时'):
                await app.run()
        self.assertIn('清理时另有错误', output.getvalue())
        self.assertNotIn('程序已退出', output.getvalue())

    async def test_live_progress_updates_after_ack_without_redrawing_input(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True
        class Connection:
            last_position = None
            async def set(self, *position):
                self.last_position = position
        app = ConsoleApp(self.root)
        app.connection = Connection()
        app.motion = Motion(RoutePath(app.route))
        app.motion.start(0)
        output = Terminal()
        with patch('sys.stdout', output), patch('campusroute.console.time.monotonic', return_value=0):
            app.show_menu()
        output.seek(0)
        output.truncate()
        with patch('sys.stdout', output), patch('campusroute.console.time.monotonic', return_value=12):
            await app.tick()
            first = output.getvalue()
            await app.tick()
        self.assertIn('0.100公里', first)
        self.assertIn('12.0秒', first)
        self.assertIn('手机已确认坐标', first)
        self.assertIn('\033[s\033[5;1H', first)
        self.assertTrue(first.endswith('\033[u'))
        self.assertNotIn('请选择', first)
        self.assertEqual(output.getvalue(), first)
        app.motion.pause(12)
        with patch('sys.stdout', output), patch('campusroute.console.time.monotonic', return_value=14):
            await app.tick()
        self.assertIn('移动已暂停', output.getvalue())
        self.assertEqual(app.motion.distance_m, 100)

    async def test_failed_position_ack_does_not_refresh_live_progress(self):
        app = ConsoleApp(self.root)
        app.connection = type('Connection', (), {'set': AsyncMock(side_effect=ConnectionError('lost'))})()
        app.motion = Motion(RoutePath(app.route))
        with patch.object(app, 'refresh_status') as refresh:
            with self.assertRaises(ConnectionError):
                await app.tick()
        refresh.assert_not_called()

    async def test_preferences_survive_restart_and_custom_source_removal(self):
        app = ConsoleApp(self.root)
        source = self.root / '自定义路线.geojson'
        feature = app.routes[-1].feature()
        feature['properties']['name'] = '我的操场'
        source.write_text(json.dumps(feature), encoding='utf-8')
        with patch('sys.stdin', io.StringIO(f'7\nI\n{source}\n8\n6:30\n3.25\n0\n')), patch('sys.stdout', io.StringIO()):
            await app.run()
        source.unlink()
        restored = ConsoleApp(self.root)
        self.assertEqual(restored.route.name, '我的操场')
        self.assertEqual(restored.route.coordinates, app.route.coordinates)
        self.assertEqual(restored.route.properties, app.route.properties)
        self.assertEqual(restored.pace_s, 390)
        self.assertEqual(restored.target_m, 3250)
        self.assertIsNone(restored.motion)
        self.assertIsNone(restored.connection)

    async def test_cancelled_or_invalid_configuration_keeps_saved_preferences(self):
        app = ConsoleApp(self.root)
        app.commands.put_nowait(str(len(app.routes)))
        with patch('sys.stdout', io.StringIO()):
            await app.choose('7')
            before = app.settings_store.path.read_bytes()
            for pace, target in [('6:00', '0'), ('6:00', 'nan')]:
                app.commands.put_nowait(pace)
                app.commands.put_nowait(target)
                if target == 'nan':
                    with self.assertRaises(ValueError):
                        await app.configure()
                else:
                    await app.configure()
                self.assertEqual(app.settings_store.path.read_bytes(), before)
        self.assertEqual(app.pace_s, 120)
        self.assertEqual(ConsoleApp(self.root).route, app.routes[-1])

    async def test_saving_failure_keeps_console_usable_and_reports_unsaved_settings(self):
        app = ConsoleApp(self.root)
        with patch.object(app.settings_store, 'save', side_effect=OSError('read only')):
            with patch('sys.stdin', io.StringIO('8\n6:00\n3\n6\n0\n')), patch('sys.stdout', new_callable=io.StringIO) as output:
                await app.run()
        self.assertIn('无法保存', output.getvalue())
        self.assertIn('状态已刷新', output.getvalue())
        self.assertEqual(app.pace_s, 360)
        self.assertEqual(app.target_m, 3000)


if __name__ == '__main__':
    unittest.main()
