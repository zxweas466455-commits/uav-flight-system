from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.models import Drone, Flight, FlightLog

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/status")
async def fleet_status(db: AsyncSession = Depends(get_db)):
    """Общий статус парка БВС для панели мониторинга."""
    total = await db.scalar(select(func.count(Drone.id)))
    by_status_result = await db.execute(
        select(Drone.status, func.count(Drone.id)).group_by(Drone.status)
    )
    by_status = {row[0]: row[1] for row in by_status_result.all()}

    active_flights_result = await db.execute(
        select(Flight).where(Flight.status == "in_progress")
    )
    active_flights = active_flights_result.scalars().all()

    return {
        "total_drones": total or 0,
        "by_status": by_status,
        "active_flights_count": len(active_flights),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/live")
async def live_positions(db: AsyncSession = Depends(get_db)):
    """Текущие координаты всех БВС в полёте (для карты)."""
    result = await db.execute(
        select(Drone).where(Drone.status == "in_flight")
    )
    drones = result.scalars().all()

    # Информация об активном полёте для каждого БВС
    payload = []
    for d in drones:
        flight_result = await db.execute(
            select(Flight)
            .where(Flight.drone_id == d.id, Flight.status == "in_progress")
            .order_by(Flight.actual_start.desc())
            .limit(1)
        )
        flight = flight_result.scalar_one_or_none()
        payload.append({
            "drone_id": str(d.id),
            "drone_name": d.name,
            "lat": d.last_lat,
            "lon": d.last_lon,
            "altitude": d.last_altitude,
            "last_telemetry_at": d.last_telemetry_at.isoformat() if d.last_telemetry_at else None,
            "flight_id": str(flight.id) if flight else None,
            "flight_status": flight.status if flight else None,
        })
    return payload


@router.get("/events")
async def recent_events(
    limit: int = 50,
    minutes: int = 60,
    db: AsyncSession = Depends(get_db)
):
    """Последние события из журнала (последние N минут)."""
    since = datetime.utcnow() - timedelta(minutes=minutes)
    result = await db.execute(
        select(FlightLog)
        .where(FlightLog.timestamp >= since)
        .order_by(FlightLog.timestamp.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "flight_id": str(log.flight_id),
            "event_type": log.event_type,
            "message": log.message,
            "lat": log.lat,
            "lon": log.lon,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ]


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Проверка живости сервиса и связи с БД."""
    try:
        await db.execute(select(1))
        return {"status": "ok", "db": "connected", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"status": "error", "db": "disconnected", "error": str(e)}