import json
from pathlib import Path
import tempfile
import unittest

from campusroute.library import RouteLibrary
from campusroute.routes import Route, presets
from campusroute.settings import Settings, SettingsStore
from campusroute.storage import write_json
from campusroute.variation import Variation

CACHE = Path(__file__).resolve().parents[1] / 'work' / '.cache'


class SettingsTests(unittest.TestCase):
    def setUp(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=CACHE)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = SettingsStore(self.root)
        self.routes = presets()

    def test_defaults_and_settings_round_trip(self):
        self.assertEqual(self.store.load(self.routes), Settings(self.routes[0]))
        expected = Settings(self.routes[-1], 395, 2500.5, Variation(True, 7.5, 0.8), False)
        self.store.save(expected, self.routes)
        self.assertEqual(self.store.load(list(reversed(self.routes))), expected)
        self.assertFalse(list(self.store.path.parent.glob('*.tmp')))

    def test_missing_optional_fields_use_documented_defaults(self):
        self.store.save(Settings(self.routes[-1]), self.routes)
        data = json.loads(self.store.path.read_text(encoding='utf-8'))
        del data['variation'], data['save_custom_routes']
        write_json(self.store.path, data)
        self.assertEqual(self.store.load(self.routes), Settings(self.routes[-1]))

    def test_corrupt_settings_fail_without_overwriting_file(self):
        self.store.path.parent.mkdir()
        for content in ('{', '[]', '{"version": 9}'):
            self.store.path.write_text(content, encoding='utf-8')
            with self.assertRaises(ValueError):
                self.store.load(self.routes)
            self.assertEqual(self.store.path.read_text(encoding='utf-8'), content)

    def test_invalid_values_fail_before_writing(self):
        self.store.save(Settings(self.routes[0]), self.routes)
        before = self.store.path.read_bytes()
        for pace, target in ((119, 1000), (True, 1000), (360, float('nan'))):
            with self.assertRaises(ValueError):
                self.store.save(Settings(self.routes[0], pace, target), self.routes)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_saved_route_reference_survives_restart(self):
        library = RouteLibrary(self.root)
        route = library.save(Route('收藏路线', self.routes[0].coordinates))
        self.store.save(Settings(route), self.routes + library.available())
        restored = self.store.load(self.routes + RouteLibrary(self.root).available())
        self.assertEqual(restored.route, route)

    def test_session_route_is_not_embedded_in_settings(self):
        library = RouteLibrary(self.root)
        route = library.save(Route('临时路线', self.routes[0].coordinates), persist=False)
        self.store.save(Settings(route, save_custom_routes=False), self.routes + library.available())
        self.assertNotIn('临时路线', self.store.path.read_text(encoding='utf-8'))
        self.assertFalse(library.path.exists())
        self.assertEqual(self.store.load(self.routes).route, self.routes[0])
