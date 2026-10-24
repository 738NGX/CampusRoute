import math
import random
import re
from dataclasses import dataclass, field

from geographiclib.geodesic import Geodesic

from campusroute.routes import RoutePath
from campusroute.variation import Variation


def parse_pace(value: str) -> int:
    if not re.fullmatch(r'[0-9]+:[0-5][0-9]', value):
        raise ValueError('配速格式为 分钟:秒，例如2:00、6:30、120:00。')
    minutes, seconds = value.split(':')
    pace_s = int(minutes) * 60 + int(seconds)
    if pace_s < 120:
        raise ValueError('最快配速为2:00／公里。')
    return pace_s


def pace_label(pace_s: int) -> str:
    return f'{pace_s // 60}:{pace_s % 60:02d}'


@dataclass
class Motion:
    path: RoutePath
    pace_s: int = 120
    target_m: float = 5000
    phase: str = 'ready'
    distance_m: float = 0
    elapsed_s: float = 0
    previous_s: float | None = None
    variation: Variation = field(default_factory=Variation, kw_only=True)
    seed: int | None = field(default=None, kw_only=True, repr=False)
    _pace_wave: tuple = field(init=False, repr=False)
    _lateral_wave: tuple = field(init=False, repr=False)

    def __post_init__(self):
        if isinstance(self.pace_s, bool) or not isinstance(self.pace_s, int) or self.pace_s < 120:
            raise ValueError('配速至少为每公里120秒。')
        if not math.isfinite(self.target_m) or self.target_m <= 0:
            raise ValueError('目标距离必须为有限的正数。')
        generator = random.Random(self.seed)
        self._pace_wave = tuple((weight, generator.uniform(*period), generator.uniform(0, math.tau))
                                for weight, period in ((0.55, (14, 26)), (0.3, (40, 65)), (0.15, (90, 140))))
        self._lateral_wave = tuple((weight, generator.uniform(*period), generator.uniform(0, math.tau))
                                   for weight, period in ((0.55, (18, 36)), (0.3, (50, 80)), (0.15, (120, 180))))

    @staticmethod
    def wave(components, elapsed):
        return sum(weight * math.sin(phase + math.tau * elapsed / period)
                   for weight, period, phase in components)

    def speed_at(self, elapsed):
        pace = self.pace_s
        if self.variation.enabled:
            pace *= 1 + self.variation.pace_percent / 100 * self.wave(self._pace_wave, elapsed)
        return 1000 / max(120, pace)

    def travel(self, start, end):
        # 使用不超过一秒的 Simpson 积分区间累计变速里程。
        count = max(1, math.ceil(end - start))
        step = (end - start) / count
        return sum(step / 6 * (self.speed_at(start + index * step)
                   + 4 * self.speed_at(start + (index + 0.5) * step)
                   + self.speed_at(start + (index + 1) * step)) for index in range(count))

    def check_time(self, now: float):
        if not math.isfinite(now) or (self.previous_s is not None and now < self.previous_s):
            raise ValueError('运行时钟必须为递增的有限数字。')

    def advance(self, now: float):
        self.check_time(now)
        if self.previous_s is not None and self.phase == 'running':
            if not self.variation.enabled or self.variation.pace_percent == 0:
                self.elapsed_s += now - self.previous_s
                self.distance_m = min(self.target_m, self.elapsed_s * (1000 / self.pace_s))
                if self.distance_m >= self.target_m:
                    self.phase = 'finished'
                    self.elapsed_s = self.target_m / 1000 * self.pace_s
            else:
                remaining = self.target_m - self.distance_m
                minimum_speed = 1000 / (self.pace_s * (1 + self.variation.pace_percent / 100))
                end = self.elapsed_s + min(now - self.previous_s, remaining / minimum_speed)
                distance = self.travel(self.elapsed_s, end)
                if distance >= remaining:
                    low, high = self.elapsed_s, end
                    for _ in range(36):
                        middle = (low + high) / 2
                        if self.travel(self.elapsed_s, middle) < remaining:
                            low = middle
                        else:
                            high = middle
                    self.elapsed_s = (low + high) / 2
                    self.distance_m = self.target_m
                    self.phase = 'finished'
                else:
                    self.elapsed_s = end
                    self.distance_m += distance
        self.previous_s = now

    def start(self, now: float):
        if self.phase not in ('ready', 'paused'):
            raise ValueError('当前状态无法开始移动。')
        self.advance(now)
        self.phase = 'running'

    def pause(self, now: float):
        if self.phase != 'running':
            raise ValueError('当前没有正在进行的移动。')
        self.check_time(now)
        # 暂停时保持最后确认的位置。
        self.phase = 'paused'
        self.previous_s = now

    def stop(self, now: float):
        self.check_time(now)
        self.phase = 'stopped'
        self.previous_s = now

    @property
    def position(self):
        return self.position_at(self.distance_m, self.elapsed_s)

    def position_at(self, distance, elapsed):
        latitude, longitude = self.path.position(distance)
        if not self.variation.enabled or not self.variation.lateral_m:
            return latitude, longitude
        ramp = min(1, elapsed / 8)
        offset = self.variation.lateral_m * self.wave(self._lateral_wave, elapsed) * ramp * ramp * (3 - 2 * ramp)
        if offset == 0:
            return latitude, longitude
        length = self.path.length_m
        if self.path.route.closed:
            before = self.path.position((distance - 2) % length)
            after = self.path.position((distance + 2) % length)
        else:
            # 开放路线折返时保持横向偏移方向连续。
            progress = distance % (2 * length)
            progress = min(progress, 2 * length - progress)
            before = self.path.position(max(0, progress - 2))
            after = self.path.position(min(length, progress + 2))
        normal = Geodesic.WGS84.Inverse(*before, *after)['azi1'] + 90
        point = Geodesic.WGS84.Direct(latitude, longitude, normal, offset)
        return point['lat2'], point['lon2']

    @property
    def velocity(self):
        if self.phase != 'running':
            return 0.0, 0.0
        # 使用轨迹前方位置计算当前朝向。
        speed = self.speed_at(self.elapsed_s)
        ahead = self.position_at(self.distance_m + 0.5, self.elapsed_s + 0.5 / speed)
        bearing = Geodesic.WGS84.Inverse(*self.position, *ahead)['azi1'] % 360
        return speed, bearing
