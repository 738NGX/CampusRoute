from pathlib import Path
import shutil
import unittest

from campusroute.android import Adb, AndroidBackend, AndroidConnection
from campusroute.backends import SessionError


class AndroidTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_executable_reports_connection_error(self):
        with self.assertRaises(SessionError):
            await Adb(str(Path(__file__).parent / 'unavailable-adb')).run('version')

    async def test_invalid_apk_is_rejected_before_device_access(self):
        with self.assertRaises(ValueError):
            await AndroidBackend().install('unused', Path(__file__))

    async def test_invalid_position_and_velocity_are_rejected_before_sending(self):
        connection = AndroidConnection(Adb())
        for latitude, longitude in ((91, 0), (0, 181), (float('nan'), 0)):
            with self.assertRaises(ValueError):
                await connection.set(latitude, longitude)
        for speed, bearing in ((-1, 0), (101, 0), (0, 360), (0, float('inf'))):
            with self.assertRaises(ValueError):
                await connection.set_motion(31.3, 121.5, speed=speed, bearing=bearing)
        self.assertFalse(connection.simulated)
        self.assertIsNone(connection.writer)

    @unittest.skipUnless(shutil.which('adb'), '需要本机 Android SDK Platform-Tools。')
    async def test_installed_adb_version(self):
        self.assertIn('Android Debug Bridge', await Adb().run('version'))
