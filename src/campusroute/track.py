"""Estimate a stadium-shaped track around four football-pitch corners in WGS84."""
import math

from geographiclib.geodesic import Geodesic

from campusroute.routes import Route

GEODESIC = Geodesic.WGS84
MAX_POINTS = 4096


def coordinates(value, minimum=0, maximum=MAX_POINTS):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f'坐标点数量需要在{minimum}至{maximum}之间。')
    result = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError('坐标需要采用 [经度, 纬度] 格式。')
        if any(isinstance(number, bool) or not isinstance(number, (int, float))
               or (isinstance(number, float) and not math.isfinite(number)) for number in point):
            raise ValueError('坐标需要为有限数字。')
        longitude, latitude = point
        if not (-180 <= longitude <= 180 and -85 <= latitude <= 85):
            raise ValueError('坐标超出地图可显示的 WGS84 经纬度范围。')
        result.append((float(longitude), float(latitude)))
    return result


def route_length(points):
    points = coordinates(points)
    return sum(GEODESIC.Inverse(first[1], first[0], second[1], second[0])['s12']
               for first, second in zip(points, points[1:]))


def parameter(value, name, low, high):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not low <= value <= high or not math.isfinite(value)):
        raise ValueError(f'{name}需要为{low:g}至{high:g}米之间的数字。')
    return float(value)


def generate_track(corners, clearance_m=2, end_inset_m=10):
    corners = coordinates(corners, 4, 4)
    if len(set(corners)) != 4:
        raise ValueError('请选择四个不同的足球场角点。')
    clearance = parameter(clearance_m, '最小间距', 0, 30)
    inset = parameter(end_inset_m, '弯道内收', 0, 50)
    # Unwrap longitudes around the first point, including sites near the date line.
    reference = corners[0][0]
    longitude = sum(reference + (point[0] - reference + 180) % 360 - 180 for point in corners) / 4
    latitude = sum(point[1] for point in corners) / 4

    def project(point):
        line = GEODESIC.Inverse(latitude, longitude, point[1], point[0])
        angle = math.radians(line['azi1'])
        return line['s12'] * math.sin(angle), line['s12'] * math.cos(angle)

    points = sorted((project(point) for point in corners), key=lambda point: math.atan2(point[1], point[0]))
    if max(math.hypot(*point) for point in points) > 500:
        raise ValueError('角点相距过远，请只选择同一足球场的四个角。')
    cross_products = []
    edges = []
    for index in range(4):
        first, second, third = (points[(index + offset) % 4] for offset in range(3))
        a = (second[0] - first[0], second[1] - first[1])
        b = (third[0] - second[0], third[1] - second[1])
        edges.append(a)
        cross_products.append(a[0] * b[1] - a[1] * b[0])
    if min(cross_products) <= 1:
        raise ValueError('四个角需要围成凸四边形，不能重叠、共线或有一点落在内部。')
    lengths = [math.hypot(*edge) for edge in edges]
    index = 0 if lengths[0] + lengths[2] >= lengths[1] + lengths[3] else 1
    opposite = (index + 2) % 4
    axis = (edges[index][0] - edges[opposite][0], edges[index][1] - edges[opposite][1])
    magnitude = math.hypot(*axis)
    u = (axis[0] / magnitude, axis[1] / magnitude)
    v = (-u[1], u[0])

    def dot(point, vector):
        return point[0] * vector[0] + point[1] * vector[1]

    xs, ys = [dot(point, u) for point in points], [dot(point, v) for point in points]
    low_x, high_x, low_y, high_y = min(xs), max(xs), min(ys), max(ys)
    field_length, field_width = high_x - low_x, high_y - low_y
    if not (20 <= field_length <= 300 and 10 <= field_width <= 200):
        raise ValueError('足球场拟合尺寸不合理，请检查四个角的位置。')
    mismatch = max(math.hypot(min(abs(x - low_x), abs(x - high_x)),
                              min(abs(y - low_y), abs(y - high_y))) for x, y in zip(xs, ys))
    if mismatch > min(15, field_width * 0.25):
        raise ValueError('四边形偏离矩形过大，请沿足球场边缘重新选择四个角。')
    if inset > (field_length - 10) / 2:
        raise ValueError('弯道内收过大，请减小数值；直道长度至少需要10米。')
    middle_x, middle_y = (low_x + high_x) / 2, (low_y + high_y) / 2
    half_straight = field_length / 2 - inset
    # The pitch corners must fit inside the semicircles, not just between the straights.
    radius = math.hypot(field_width / 2, inset) + clearance
    arc_steps = max(24, math.ceil(math.pi * radius / 2))
    straight_steps = max(1, math.ceil(half_straight))
    local = []
    for index in range(arc_steps + 1):
        angle = -math.pi / 2 + math.pi * index / arc_steps
        local.append((half_straight + radius * math.cos(angle), radius * math.sin(angle)))
    for index in range(1, straight_steps + 1):
        local.append((half_straight - 2 * half_straight * index / straight_steps, radius))
    for index in range(1, arc_steps + 1):
        angle = math.pi / 2 + math.pi * index / arc_steps
        local.append((-half_straight + radius * math.cos(angle), radius * math.sin(angle)))
    for index in range(1, straight_steps):
        local.append((-half_straight + 2 * half_straight * index / straight_steps, -radius))
    result = []
    for x, y in local:
        east = (x + middle_x) * u[0] + (y + middle_y) * v[0]
        north = (x + middle_x) * u[1] + (y + middle_y) * v[1]
        point = GEODESIC.Direct(latitude, longitude, math.degrees(math.atan2(east, north)), math.hypot(east, north))
        result.append((round(point['lon2'], 9), round(point['lat2'], 9)))
    result.append(result[0])
    route = Route('足球场四角生成的跑道', tuple(result), {
        'source': '用户选择的足球场四角与参数化跑道估算',
        'estimated': True,
        'generator': 'football_pitch_stadium_v1',
        'football_corners': [list(point) for point in corners],
        'field_length_m': round(field_length, 3),
        'field_width_m': round(field_width, 3),
        'straight_length_m': round(2 * half_straight, 3),
        'bend_radius_m': round(radius, 3),
        'clearance_m': clearance,
        'end_inset_m': inset,
        'geometry_note': '根据足球场四角拟合，两条直道与两段半圆组成的估算轨迹；不是实测跑道，不保证为标准400米。',
    })
    return route.feature()
