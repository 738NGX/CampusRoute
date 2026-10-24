import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import geojson

from campusroute.routes import Route, RoutePath, route_from_feature
from campusroute.storage import write_json
from campusroute.variation import Variation


@dataclass
class Settings:
    route: Route
    pace_s: int = 120
    target_m: float = 5000
    variation: Variation = field(default_factory=Variation)
    save_custom_routes: bool = True

    def __post_init__(self):
        if type(self.pace_s) is not int or self.pace_s < 120:
            raise ValueError('保存的配速必须为每公里至少120秒。')
        if type(self.target_m) not in (int, float) or not math.isfinite(self.target_m) or self.target_m <= 0:
            raise ValueError('保存的目标距离必须为有限的正数。')
        if type(self.save_custom_routes) is not bool:
            raise ValueError('自定义路线保存开关必须为布尔值。')


class SettingsStore:
    def __init__(self, root: Path):
        self.path = root / 'work' / 'settings.json'

    def load(self, routes: list[Route]) -> Settings:
        if not self.path.exists():
            return Settings(routes[0])
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
            raise ValueError('设置文件格式无法识别，请检查 work/settings.json，或删除该文件恢复默认设置。')
        selected = data['route']
        if selected['kind'] == 'preset':
            matches = [item for item in routes if item.properties.get('id') == selected['id']]
        elif selected['kind'] == 'saved':
            matches = [item for item in routes if item.properties.get('local_id') == selected['id']]
        elif selected['kind'] == 'custom':
            matches = [route_from_feature(geojson.loads(json.dumps(selected['feature'])))]
        else:
            raise ValueError('保存的路线类型无法识别。')
        if not matches:
            raise ValueError('已选择的路线不存在，请检查路线收藏，或删除 work/settings.json 重新选择。')
        RoutePath(matches[0])
        return Settings(matches[0], data['pace_s'], data['target_m'],
                        Variation(**data.get('variation', {})), data.get('save_custom_routes', True))

    def save(self, settings: Settings, routes: list[Route]):
        route = settings.route if settings.route in routes and not settings.route.properties.get('session_only') else routes[0]
        local_id = route.properties.get('local_id')
        selected = {'kind': 'saved', 'id': local_id} if local_id else {'kind': 'preset', 'id': route.properties['id']}
        write_json(self.path, {
            'version': 1, 'route': selected, 'pace_s': settings.pace_s,
            'target_m': settings.target_m, 'variation': asdict(settings.variation),
            'save_custom_routes': settings.save_custom_routes,
        })
