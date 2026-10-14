"""Юнит-тесты модуля верификации маршрутов."""
import pytest
from app.services.verification import RouteVerifier


@pytest.fixture
def verifier():
    return RouteVerifier()


@pytest.fixture
def square_zone():
    """Квадратная зона вокруг (55.75, 37.61)-(55.76, 37.63)."""
    return {
        "id": "zone-1",
        "name": "Тестовая зона",
        "zone_type": "permanent",
        "lower_limit_m": 0,
        "upper_limit_m": 500,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [37.61, 55.75],
                [37.63, 55.75],
                [37.63, 55.76],
                [37.61, 55.76],
                [37.61, 55.75],
            ]],
        },
    }


def test_route_fully_outside_zone(verifier, square_zone):
    """Маршрут полностью вне зоны — конфликтов нет."""
    waypoints = [
        {"lat": 55.70, "lon": 37.50, "alt": 100},
        {"lat": 55.71, "lon": 37.55, "alt": 100},
    ]
    result = verifier.check_route_conflicts(waypoints, [square_zone], altitude=100)
    assert result["is_valid"] is True
    assert result["critical_count"] == 0
    assert result["total_zones_checked"] == 1


def test_route_crosses_zone(verifier, square_zone):
    """Маршрут проходит сквозь зону на запрещённой высоте — конфликт."""
    waypoints = [
        {"lat": 55.755, "lon": 37.60, "alt": 200},  # западнее зоны
        {"lat": 55.755, "lon": 37.64, "alt": 200},  # восточнее зоны
    ]
    result = verifier.check_route_conflicts(waypoints, [square_zone], altitude=200)
    assert result["is_valid"] is False
    assert result["critical_count"] == 1
    assert result["conflicts"][0]["severity"] == "critical"


def test_route_above_zone_but_altitude_too_high(verifier, square_zone):
    """Маршрут по горизонтали пересекает зону, но летит выше верхней границы."""
    waypoints = [
        {"lat": 55.755, "lon": 37.60, "alt": 1000},
        {"lat": 55.755, "lon": 37.64, "alt": 1000},
    ]
    result = verifier.check_route_conflicts(waypoints, [square_zone], altitude=1000)
    assert result["is_valid"] is True  # критических нет
    assert result["critical_count"] == 0
    # Но должен быть информационный конфликт
    assert any(c["severity"] == "info" for c in result["conflicts"])


def test_route_below_zone_min_altitude(verifier, square_zone):
    """Маршрут пересекает зону, но высота ниже нижней границы."""
    zone = dict(square_zone)
    zone["lower_limit_m"] = 300
    waypoints = [
        {"lat": 55.755, "lon": 37.60, "alt": 100},
        {"lat": 55.755, "lon": 37.64, "alt": 100},
    ]
    result = verifier.check_route_conflicts(waypoints, [zone], altitude=100)
    assert result["is_valid"] is True
    assert result["critical_count"] == 0


def test_route_touches_zone_boundary(verifier, square_zone):
    """Маршрут касается границы зоны — считается пересечением."""
    waypoints = [
        {"lat": 55.75, "lon": 37.60, "alt": 100},  # на границе
        {"lat": 55.75, "lon": 37.65, "alt": 100},
    ]
    result = verifier.check_route_conflicts(waypoints, [square_zone], altitude=100)
    # Shapely считает касание пересечением — критический конфликт
    assert result["critical_count"] >= 1


def test_empty_waypoints(verifier, square_zone):
    """Маршрут из менее чем 2 точек — ошибка."""
    result = verifier.check_route_conflicts([], [square_zone], altitude=100)
    assert result["is_valid"] is False
    assert "error" in result


def test_single_waypoint(verifier, square_zone):
    """Маршрут из одной точки — ошибка."""
    result = verifier.check_route_conflicts(
        [{"lat": 55.75, "lon": 37.62, "alt": 100}], [square_zone], altitude=100
    )
    assert result["is_valid"] is False


def test_no_zones(verifier):
    """Нет зон — маршрут всегда безопасен."""
    waypoints = [
        {"lat": 55.75, "lon": 37.60, "alt": 100},
        {"lat": 55.76, "lon": 37.65, "alt": 100},
    ]
    result = verifier.check_route_conflicts(waypoints, [], altitude=100)
    assert result["is_valid"] is True
    assert result["total_zones_checked"] == 0


def test_multiple_zones_mixed(verifier, square_zone):
    """Несколько зон: одна конфликтует, вторая — нет."""
    far_zone = {
        "id": "zone-2",
        "name": "Далёкая зона",
        "zone_type": "temporary",
        "lower_limit_m": 0,
        "upper_limit_m": 1000,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [37.80, 55.80], [37.82, 55.80],
                [37.82, 55.82], [37.80, 55.82],
                [37.80, 55.80],
            ]],
        },
    }
    waypoints = [
        {"lat": 55.755, "lon": 37.60, "alt": 200},
        {"lat": 55.755, "lon": 37.64, "alt": 200},
    ]
    result = verifier.check_route_conflicts(waypoints, [square_zone, far_zone], altitude=200)
    assert result["is_valid"] is False
    assert result["critical_count"] == 1
    assert result["total_zones_checked"] == 2


def test_avoidance_suggestion(verifier, square_zone):
    """Рекомендация по обходу при конфликте."""
    waypoints = [
        {"lat": 55.755, "lon": 37.60, "alt": 200},
        {"lat": 55.755, "lon": 37.64, "alt": 200},
    ]
    result = verifier.suggest_avoidance(waypoints, [square_zone], 200)
    assert result["action"] == "reroute_needed"
    assert len(result["conflicts"]) >= 1


def test_avoidance_no_conflict(verifier):
    """Рекомендация при отсутствии конфликта — none."""
    waypoints = [
        {"lat": 55.60, "lon": 37.30, "alt": 100},
        {"lat": 55.61, "lon": 37.35, "alt": 100},
    ]
    result = verifier.suggest_avoidance(waypoints, [], 100)
    assert result["action"] == "none"


def test_route_length_calculation(verifier):
    """Проверка расчёта длины маршрута."""
    waypoints = [
        {"lat": 55.75, "lon": 37.60, "alt": 100},
        {"lat": 55.75, "lon": 37.70, "alt": 100},
    ]
    result = verifier.check_route_conflicts(waypoints, [], altitude=100)
    # ~6.3 км на этой широте
    assert 5000 < result["route_length_m"] < 8000