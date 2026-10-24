"""Local preferences, independent of device sessions and temporary runtime files."""

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import geojson

from campusroute.routes import Route, RoutePath, route_from_feature
from campusroute.variation import Variation


@dataclass
class Settings:
    route: Route
    pace_s: int = 120
    target_m: float = 5000
    variation: Variation = field(default_factory=Variation)


class SettingsStore:
    def __init__(self, root: Path):
        self.path = root / 'work' / 'settings.json'

    def load(self, routes: list[Route]) -> tuple[Settings, str]:
        settings = Settings(routes[0])
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return settings, ''
        except (OSError, ValueError) as error:
            return settings, f'无法读取上次配置，已使用默认设置：{error}'
        if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
            return settings, '上次配置格式无法识别，已使用默认设置。'

        invalid = []
        if 'variation' in data:
            try:
                settings.variation = Variation(**data['variation'])
            except (TypeError, ValueError, OverflowError):
                invalid.append('波动设置')
        pace = data.get('pace_s')
        if type(pace) is int and pace >= 120:
            settings.pace_s = pace
        else:
            invalid.append('配速')
        target = data.get('target_m')
        try:
            valid_target = type(target) in (int, float) and math.isfinite(target) and target > 0
        except OverflowError:
            valid_target = False
        if valid_target:
            settings.target_m = target
        else:
            invalid.append('目标距离')
        try:
            selected = data['route']
            if selected['kind'] == 'preset':
                settings.route = next(route for route in routes if route.properties.get('id') == selected['id'])
            elif selected['kind'] == 'custom':
                route = route_from_feature(geojson.loads(json.dumps(selected['feature'])))
                RoutePath(route)
                settings.route = route
            else:
                raise ValueError('Unknown route kind')
        except (KeyError, TypeError, ValueError, AttributeError, StopIteration, OverflowError):
            invalid.append('路线')
        message = f'上次配置中的{"、".join(invalid)}无效，已恢复对应默认值。' if invalid else ''
        return settings, message

    def save(self, settings: Settings, routes: list[Route]):
        if settings.route in routes:
            selected = {'kind': 'preset', 'id': settings.route.properties['id']}
        else:
            selected = {'kind': 'custom', 'feature': settings.route.feature()}
        content = json.dumps({
            'version': 1, 'route': selected,
            'pace_s': settings.pace_s, 'target_m': settings.target_m,
            'variation': asdict(settings.variation),
        }, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='settings-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)
