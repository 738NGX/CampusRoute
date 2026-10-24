import unittest

from geographiclib.geodesic import Geodesic

from campusroute.motion import Motion
from campusroute.routes import Route, RoutePath, presets
from campusroute.variation import Variation


class VariationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = RoutePath(next(route for route in presets() if route.properties['id'] == 'sufe-wudong'))

    def motion(self, **kwargs):
        return Motion(self.path, 360, 10000, variation=Variation(True), seed=42, **kwargs)

    def test_disabled_preserves_constant_playback(self):
        baseline = Motion(self.path, 360)
        disabled = Motion(self.path, 360, variation=Variation(False, 20, 3), seed=42)
        for motion in (baseline, disabled):
            motion.start(0)
        for now in (0.2, 5, 20, 100):
            for motion in (baseline, disabled):
                motion.advance(now)
            self.assertEqual(disabled.position, baseline.position)
            self.assertEqual(disabled.velocity, baseline.velocity)
            self.assertEqual(disabled.distance_m, baseline.distance_m)

    def test_pace_is_bounded_smooth_and_varies(self):
        motion = self.motion()
        paces = [1000 / motion.speed_at(index / 5) for index in range(1500)]
        self.assertGreater(max(paces) - min(paces), 10)
        self.assertTrue(all(342 <= pace <= 378 for pace in paces))
        self.assertLess(max(abs(a - b) for a, b in zip(paces, paces[1:])), 1.2)
        fastest = Motion(self.path, 120, variation=Variation(True, 20, 0), seed=42)
        self.assertTrue(all(120 - 1e-9 <= 1000 / fastest.speed_at(index) <= 144 for index in range(300)))

    def test_lateral_offset_is_bounded_and_closed_seam_has_no_jump(self):
        motion = self.motion()
        offsets = []
        for index in range(400):
            distance, elapsed = index * 2, index * 0.72
            point = motion.position_at(distance, elapsed)
            offsets.append(Geodesic.WGS84.Inverse(*self.path.position(distance), *point)['s12'])
        self.assertLessEqual(max(offsets), 0.600001)
        self.assertGreater(max(offsets), 0.2)
        self.assertEqual(motion.position_at(0, 0), self.path.position(0))
        for distance in (self.path.length_m, 2 * self.path.length_m):
            before = motion.position_at(distance - 0.001, 100)
            after = motion.position_at(distance + 0.001, 100.00072)
            self.assertLess(Geodesic.WGS84.Inverse(*before, *after)['s12'], 0.01)

    def test_open_route_turnaround_does_not_flip_lateral_side(self):
        path = RoutePath(Route('straight', ((121.5, 31.3), (121.5, 31.301))))
        motion = Motion(path, variation=Variation(True, 0, 3), seed=42)
        points = [motion.position_at(path.length_m + delta, 20 + delta / 3)
                  for delta in (-0.001, 0, 0.001)]
        self.assertTrue(all(Geodesic.WGS84.Inverse(*first, *second)['s12'] < 0.01
                            for first, second in zip(points, points[1:])))

    def test_distance_integrates_speed_and_is_independent_of_update_cadence(self):
        coarse, fine = self.motion(), self.motion()
        coarse.start(0)
        fine.start(0)
        coarse.advance(100)
        for index in range(1, 501):
            fine.advance(index / 5)
        self.assertAlmostEqual(coarse.distance_m, fine.distance_m, delta=0.001)
        self.assertGreater(abs(fine.distance_m - 100 * fine.speed_at(100)), 1)
        self.assertAlmostEqual(fine.elapsed_s, 100)

    def test_pause_resume_stop_hold_the_same_perturbed_point(self):
        motion = self.motion()
        motion.start(0)
        motion.advance(20)
        position, distance = motion.position, motion.distance_m
        motion.pause(25)
        motion.advance(1000)
        self.assertEqual((motion.position, motion.distance_m, motion.elapsed_s), (position, distance, 20))
        self.assertEqual(motion.velocity, (0, 0))
        motion.start(1001)
        self.assertEqual(motion.position, position)
        motion.advance(1002)
        self.assertEqual(motion.elapsed_s, 21)
        position = motion.position
        motion.stop(1003)
        motion.advance(2000)
        self.assertEqual(motion.position, position)
        self.assertEqual(motion.velocity, (0, 0))

    def test_target_is_exact_and_finished_point_stays_still(self):
        motion = Motion(self.path, 360, 10, variation=Variation(True), seed=42)
        motion.start(0)
        motion.advance(100)
        self.assertEqual(motion.phase, 'finished')
        self.assertEqual(motion.distance_m, 10)
        self.assertTrue(3.42 <= motion.elapsed_s <= 3.78)
        self.assertAlmostEqual(motion.travel(0, motion.elapsed_s), 10, delta=0.000001)
        position = motion.position
        motion.advance(1000)
        self.assertEqual(motion.position, position)
        self.assertEqual(motion.velocity, (0, 0))

    def test_new_seed_changes_playback_but_fixed_seed_is_reproducible(self):
        first, same = self.motion(), self.motion()
        other = Motion(self.path, 360, variation=Variation(True), seed=43)
        for motion in (first, same, other):
            motion.start(0)
            motion.advance(30)
        self.assertEqual(first.position, same.position)
        self.assertEqual(first.velocity, same.velocity)
        self.assertNotEqual(first.position, other.position)
        self.assertNotEqual(first.velocity, other.velocity)

    def test_invalid_ranges_are_rejected(self):
        for settings in ((1, 5, 0.6), (True, -1, 0.6), (True, 21, 0.6),
                         (True, 5, 3.01), (True, 5, float('nan')), (True, float('inf'), 0),
                         (True, True, 0), (True, 5, -1)):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                Variation(*settings)
