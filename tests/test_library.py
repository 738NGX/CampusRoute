from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from campusroute.library import RouteLibrary
from campusroute.console import ConsoleApp
from campusroute.mapserver import MapServer
from campusroute.routes import Route, presets
from support import CACHE, run_console


class LibraryTests(unittest.TestCase):
    def setUp(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=CACHE)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.library = RouteLibrary(self.root)
        self.presets = presets()
        self.route = Route('我的路线', self.presets[0].coordinates, {'source': '用户绘制'})

    def test_saved_routes_keep_order_and_duplicate_save_is_idempotent(self):
        first = self.library.save(self.route)
        second = self.library.save(Route('第二条路线', self.route.coordinates))
        self.assertEqual(self.library.save(self.route), first)
        self.assertEqual(RouteLibrary(self.root).load(), [first, second])
        self.assertFalse(list(self.library.path.parent.glob('*.tmp')))

    def test_concurrent_saves_preserve_all_routes(self):
        routes = [Route(f'路线{index}', self.route.coordinates) for index in range(8)]
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(self.library.save, routes))
        self.assertEqual({item.name for item in self.library.load()}, {item.name for item in routes})

    def test_session_only_routes_do_not_create_files(self):
        temporary = self.library.save(self.route, persist=False)
        self.assertEqual(self.library.available(), [temporary])
        self.assertEqual(self.library.save(self.route, persist=False), temporary)
        self.assertFalse(self.library.path.exists())
        self.assertEqual(RouteLibrary(self.root).available(), [])

    def test_embedded_custom_route_is_added_to_library_on_startup(self):
        path = self.root / 'work' / 'settings.json'
        path.parent.mkdir()
        path.write_text(json.dumps({'version': 1, 'route': {'kind': 'custom', 'feature': self.route.feature()},
                                    'pace_s': 360, 'target_m': 2500}), encoding='utf-8')
        result = run_console(self.root, '0\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.library.load()[0].name, self.route.name)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['route']['kind'], 'saved')

    def test_saving_session_route_permanently_keeps_single_option(self):
        self.library.save(self.route, persist=False)
        saved = self.library.save(self.route)
        self.assertEqual(self.library.available(), [saved])

    def test_selected_session_route_can_be_saved_and_restored(self):
        app = ConsoleApp(self.root)
        app.route = app.route_library.save(self.route, persist=False)
        saved = app.route_library.save(self.route)
        app.save_settings()
        self.assertEqual(app.route, saved)
        self.assertEqual(ConsoleApp(self.root).route, saved)

    def test_corrupt_library_is_not_overwritten(self):
        self.library.path.parent.mkdir()
        self.library.path.write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.library.save(self.route)
        self.assertEqual(self.library.path.read_text(encoding='utf-8'), '{}')

    def test_cli_import_adds_number_and_survives_source_removal(self):
        source = self.root / 'route.geojson'
        source.write_text(json.dumps(self.route.feature()), encoding='utf-8')
        result = run_console(self.root, f'7\nI\n{source}\n0\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        number = len(self.presets) + 1
        self.assertIn(f'路线编号{number}', result.stdout)
        source.unlink()
        result = run_console(self.root, f'7\n{number}\n0\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'{number}  我的路线', result.stdout)
        self.assertEqual(len(self.library.load()), 1)

    def test_cli_save_opt_out_is_persistent_and_keeps_route_in_memory(self):
        source = self.root / 'route.geojson'
        source.write_text(json.dumps(self.route.feature()), encoding='utf-8')
        number = len(self.presets) + 1
        result = run_console(self.root, f'12\n2\n7\nI\n{source}\n7\n{number}\n0\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('仅本次窗口使用', result.stdout)
        self.assertFalse(self.library.path.exists())
        settings = json.loads((self.root / 'work' / 'settings.json').read_text(encoding='utf-8'))
        self.assertFalse(settings['save_custom_routes'])
        result = run_console(self.root, '7\n0\n0\n')
        self.assertNotIn('我的路线', result.stdout)

    def test_map_save_returns_console_number_and_supports_opt_out(self):
        server = MapServer(lambda: self.presets + self.library.available(), self.library)
        try:
            def save(feature, persist, origin=None):
                headers = {'Content-Type': 'application/json'}
                if origin:
                    headers['Origin'] = origin
                request = Request(server.url + 'save-route',
                                  json.dumps({'feature': feature, 'save': persist}).encode('utf-8'), headers)
                with urlopen(request, timeout=3) as response:
                    return json.load(response)
            result = save(self.route.feature(), True)
            self.assertEqual(result, {'number': len(self.presets) + 1, 'saved': True})
            temporary = Route('临时路线', self.route.coordinates)
            result = save(temporary.feature(), False)
            self.assertEqual(result, {'number': len(self.presets) + 2, 'saved': False})
            with urlopen(server.url + 'routes.json', timeout=3) as response:
                self.assertEqual(len(json.load(response)['features']), len(self.presets) + 2)
            with self.assertRaises(HTTPError) as caught:
                save(self.route.feature(), True, 'https://example.com')
            self.assertEqual(caught.exception.code, 400)
        finally:
            server.close()
        self.assertEqual([item.name for item in RouteLibrary(self.root).load()], ['我的路线'])
