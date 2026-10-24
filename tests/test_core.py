import json
from pathlib import Path
import tempfile
import unittest
from urllib.request import urlopen

from campusroute.mapserver import MapServer
from campusroute.motion import Motion, parse_pace
from campusroute.routes import RoutePath, presets, read_route

CACHE = Path(__file__).resolve().parents[1] / 'work' / '.cache'


class CoreTests(unittest.TestCase):
    def test_presets_round_trip_and_provenance(self):
        routes = presets()
        self.assertEqual(len({item.properties['id'] for item in routes}), len(routes))
        CACHE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=CACHE) as directory:
            for route in routes:
                length = RoutePath(route).length_m
                self.assertTrue(route.closed)
                self.assertTrue(100 < length < 1000)
                self.assertTrue(route.properties.get('source_url') or route.properties.get('source_file'))
                path = Path(directory) / 'route.geojson'
                path.write_text(json.dumps(route.feature()), encoding='utf-8')
                self.assertEqual(read_route(path).coordinates, route.coordinates)

    def test_pace_validation_and_pause_resume_finish(self):
        for value in ('1:59', '6:60', 'NaN', '2'):
            with self.assertRaises(ValueError):
                parse_pace(value)
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
        self.assertEqual(motion.velocity, (0, 0))

    def test_pause_and_stop_hold_last_confirmed_position(self):
        for action in ('pause', 'stop'):
            motion = Motion(RoutePath(presets()[0]))
            motion.start(0)
            motion.advance(1)
            position, distance = motion.position, motion.distance_m
            getattr(motion, action)(4)
            motion.advance(20)
            self.assertEqual(motion.position, position)
            self.assertEqual(motion.distance_m, distance)
            self.assertEqual(motion.velocity, (0, 0))

    def test_map_assets_and_security_headers(self):
        server = MapServer(presets)
        try:
            with urlopen(server.url + 'routes.json', timeout=3) as response:
                self.assertEqual(len(json.load(response)['features']), len(presets()))
            with urlopen(server.url, timeout=3) as response:
                self.assertIn('save-route', response.read().decode('utf-8'))
                self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
        finally:
            server.close()
