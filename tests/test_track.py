import itertools
import json
import math
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from geographiclib.geodesic import Geodesic

from campusroute.mapserver import MapServer
from campusroute.routes import RoutePath, presets, route_from_feature
from campusroute.track import generate_track, route_length
import geojson


def football_corners(length=105, width=68, rotation=0, longitude=121.5, latitude=31.3):
    points = []
    for x, y in [(-length / 2, -width / 2), (length / 2, -width / 2),
                 (length / 2, width / 2), (-length / 2, width / 2)]:
        angle = math.atan2(x, y) + math.radians(rotation)
        result = Geodesic.WGS84.Direct(latitude, longitude, math.degrees(angle), math.hypot(x, y))
        points.append([result['lon2'], result['lat2']])
    return points


class TrackTests(unittest.TestCase):
    def test_rotated_football_field_generates_closed_importable_route(self):
        feature = generate_track(football_corners(rotation=37))
        route = route_from_feature(geojson.loads(json.dumps(feature)))
        self.assertTrue(route.closed)
        self.assertGreater(len(route.coordinates), 100)
        self.assertAlmostEqual(feature['properties']['field_length_m'], 105, places=2)
        self.assertAlmostEqual(feature['properties']['field_width_m'], 68, places=2)
        self.assertAlmostEqual(feature['properties']['straight_length_m'], 85, places=2)
        radius = math.hypot(34, 10) + 2
        analytic_length = 2 * 85 + 2 * math.pi * radius
        self.assertAlmostEqual(RoutePath(route).length_m, analytic_length, delta=0.05)
        self.assertAlmostEqual(feature['properties']['length_m'], RoutePath(route).length_m, delta=0.001)
        self.assertTrue(feature['properties']['estimated'])

    def test_corner_selection_order_does_not_change_length(self):
        corners = football_corners(rotation=28)
        lengths = [generate_track(list(permutation))['properties']['length_m']
                   for permutation in itertools.permutations(corners)]
        self.assertLess(max(lengths) - min(lengths), 0.002)

    def test_track_encloses_every_football_corner_with_requested_clearance(self):
        corners = football_corners()
        feature = generate_track(corners, clearance_m=3, end_inset_m=12)
        track = feature['geometry']['coordinates']
        # 采样点间距最多两米，最近采样点与圆弧的距离存在少量偏差。
        for corner in corners:
            nearest = min(Geodesic.WGS84.Inverse(corner[1], corner[0], point[1], point[0])['s12']
                          for point in track)
            self.assertGreaterEqual(nearest, 2.99)
            self.assertLess(nearest, 3.2)

    def test_larger_clearance_increases_perimeter_as_expected(self):
        corners = football_corners()
        small = generate_track(corners, 1)['properties']['length_m']
        large = generate_track(corners, 4)['properties']['length_m']
        self.assertAlmostEqual(large - small, 2 * math.pi * 3, delta=0.02)

    def test_zero_inset_and_date_line_are_supported(self):
        feature = generate_track(football_corners(longitude=179.9999, latitude=70), 0, 0)
        self.assertAlmostEqual(feature['properties']['straight_length_m'], 105, places=2)
        self.assertAlmostEqual(feature['properties']['bend_radius_m'], 34, places=2)
        self.assertGreater(feature['properties']['length_m'], 400)

    def test_invalid_quadrilaterals_and_parameters_rejected(self):
        valid = football_corners()
        cases = [valid[:3], [valid[0]] * 4,
                 [valid[0], valid[1], valid[2], [121.5, 31.3]],
                 [[121.5, 31.3 + index * 0.0001] for index in range(4)],
                 football_corners(length=5, width=4), football_corners(length=3000)]
        for points in cases:
            with self.subTest(points=points), self.assertRaises(ValueError):
                generate_track(points)
        for value in (None, True, float('nan'), -1, 31, '2'):
            with self.subTest(clearance=value), self.assertRaises(ValueError):
                generate_track(valid, clearance_m=value)
        with self.assertRaises(ValueError):
            generate_track(football_corners(length=30, width=20), end_inset_m=20)

    def test_manual_distance_includes_closing_segment_only_when_closed(self):
        corners = football_corners()
        open_length = route_length(corners)
        closed_length = route_length(corners + [corners[0]])
        self.assertAlmostEqual(closed_length, 346, places=2)
        self.assertAlmostEqual(closed_length - open_length, 68, places=2)
        self.assertEqual(route_length([]), 0)
        self.assertEqual(route_length([corners[0]]), 0)
        self.assertLess(route_length([corners[0], corners[0]]), 0.001)


class TrackApiTests(unittest.TestCase):
    def setUp(self):
        self.server = MapServer(presets)

    def tearDown(self):
        self.server.close()

    def post(self, endpoint, value):
        request = Request(self.server.url + endpoint, json.dumps(value).encode('utf-8'),
                          {'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_generation_and_distance_apis_agree(self):
        feature = self.post('generate-track', {'corners': football_corners()})
        length = self.post('route-length', {'coordinates': feature['geometry']['coordinates']})
        self.assertEqual(length['length_m'], feature['properties']['length_m'])

    def test_invalid_geometry_has_actionable_json_error(self):
        with self.assertRaises(HTTPError) as caught:
            self.post('generate-track', {'corners': []})
        self.assertEqual(caught.exception.code, 400)
        self.assertIn('error', json.load(caught.exception))

    def test_oversized_coordinate_list_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            self.post('route-length', {'coordinates': [[121.5, 31.3]] * 4097})
        self.assertEqual(caught.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
