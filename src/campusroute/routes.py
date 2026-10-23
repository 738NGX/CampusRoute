import bisect
import math
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

import geojson
import geojson.geometry
import gpxpy
from geographiclib.geodesic import Geodesic

geojson.geometry.DEFAULT_PRECISION = 9


@dataclass(frozen=True)
class Route:
    name: str
    coordinates: tuple[tuple[float, float], ...]
    properties: dict = field(default_factory=dict)

    def __post_init__(self):
        if len(self.coordinates) < 2:
            raise ValueError('路线至少需要两个不同的坐标点。')
        for longitude, latitude in self.coordinates:
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (longitude, latitude)):
                raise ValueError('路线坐标必须为数字。')
            if not (math.isfinite(latitude) and math.isfinite(longitude)):
                raise ValueError('路线坐标必须为有限数字。')
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError('路线坐标超出 WGS84 经纬度范围。')
        if any(a == b for a, b in zip(self.coordinates, self.coordinates[1:])):
            raise ValueError('相邻坐标点不能完全相同，请删除重复坐标。')
        if self.closed and len(set(self.coordinates)) < 3:
            raise ValueError('闭合路线至少需要三个不同的坐标点。')

    @property
    def closed(self):
        return self.coordinates[0] == self.coordinates[-1]

    def feature(self):
        return geojson.Feature(
            geometry=geojson.LineString(self.coordinates, precision=9),
            properties={
                **self.properties, 'name': self.name, 'coordinate_system': 'WGS84',
                'length_m': round(RoutePath(self).length_m, 3),
            },
        )


class RoutePath:
    def __init__(self, route: Route):
        self.route = route
        self.lines = []
        self.ends = [0.0]
        for first, second in zip(route.coordinates, route.coordinates[1:]):
            line = Geodesic.WGS84.InverseLine(first[1], first[0], second[1], second[0])
            self.lines.append(line)
            self.ends.append(self.ends[-1] + line.s13)
        self.length_m = self.ends[-1]
        if self.length_m < 10:
            raise ValueError('路线总长度至少为10米。')

    def position(self, distance_m: float) -> tuple[float, float]:
        if not math.isfinite(distance_m) or distance_m < 0:
            raise ValueError('移动距离必须为有限的非负数。')
        # 闭合路线循环前进；开放路线到达终点后沿原路返回。
        cycle = self.length_m if self.route.closed else self.length_m * 2
        offset = distance_m % cycle
        if offset > self.length_m:
            offset = cycle - offset
        index = min(bisect.bisect_right(self.ends, offset) - 1, len(self.lines) - 1)
        point = self.lines[index].Position(offset - self.ends[index])
        return point['lat2'], point['lon2']


def route_from_feature(feature) -> Route:
    if not isinstance(feature, geojson.Feature) or not isinstance(feature.geometry, geojson.LineString):
        raise ValueError('GeoJSON 文件必须包含一个 Feature，geometry 类型为 LineString。')
    if not feature.geometry.is_valid:
        raise ValueError('GeoJSON 路线坐标格式无效。')
    properties = feature.properties or {}
    if properties.get('coordinate_system', 'WGS84') != 'WGS84':
        raise ValueError('请提供 WGS84 坐标；GCJ-02、BD-09 坐标需要先转换。')
    name = properties.get('name', '自定义路线')
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError('路线名称需要包含1至120个字符。')
    coordinates = feature.geometry.coordinates
    if any(len(point) != 2 for point in coordinates):
        raise ValueError('GeoJSON 坐标需要采用 [经度, 纬度] 的二维格式。')
    return Route(name.strip(), tuple(tuple(point) for point in coordinates), properties)


def read_route(path: Path) -> Route:
    if path.suffix.lower() in ('.geojson', '.json'):
        with path.open(encoding='utf-8') as handle:
            route = route_from_feature(geojson.load(handle))
    elif path.suffix.lower() == '.gpx':
        with path.open(encoding='utf-8') as handle:
            document = gpxpy.parse(handle)
        segments = [segment.points for track in document.tracks for segment in track.segments if segment.points]
        segments.extend(item.points for item in document.routes if item.points)
        if len(segments) != 1:
            raise ValueError('GPX 文件需要包含一条连续路线；请先合并多个路线段。')
        points = tuple((point.longitude, point.latitude) for point in segments[0])
        route = Route(path.stem, points)
    else:
        raise ValueError('请选择 .geojson 或 .gpx 路线文件。')
    RoutePath(route)
    return route


def presets() -> list[Route]:
    directory = files('campusroute').joinpath('data')
    routes = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.name.endswith('.geojson'):
            route = route_from_feature(geojson.loads(path.read_text(encoding='utf-8')))
            RoutePath(route)
            routes.append(route)
    if not routes:
        raise RuntimeError('未找到内置路线数据。')
    return sorted(routes, key=lambda route: route.properties['order'])
