"""
Наполнение базы тестовыми данными:
- 10 БВС разного класса и статуса
- 4 зоны ограничения полётов
- 3 демонстрационных полётных задания
- события журнала для наглядности
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="scripts.seed_data")
import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, func

from app.core.database import async_session, engine, Base
from app.models.models import Drone, RestrictedZone, Flight, FlightLog
from app.services.verification import RouteVerifier


# ============================================================
# ПАРК БВС (10 аппаратов)
# ============================================================
DRONES_DATA = [
    {
        "name": "БВС-01 «Орлан»",
        "serial_number": "ORL-001",
        "model": "Орлан-10",
        "status": "in_flight",
        "last_lat": 55.7558,
        "last_lon": 37.6173,
        "last_altitude": 340.0,
    },
    {
        "name": "БВС-02 «Форпост»",
        "serial_number": "FRP-002",
        "model": "Форпост-Р",
        "status": "in_flight",
        "last_lat": 55.7620,
        "last_lon": 37.6350,
        "last_altitude": 480.0,
    },
    {
        "name": "БВС-03 «Гранат»",
        "serial_number": "GRN-003",
        "model": "Гранат-4",
        "status": "idle",
        "last_lat": 55.7400,
        "last_lon": 37.6000,
        "last_altitude": 0.0,
    },
    {
        "name": "БВС-04 «ЗаALA»",
        "serial_number": "ZAL-004",
        "model": "ZALA 421-16E",
        "status": "idle",
        "last_lat": 55.7480,
        "last_lon": 37.5800,
        "last_altitude": 0.0,
    },
    {
        "name": "БВС-05 «Supercam»",
        "serial_number": "SPC-005",
        "model": "Supercam S350",
        "status": "in_flight",
        "last_lat": 55.7700,
        "last_lon": 37.6500,
        "last_altitude": 220.0,
    },
    {
        "name": "БВС-06 «DJI Matrice»",
        "serial_number": "DJM-006",
        "model": "DJI Matrice 300 RTK",
        "status": "idle",
        "last_lat": 55.7520,
        "last_lon": 37.6100,
        "last_altitude": 0.0,
    },
    {
        "name": "БВС-07 «Геоскан»",
        "serial_number": "GSK-007",
        "model": "Геоскан 201",
        "status": "maintenance",
        "last_lat": 55.7450,
        "last_lon": 37.5950,
        "last_altitude": 0.0,
    },
    {
        "name": "БВС-08 «Autel EVO»",
        "serial_number": "ATE-008",
        "model": "Autel EVO II Pro",
        "status": "idle",
        "last_lat": 55.7580,
        "last_lon": 37.6300,
        "last_altitude": 0.0,
    },
    {
        "name": "БВС-09 «WingtraOne»",
        "serial_number": "WGT-009",
        "model": "WingtraOne Gen II",
        "status": "maintenance",
        "last_lat": 55.7350,
        "last_lon": 37.5700,
        "last_altitude": 0.0,
    },
    {
        "name": "БВС-10 «Альтиус»",
        "serial_number": "ALT-010",
        "model": "Альтиус-У",
        "status": "in_flight",
        "last_lat": 55.7650,
        "last_lon": 37.6000,
        "last_altitude": 1250.0,
    },
]


# ============================================================
# ЗОНЫ ОГРАНИЧЕНИЯ
# ============================================================
ZONES_DATA = [
    {
        "name": "Зона №1 — вокруг аэропорта Шереметьево",
        "zone_type": "permanent",
        "geometry": "SRID=4326;POLYGON((37.35 55.95, 37.50 55.95, 37.50 56.02, 37.35 56.02, 37.35 55.95))",
        "lower_limit_m": 0,
        "upper_limit_m": 3000,
        "description": "Постоянная запретная зона вокруг аэропорта",
    },
    {
        "name": "Зона №2 — центр Москвы (Кремль)",
        "zone_type": "permanent",
        "geometry": "SRID=4326;POLYGON((37.60 55.745, 37.63 55.745, 37.63 55.760, 37.60 55.760, 37.60 55.745))",
        "lower_limit_m": 0,
        "upper_limit_m": 2000,
        "description": "Зона ограничения полётов над центром",
    },
    {
        "name": "Зона №3 — временная (учения МЧС)",
        "zone_type": "temporary",
        "geometry": "SRID=4326;POLYGON((37.70 55.75, 37.78 55.75, 37.78 55.80, 37.70 55.80, 37.70 55.75))",
        "lower_limit_m": 0,
        "upper_limit_m": 600,
        "description": "Временная зона на период учений",
        "valid_from": datetime.utcnow() - timedelta(days=1),
        "valid_until": datetime.utcnow() + timedelta(days=7),
    },
    {
        "name": "Зона №4 — резервная (VIP-полёты)",
        "zone_type": "reserved",
        "geometry": "SRID=4326;POLYGON((37.55 55.68, 37.62 55.68, 37.62 55.72, 37.55 55.72, 37.55 55.68))",
        "lower_limit_m": 300,
        "upper_limit_m": 1500,
        "description": "Резервная зона для правительственных полётов",
    },
]


# ============================================================
# ДЕМОНСТРАЦИОННЫЕ ПОЛЁТЫ
# ============================================================
def build_flight_route(waypoints):
    """WKT LineString из списка точек."""
    pairs = ", ".join(f"{wp['lon']} {wp['lat']}" for wp in waypoints)
    return f"SRID=4326;LINESTRING({pairs})"


FLIGHTS_DATA = [
    {
        "drone_serial": "ORL-001",
        "waypoints": [
            {"lat": 55.740, "lon": 37.550, "alt": 300},
            {"lat": 55.755, "lon": 37.600, "alt": 320},
            {"lat": 55.765, "lon": 37.640, "alt": 340},
        ],
        "status": "in_progress",
        "scheduled_start": datetime.utcnow() - timedelta(hours=1),
        "scheduled_end": datetime.utcnow() + timedelta(hours=1),
        "actual_start": datetime.utcnow() - timedelta(minutes=45),
        "notes": "Плановый облёт северного сектора",
    },
    {
        "drone_serial": "FRP-002",
        "waypoints": [
            {"lat": 55.755, "lon": 37.610, "alt": 480},
            {"lat": 55.760, "lon": 37.620, "alt": 480},
            {"lat": 55.765, "lon": 37.635, "alt": 480},
        ],
        "status": "in_progress",
        "scheduled_start": datetime.utcnow() - timedelta(minutes=30),
        "scheduled_end": datetime.utcnow() + timedelta(minutes=30),
        "actual_start": datetime.utcnow() - timedelta(minutes=25),
        "notes": "Мониторинг транспортного узла",
    },
    {
        "drone_serial": "ALT-010",
        "waypoints": [
            {"lat": 55.740, "lon": 37.560, "alt": 1200},
            {"lat": 55.760, "lon": 37.600, "alt": 1250},
            {"lat": 55.780, "lon": 37.620, "alt": 1250},
        ],
        "status": "in_progress",
        "scheduled_start": datetime.utcnow() - timedelta(minutes=20),
        "scheduled_end": datetime.utcnow() + timedelta(hours=2),
        "actual_start": datetime.utcnow() - timedelta(minutes=15),
        "notes": "Высотный патруль",
    },
    {
        "drone_serial": "GRN-003",
        "waypoints": [
            {"lat": 55.740, "lon": 37.590, "alt": 150},
            {"lat": 55.745, "lon": 37.605, "alt": 150},
        ],
        "status": "completed",
        "scheduled_start": datetime.utcnow() - timedelta(days=1),
        "scheduled_end": datetime.utcnow() - timedelta(days=1) + timedelta(hours=1),
        "actual_start": datetime.utcnow() - timedelta(days=1),
        "actual_end": datetime.utcnow() - timedelta(days=1) + timedelta(minutes=50),
        "notes": "Завершённый полёт — учебный",
    },
    {
        "drone_serial": "SPC-005",
        "waypoints": [
            {"lat": 55.765, "lon": 37.640, "alt": 220},
            {"lat": 55.772, "lon": 37.660, "alt": 220},
            {"lat": 55.778, "lon": 37.680, "alt": 220},
        ],
        "status": "approved",
        "scheduled_start": datetime.utcnow() + timedelta(hours=2),
        "scheduled_end": datetime.utcnow() + timedelta(hours=3),
        "notes": "Запланированный вылет",
    },
]


# ============================================================
# СЦЕНАРИЙ НАПОЛНЕНИЯ
# ============================================================
async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # --- 1. Проверка: если дроны уже есть, не дублируем ---
        existing = await session.scalar(select(func.count(Drone.id)))
        if existing and existing > 0:
            print(f"⚠️  В базе уже {existing} БВС. Пропускаем seed.")
            print("   Для пересоздания: DELETE FROM flights, drones, restricted_zones CASCADE;")
            return

        # --- 2. Дроны ---
        drones_by_serial = {}
        for d in DRONES_DATA:
            drone = Drone(**d, last_telemetry_at=datetime.utcnow())
            session.add(drone)
            drones_by_serial[d["serial_number"]] = drone
        await session.flush()
        print(f"✅ Добавлено БВС: {len(DRONES_DATA)}")

        # --- 3. Зоны ограничения ---
        for z in ZONES_DATA:
            session.add(RestrictedZone(source="seed", **z))
        await session.flush()
        print(f"✅ Добавлено зон: {len(ZONES_DATA)}")

        # --- 4. Загрузка зон для верификации ---
        zones_result = await session.execute(select(RestrictedZone))
        zones = zones_result.scalars().all()
        zones_for_verify = []
        for z in zones:
            from geoalchemy2.shape import to_shape
            shape = to_shape(z.geometry)
            zones_for_verify.append({
                "id": str(z.id),
                "name": z.name,
                "zone_type": z.zone_type,
                "lower_limit_m": z.lower_limit_m,
                "upper_limit_m": z.upper_limit_m,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[list(pt) for pt in shape.exterior.coords]],
                },
            })

        verifier = RouteVerifier()

        # --- 5. Полёты ---
        for f in FLIGHTS_DATA:
            drone = drones_by_serial[f["drone_serial"]]
            waypoints = f["waypoints"]

            # Верификация
            verification = verifier.check_route_conflicts(
                waypoints, zones_for_verify,
                altitude_m=waypoints[0]["alt"],
            )

            flight = Flight(
                drone_id=drone.id,
                route_geometry=build_flight_route(waypoints),
                route_waypoints=waypoints,
                status=f["status"],
                verification_result=verification,
                scheduled_start=f.get("scheduled_start"),
                scheduled_end=f.get("scheduled_end"),
                actual_start=f.get("actual_start"),
                actual_end=f.get("actual_end"),
                notes=f.get("notes"),
            )
            session.add(flight)
            await session.flush()

            # --- 6. События для каждого полёта ---
            session.add(FlightLog(
                flight_id=flight.id,
                event_type="verification",
                message=(
                    f"Верификация: {'успешно' if verification['is_valid'] else 'конфликты'}; "
                    f"зон проверено: {verification['total_zones_checked']}"
                ),
                timestamp=flight.scheduled_start or datetime.utcnow(),
            ))

            if f["status"] in ("in_progress", "completed"):
                session.add(FlightLog(
                    flight_id=flight.id,
                    event_type="status_change",
                    message="Взлёт разрешён, полёт начат",
                    lat=waypoints[0]["lat"],
                    lon=waypoints[0]["lon"],
                    altitude=waypoints[0]["alt"],
                    timestamp=f.get("actual_start") or datetime.utcnow(),
                ))
                # Промежуточные точки
                for i, wp in enumerate(waypoints[1:-1], start=2):
                    session.add(FlightLog(
                        flight_id=flight.id,
                        event_type="waypoint_reached",
                        message=f"Достигнута путевая точка №{i}",
                        lat=wp["lat"], lon=wp["lon"], altitude=wp["alt"],
                        timestamp=(f.get("actual_start") or datetime.utcnow())
                                  + timedelta(minutes=10 * i),
                    ))

            if f["status"] == "completed":
                session.add(FlightLog(
                    flight_id=flight.id,
                    event_type="status_change",
                    message="Полёт завершён, посадка выполнена",
                    lat=waypoints[-1]["lat"],
                    lon=waypoints[-1]["lon"],
                    altitude=0,
                    timestamp=f.get("actual_end") or datetime.utcnow(),
                ))

        await session.commit()

        # --- 7. Итог ---
        total_drones = await session.scalar(select(func.count(Drone.id)))
        total_zones = await session.scalar(select(func.count(RestrictedZone.id)))
        total_flights = await session.scalar(select(func.count(Flight.id)))
        total_logs = await session.scalar(select(func.count(FlightLog.id)))

        print("=" * 55)
        print("📊 Итог наполнения:")
        print(f"   БВС:           {total_drones}")
        print(f"   Зон:           {total_zones}")
        print(f"   Полётов:       {total_flights}")
        print(f"   Событий в лог: {total_logs}")
        print("=" * 55)


if __name__ == "__main__":
    asyncio.run(seed())