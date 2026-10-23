import math
import re
from dataclasses import dataclass

from campusroute.routes import RoutePath


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

    def __post_init__(self):
        if isinstance(self.pace_s, bool) or not isinstance(self.pace_s, int) or self.pace_s < 120:
            raise ValueError('配速至少为每公里120秒。')
        if not math.isfinite(self.target_m) or self.target_m <= 0:
            raise ValueError('目标距离必须为有限的正数。')

    def advance(self, now: float):
        if not math.isfinite(now) or (self.previous_s is not None and now < self.previous_s):
            raise ValueError('运行时钟必须为递增的有限数字。')
        if self.previous_s is not None and self.phase == 'running':
            self.elapsed_s += now - self.previous_s
            self.distance_m = min(self.target_m, self.elapsed_s * (1000 / self.pace_s))
            if self.distance_m >= self.target_m:
                self.phase = 'finished'
                self.elapsed_s = self.target_m / 1000 * self.pace_s
        self.previous_s = now

    def start(self, now: float):
        if self.phase not in ('ready', 'paused'):
            raise ValueError('当前状态无法开始移动。')
        self.advance(now)
        self.phase = 'running'

    def pause(self, now: float):
        if self.phase != 'running':
            raise ValueError('当前没有正在进行的移动。')
        self.advance(now)
        if self.phase != 'finished':
            self.phase = 'paused'

    def stop(self, now: float):
        self.advance(now)
        self.phase = 'stopped'

    @property
    def position(self):
        return self.path.position(self.distance_m)
