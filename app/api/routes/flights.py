from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.models.models import Flight, Drone, RestrictedZone, FlightLog
from app.schemas.schemas import (
    FlightCreate, FlightResponse, VerificationRequest,
    VerificationResponse, FlightStatusUpdate
)
from app.services.verification import RouteVerifier
from app.services.export import JournalExporter

router = APIRouter(prefix="/flights", tags=["flights"])


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _waypoints_to_dicts(waypoints) -> list[dict]:
    """Pydantic Waypoint → dict (для верификатора и JSONB)."""
    out = []
    for wp in waypoints:
        if isinstance(wp, dict):
            out.append({"lat": wp["lat"], "lon": wp["lon"], "alt": wp.get("alt", 100)})
        else:
            out.append({"lat": wp.lat, "lon": wp.lon, "alt": wp.alt})
    return out


async def _load_zones(db: AsyncSession) -> list[dict]:
    """Активные зоны для верификатора."""
    now = _utcnow()
    query = select(RestrictedZone).where(
        (RestrictedZone.valid_from.is_(None)) | (RestrictedZone.valid_from <= now),
        (RestrictedZone.valid_until.is_(None)) | (RestrictedZone.valid_until >= now),
    )
    result = await db.execute(query)
    zones = result.scalars().all()

    from geoalchemy2.shape import to_shape

    zones_data = []
    for z in zones:
        try:
            shape = to_shape(z.geometry)
            coords = [[list(pt) for pt in shape.exterior.coords]]
            zones_data.append({
                "id": str(z.id),
                "name": z.name,
                "zone_type": z.zone_type,
                "lower_limit_m": z.lower_limit_m,
                "upper_limit_m": z.upper_limit_m,
                "geometry": {"type": "Polygon", "coordinates": coords},
            })
        except Exception:
            continue
    return zones_data


