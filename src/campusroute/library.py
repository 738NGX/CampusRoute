from pathlib import Path
import threading
from uuid import uuid4

import geojson

from campusroute.routes import Route, RoutePath, route_from_feature
from campusroute.storage import write_json


class RouteLibrary:
    def __init__(self, root: Path):
        self.path = root / 'user-routes' / 'routes.geojson'
        self.lock = threading.RLock()
        self.session_routes = []

    def available(self):
        with self.lock:
            return self.load() + list(self.session_routes)

    def load(self):
        with self.lock:
            if not self.path.exists():
                return []
            with self.path.open(encoding='utf-8') as handle:
                collection = geojson.load(handle)
            if not isinstance(collection, geojson.FeatureCollection):
                raise ValueError('路线收藏需要采用 GeoJSON FeatureCollection 格式。')
            routes = [route_from_feature(feature) for feature in collection.features]
            identifiers = [route.properties.get('local_id') for route in routes]
            if any(not isinstance(value, str) or not value for value in identifiers) or len(set(identifiers)) != len(routes):
                raise ValueError('路线收藏的标识缺失或重复。')
            for route in routes:
                RoutePath(route)
            return routes

    @staticmethod
    def route_properties(route):
        return {key: value for key, value in route.feature().properties.items()
                if key not in ('local_id', 'id', 'order', 'session_only')}

    def save(self, route: Route, persist=True):
        if type(persist) is not bool:
            raise ValueError('路线保存开关必须为布尔值。')
        RoutePath(route)
        properties = self.route_properties(route)
        with self.lock:
            routes = self.load()
            for saved in routes:
                if saved.coordinates == route.coordinates and self.route_properties(saved) == properties:
                    return saved
            temporary = next((item for item in self.session_routes
                              if item.coordinates == route.coordinates and self.route_properties(item) == properties), None)
            if not persist:
                if temporary is not None:
                    return temporary
                temporary = Route(route.name, route.coordinates,
                                  {**properties, 'local_id': uuid4().hex, 'session_only': True})
                self.session_routes.append(temporary)
                return temporary
            identifier = temporary.properties['local_id'] if temporary is not None else uuid4().hex
            saved = Route(route.name, route.coordinates, {**properties, 'local_id': identifier})
            routes.append(saved)
            write_json(self.path, geojson.FeatureCollection([item.feature() for item in routes]))
            self.session_routes = [item for item in self.session_routes if item != temporary]
            return saved
