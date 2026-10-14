"""Утилиты для геопространственных расчётов."""
import math
from typing import Iterable

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками в метрах (формула гаверсинуса)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def route_length_m(waypoints: Iterable[dict]) -> float:
    """Суммарная длина маршрута по списку waypoints [{'lat', 'lon', ...}]."""
    pts = list(waypoints)
    total = 0.0
    for a, b in zip(pts, pts[1:]):
        total += haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    return total


def bounding_box(waypoints: Iterable[dict]) -> dict:
    """Минимальный охватывающий прямоугольник маршрута."""
    pts = list(waypoints)
    if not pts:
        return {}
    lats = [p["lat"] for p in pts]
    lons = [p["lon"] for p in pts]
    return {
        "min_lat": min(lats), "max_lat": max(lats),
        "min_lon": min(lons), "max_lon": max(lons),
    }


def interpolate_waypoints(waypoints: list[dict], step_m: float = 100.0) -> list[dict]:
    """Разбиение маршрута на точки с заданным шагом (для плотной проверки)."""
    if len(waypoints) < 2:
        return waypoints
    result = [waypoints[0]]
    for a, b in zip(waypoints, waypoints[1:]):
        seg_len = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        if seg_len <= step_m:
            result.append(b)
            continue
        n = int(seg_len // step_m)
        for i in range(1, n + 1):
            t = i / (n + 1)
            result.append({
                "lat": a["lat"] + (b["lat"] - a["lat"]) * t,
                "lon": a["lon"] + (b["lon"] - a["lon"]) * t,
                "alt": a.get("alt", 0) + (b.get("alt", 0) - a.get("alt", 0)) * t,
            })
        result.append(b)
    return result