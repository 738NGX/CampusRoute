import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from campusroute.runtime import AlreadyRunningError, instance_lock, runtime
from support import run_console

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'work' / '.cache'
HAS_IOS = importlib.util.find_spec('pymobiledevice3') is not None


class StartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CACHE.mkdir(parents=True, exist_ok=True)

    def run_console(self, commands, backend='android'):
        with tempfile.TemporaryDirectory(prefix='startup-', dir=CACHE) as directory:
            result = run_console(Path(directory), commands, backend)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('程序已退出', result.stdout)
            cache = Path(directory) / 'work' / '.cache'
            self.assertEqual(list(cache.iterdir()), [])
            settings_path = Path(directory) / 'work' / 'settings.json'
            settings = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else None
            return result.stdout, settings

    def test_android_explicit_exit(self):
        output, settings = self.run_console('0\n')
        self.assertIn('Android', output)
        self.assertIsNone(settings)

    @unittest.skipUnless(HAS_IOS, '需要 ios 可选依赖。')
    def test_ios_explicit_exit(self):
        output, settings = self.run_console('0\n', 'ios')
        self.assertIn('iPhone', output)
        self.assertIsNone(settings)

    def test_queued_parameters_are_saved_before_exit(self):
        output, settings = self.run_console('8\n6:30\n3.25\n6\n0\n')
        self.assertIn('状态已刷新', output)
        self.assertEqual(settings['pace_s'], 390)
        self.assertEqual(settings['target_m'], 3250)

    def test_eof_in_menu_and_submenus_cleans_up(self):
        for commands in ('', '7\n', '7\nI\n', '8\n', '8\n6:00\n', '10\n', '11\n',
                         '11\n1\n', '11\n1\n5\n', '12\n'):
            with self.subTest(commands=commands):
                _, settings = self.run_console(commands)
                self.assertIsNone(settings)

    def test_queued_parameters_are_processed_before_eof(self):
        _, settings = self.run_console('8\n6:30\n3.25\n6\n')
        self.assertEqual(settings['pace_s'], 390)
        self.assertEqual(settings['target_m'], 3250)

    def test_cancelled_and_invalid_parameters_leave_settings_unchanged(self):
        output, settings = self.run_console('8\n6:00\n0\n8\n1:59\n6\n0\n')
        self.assertIn('输入无效', output)
        self.assertIn('状态已刷新', output)
        self.assertIsNone(settings)

    def test_environment_probe_for_installed_package(self):
        backends = ('android', 'ios') if HAS_IOS else ('android',)
        for backend in backends:
            with self.subTest(backend=backend):
                result = subprocess.run(
                    [sys.executable, '-B', str(ROOT / 'tools' / 'check_environment.py'), '--backend', backend],
                    text=True, encoding='utf-8', capture_output=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_runtime_lock_and_cleanup_across_processes(self):
        previous = {key: os.environ.get(key) for key in ('TMPDIR', 'TEMP', 'TMP')}
        with tempfile.TemporaryDirectory(prefix='startup-lock-', dir=CACHE) as directory:
            root = Path(directory)

            def probe():
                return subprocess.run(
                    [sys.executable, '-B', str(Path(__file__).resolve()), '--probe-lock', str(root)],
                    capture_output=True, timeout=30,
                )

            with runtime(root):
                temporary = Path(tempfile.gettempdir())
                self.assertTrue(temporary.is_relative_to(root))
                self.assertEqual(probe().returncode, 2)
            self.assertFalse(temporary.exists())
            self.assertEqual(probe().returncode, 0)
            self.assertFalse((root / 'work' / '.campusroute.lock').exists())
        self.assertEqual(previous, {key: os.environ.get(key) for key in previous})


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--probe-lock':
        try:
            with instance_lock(Path(sys.argv[2])):
                pass
        except AlreadyRunningError:
            raise SystemExit(2)
    else:
        unittest.main()
