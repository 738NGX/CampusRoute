import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from campusroute.routes import presets
from campusroute.settings import Settings, SettingsStore
from campusroute.variation import Variation


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes = presets()

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = SettingsStore(Path(directory.name))

    def test_first_launch_defaults_and_preset_selected_by_id(self):
        settings, warning = self.store.load(self.routes)
        self.assertEqual(settings, Settings(self.routes[0]))
        self.assertEqual(warning, '')
        expected = Settings(self.routes[-1], 395, 2500.5)
        self.store.save(expected, self.routes)
        restored, warning = self.store.load(list(reversed(self.routes)))
        self.assertEqual(restored, expected)
        self.assertEqual(warning, '')
        data = json.loads(self.store.path.read_text(encoding='utf-8'))
        self.assertEqual(data['route'], {'kind': 'preset', 'id': expected.route.properties['id']})
        self.assertEqual(set(data), {'version', 'route', 'pace_s', 'target_m', 'variation'})

    def test_variation_roundtrip_and_older_settings_default_to_off(self):
        expected = Settings(self.routes[-1], 360, 3000, Variation(True, 7.5, 0.8))
        self.store.save(expected, self.routes)
        restored, warning = self.store.load(self.routes)
        self.assertEqual(restored, expected)
        self.assertEqual(warning, '')
        data = json.loads(self.store.path.read_text(encoding='utf-8'))
        del data['variation']
        self.store.path.write_text(json.dumps(data), encoding='utf-8')
        restored, warning = self.store.load(self.routes)
        self.assertEqual(restored, Settings(self.routes[-1], 360, 3000))
        self.assertEqual(warning, '')

    def test_invalid_variation_keeps_other_saved_preferences(self):
        self.store.save(Settings(self.routes[-1], 360, 3000), self.routes)
        data = json.loads(self.store.path.read_text(encoding='utf-8'))
        for value in (None, [], {'enabled': 'true'}, {'enabled': True, 'lateral_m': 10}):
            self.store.path.write_text(json.dumps({**data, 'variation': value}), encoding='utf-8')
            restored, warning = self.store.load(self.routes)
            self.assertEqual(restored, Settings(self.routes[-1], 360, 3000))
            self.assertIn('波动设置', warning)

    def test_corrupt_or_unsupported_file_falls_back(self):
        self.store.path.parent.mkdir()
        for content in ('{', '[]', '{"version": 9}', '{"version": true}', '\ufeff{}'):
            with self.subTest(content=content):
                self.store.path.write_text(content, encoding='utf-8')
                restored, warning = self.store.load(self.routes)
                self.assertEqual(restored, Settings(self.routes[0]))
                self.assertTrue(warning)

    def test_invalid_fields_fall_back_independently(self):
        self.store.save(Settings(self.routes[-1], 360, 10000), self.routes)
        data = json.loads(self.store.path.read_text(encoding='utf-8'))
        for pace, target in [(True, False), (119, -1), (360.5, float('nan')), ('360', float('inf'))]:
            with self.subTest(pace=pace, target=target):
                self.store.path.write_text(json.dumps({**data, 'pace_s': pace, 'target_m': target}), encoding='utf-8')
                restored, warning = self.store.load(self.routes)
                self.assertEqual(restored, Settings(self.routes[-1]))
                self.assertIn('配速、目标距离', warning)
        for selected in ({'kind': 'preset', 'id': 'removed'}, {'kind': 'custom', 'feature': {}}, None):
            self.store.path.write_text(json.dumps({**data, 'route': selected}), encoding='utf-8')
            restored, warning = self.store.load(self.routes)
            self.assertEqual(restored, Settings(self.routes[0], 360, 10000))
            self.assertIn('路线', warning)

    def test_failed_atomic_replace_preserves_previous_file(self):
        self.store.save(Settings(self.routes[0]), self.routes)
        before = self.store.path.read_bytes()
        with patch('campusroute.settings.os.replace', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                self.store.save(Settings(self.routes[-1], 360, 1000), self.routes)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(list(self.store.path.parent.glob('settings-*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
