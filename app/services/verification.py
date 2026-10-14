"""
Модуль автоматической верификации маршрута по зонам ограничения полётов.
Работает и с dict, и с Pydantic-объектами (Waypoint).
"""
from shapely.geometry import LineString, Polygon
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def _get(obj, key, default=None):
    """Универсальный доступ: и к dict, и к объекту с атрибутами."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class RouteVerifier:
    """Верификатор маршрутов БВС."""

    def __init__(self):
        pass

    def build_route_line(self, waypoints: List[Any]) -> LineString:
        """LineString из списка точек (dict или объект с .lat/.lon)."""
        coords = [(_get(wp, "lon"), _get(wp, "lat")) for wp in waypoints]
        return LineString(coords)

    def build_zone_polygon(self, coordinates: List[List[float]]) -> Polygon:
        """Polygon из GeoJSON-подобных координат."""
        return Polygon(coordinates[0])

    def check_route_conflicts(
        self,
        route_waypoints: List[Any],
        restricted_zones: List[Dict[str, Any]],
        altitude_m: float = 100.0,
    ) -> Dict[str, Any]:
        """
        Проверка маршрута на пересечение с зонами ограничения.
        """
        if not route_waypoints or len(route_waypoints) < 2:
            return {
                "is_valid": False,
                "error": "Нужно минимум 2 путевые точки",
                "conflicts": [],
                "critical_count": 0,
                "total_zones_checked": 0,
                "route_length_m": 0.0,
                "flight_altitude_m": altitude_m,
            }

        route_line = self.build_route_line(route_waypoints)
        conflicts: List[Dict[str, Any]] = []
        zones_checked = 0

        for zone in restricted_zones:
            zones_checked += 1
            try:
                coords = zone["geometry"]["coordinates"]
                zone_poly = self.build_zone_polygon(coords)
                lower = zone.get("lower_limit_m", 0)
                upper = zone.get("upper_limit_m", 10000)

                if route_line.intersects(zone_poly):
                    if lower <= altitude_m <= upper:
                        intersection = route_line.intersection(zone_poly)
                        conflicts.append({
                            "zone_id": zone.get("id"),
                            "zone_name": zone["name"],
                            "zone_type": zone.get("zone_type", "unknown"),
                            "intersection_geometry": intersection.wkt,
                            "severity": "critical",
                            "message": (
                                f"Маршрут пересекает зону «{zone['name']}» "
                                f"на высоте {altitude_m} м "
                                f"(разрешённый диапазон: {lower}–{upper} м)"
                            ),
                        })
                        logger.warning(
                            f"Конфликт: маршрут пересекает «{zone['name']}»"
                        )
                    else:
                        conflicts.append({
                            "zone_id": zone.get("id"),
                            "zone_name": zone["name"],
                            "zone_type": zone.get("zone_type", "unknown"),
                            "severity": "info",
                            "message": (
                                f"Маршрут проходит над/под зоной «{zone['name']}», "
                                f"но высота {altitude_m} м вне диапазона "
                                f"{lower}–{upper} м"
                            ),
                        })
            except Exception as e:
                logger.error(f"Ошибка проверки зоны {zone.get('name')}: {e}")
                continue

        critical = [c for c in conflicts if c["severity"] == "critical"]

        # Длина в метрах (грубая оценка через градусы → ~111 км на градус)
        try:
            route_length_m = route_line.length * 111_000
        except Exception:
            route_length_m = 0.0

        return {
            "is_valid": len(critical) == 0,
            "conflicts": conflicts,
            "critical_count": len(critical),
            "total_zones_checked": zones_checked,
            "route_length_m": route_length_m,
            "flight_altitude_m": altitude_m,
        }

    def suggest_avoidance(
        self, route_waypoints, restricted_zones, altitude_m
    ) -> Dict[str, Any]:
        result = self.check_route_conflicts(
            route_waypoints, restricted_zones, altitude_m
        )
        if result["is_valid"]:
            return {"action": "none", "message": "Маршрут безопасен"}
        return {
            "action": "reroute_needed",
            "message": (
                f"Обнаружено {result['critical_count']} критических конфликтов. "
                f"Рекомендуется изменить маршрут или высоту полёта."
            ),
            "conflicts": [
                c for c in result["conflicts"] if c["severity"] == "critical"
            ],
        }