@router.post("/verify", response_model=VerificationResponse)
async def verify_route(
    request: VerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Верификация маршрута без сохранения."""
    zones_data = await _load_zones(db)
    verifier = RouteVerifier()
    waypoints_dicts = _waypoints_to_dicts(request.waypoints)
    return verifier.check_route_conflicts(
        waypoints_dicts, zones_data, request.altitude_m
    )


@router.post("", response_model=FlightResponse, status_code=201)
async def create_flight(
    data: FlightCreate,
    db: AsyncSession = Depends(get_db),
):
    """Создание полётного задания с автоматической верификацией."""
    drone_result = await db.execute(select(Drone).where(Drone.id == data.drone_id))
    drone = drone_result.scalar_one_or_none()
    if not drone:
        raise HTTPException(404, "БВС не найден")
    if drone.status == "maintenance":
        raise HTTPException(400, "БВС на обслуживании, полёт невозможен")

    waypoints_dicts = _waypoints_to_dicts(data.waypoints)

    zones_data = await _load_zones(db)
    verifier = RouteVerifier()
    verification = verifier.check_route_conflicts(
        waypoints_dicts, zones_data, data.altitude_m
    )

    coords = [(wp["lon"], wp["lat"]) for wp in waypoints_dicts]
    linestring_wkt = (
        f"SRID=4326;LINESTRING({', '.join(f'{c[0]} {c[1]}' for c in coords)})"
    )

    flight = Flight(
        drone_id=data.drone_id,
        route_geometry=linestring_wkt,
        route_waypoints=waypoints_dicts,
        status="approved" if verification["is_valid"] else "rejected",
        verification_result=verification,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        notes=data.notes,
    )
    db.add(flight)
    await db.flush()

    db.add(FlightLog(
        flight_id=flight.id,
        event_type="verification",
        message=(
            f"Верификация {'успешна' if verification['is_valid'] else 'выявила конфликты'}; "
            f"проверено зон: {verification['total_zones_checked']}, "
            f"критических: {verification['critical_count']}"
        ),
        timestamp=_utcnow(),
    ))

    await db.commit()
    await db.refresh(flight)
    return flight


@router.get("", response_model=list[FlightResponse])
async def list_flights(
    status: Optional[str] = Query(None),
    drone_id: Optional[UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Flight).order_by(Flight.created_at.desc())
    if status:
        query = query.where(Flight.status == status)
    if drone_id:
        query = query.where(Flight.drone_id == drone_id)
    if date_from:
        query = query.where(Flight.scheduled_start >= date_from)
    if date_to:
        query = query.where(Flight.scheduled_start <= date_to)
    if search:
        query = query.where(Flight.notes.ilike(f"%{search}%"))

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{flight_id}", response_model=FlightResponse)
async def get_flight(flight_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Flight).where(Flight.id == flight_id))
    flight = result.scalar_one_or_none()
    if not flight:
        raise HTTPException(404, "Полёт не найден")
    return flight


@router.patch("/{flight_id}/status", response_model=FlightResponse)
async def update_status(
    flight_id: UUID,
    data: FlightStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    allowed = {"planned", "approved", "in_progress", "completed", "rejected", "cancelled"}
    if data.status not in allowed:
        raise HTTPException(400, f"Недопустимый статус. Разрешено: {allowed}")

    result = await db.execute(select(Flight).where(Flight.id == flight_id))
    flight = result.scalar_one_or_none()
    if not flight:
        raise HTTPException(404, "Полёт не найден")

    if data.status == "in_progress" and not flight.actual_start:
        flight.actual_start = _utcnow()
    if data.status == "completed" and not flight.actual_end:
        flight.actual_end = _utcnow()

    flight.status = data.status

    drone_result = await db.execute(select(Drone).where(Drone.id == flight.drone_id))
    drone = drone_result.scalar_one_or_none()
    if drone:
        if data.status == "in_progress":
            drone.status = "in_flight"
        elif data.status in ("completed", "cancelled"):
            drone.status = "idle"

    db.add(FlightLog(
        flight_id=flight.id,
        event_type="status_change",
        message=f"Статус изменён на «{data.status}»",
        timestamp=_utcnow(),
    ))

    await db.commit()
    await db.refresh(flight)
    return flight


@router.get("/{flight_id}/logs")
async def get_flight_logs(flight_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FlightLog)
        .where(FlightLog.flight_id == flight_id)
        .order_by(FlightLog.timestamp)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "event_type": log.event_type,
            "message": log.message,
            "lat": log.lat,
            "lon": log.lon,
            "altitude": log.altitude,
            "timestamp": log.timestamp,
        }
        for log in logs
    ]


@router.get("/export/excel")
async def export_excel(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Flight).order_by(Flight.created_at.desc()))
    flights = result.scalars().all()

    drones_result = await db.execute(select(Drone))
    drones_map = {d.id: d.name for d in drones_result.scalars().all()}

    exporter = JournalExporter()
    rows = [{
        "id": f.id,
        "drone_name": drones_map.get(f.drone_id, str(f.drone_id)),
        "status": f.status,
        "scheduled_start": f.scheduled_start,
        "scheduled_end": f.scheduled_end,
        "actual_start": f.actual_start,
        "actual_end": f.actual_end,
        "verification_result": f.verification_result,
        "notes": f.notes,
    } for f in flights]

    buffer = exporter.to_excel(rows)
    filename = f"flight_journal_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/csv")
async def export_csv(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Flight).order_by(Flight.created_at.desc()))
    flights = result.scalars().all()
    drones_result = await db.execute(select(Drone))
    drones_map = {d.id: d.name for d in drones_result.scalars().all()}

    rows = [{
        "id": f.id,
        "drone_name": drones_map.get(f.drone_id, str(f.drone_id)),
        "status": f.status,
        "scheduled_start": f.scheduled_start,
        "scheduled_end": f.scheduled_end,
        "actual_start": f.actual_start,
        "actual_end": f.actual_end,
        "verification_result": f.verification_result,
        "notes": f.notes,
    } for f in flights]

    buffer = JournalExporter().to_csv(rows)
    filename = f"flight_journal_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        buffer,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )