import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Variation:
    enabled: bool = False
    pace_percent: float = 5.0
    lateral_m: float = 0.6

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError('波动开关必须为布尔值。')
        for value, maximum, label in ((self.pace_percent, 20, '配速波动'),
                                      (self.lateral_m, 3, '横向偏移')):
            if type(value) not in (int, float) or not 0 <= value <= maximum or not math.isfinite(value):
                raise ValueError(f'{label}必须在0至{maximum}之间。')

    @property
    def label(self):
        if not self.enabled:
            return '关闭'
        return f'配速±{self.pace_percent:g}%；横向≤{self.lateral_m:g}米'
