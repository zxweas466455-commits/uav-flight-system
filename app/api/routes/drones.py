from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from uuid import UUID

from app.core.database import get_db
from app.models.models import Drone, Flight, FlightLog
from app.schemas.schemas import DroneCreate, DroneResponse, DroneUpdate

router = APIRouter(prefix="/drones", tags=["drones"])


@router.get("", response_model=list[DroneResponse])
async def list_drones(
    status: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Список всех БВС с фильтром по статусу."""
    query = select(Drone).order_by(Drone.name)
    if status:
        query = query.where(Drone.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=DroneResponse, status_code=201)
async def create_drone(data: DroneCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация нового БВС в парке."""
    # Проверка уникальности серийного номера
    exists = await db.execute(
        select(Drone).where(Drone.serial_number == data.serial_number)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(400, "БВС с таким серийным номером уже зарегистрирован")

    drone = Drone(
        name=data.name,
        serial_number=data.serial_number,
        model=data.model,
        status="idle"
    )
    db.add(drone)
    await db.commit()
    await db.refresh(drone)
    return drone


@router.get("/{drone_id}", response_model=DroneResponse)
async def get_drone(drone_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Drone).where(Drone.id == drone_id))
    drone = result.scalar_one_or_none()
    if not drone:
        raise HTTPException(404, "БВС не найден")
    return drone


@router.patch("/{drone_id}", response_model=DroneResponse)
async def update_drone(
    drone_id: UUID,
    data: DroneUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновление данных БВС (в т.ч. телеметрии)."""
    result = await db.execute(select(Drone).where(Drone.id == drone_id))
    drone = result.scalar_one_or_none()
    if not drone:
        raise HTTPException(404, "БВС не найден")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(drone, field, value)

    if data.last_lat is not None and data.last_lon is not None:
        drone.last_telemetry_at = datetime.utcnow()

    await db.commit()
    await db.refresh(drone)
    return drone


@router.post("/{drone_id}/telemetry", response_model=DroneResponse)
async def push_telemetry(
    drone_id: UUID,
    lat: float,
    lon: float,
    altitude: float,
    db: AsyncSession = Depends(get_db)
):
    """Приём телеметрии от БВС (заглушка для реального канала связи)."""
    result = await db.execute(select(Drone).where(Drone.id == drone_id))
    drone = result.scalar_one_or_none()
    if not drone:
        raise HTTPException(404, "БВС не найден")

    drone.last_lat = lat
    drone.last_lon = lon
    drone.last_altitude = altitude
    drone.last_telemetry_at = datetime.utcnow()

    # Если БВС в полёте — пишем в лог активного полёта
    active_flight = await db.execute(
        select(Flight)
        .where(Flight.drone_id == drone_id, Flight.status == "in_progress")
        .order_by(Flight.actual_start.desc())
        .limit(1)
    )
    flight = active_flight.scalar_one_or_none()
    if flight:
        log = FlightLog(
            flight_id=flight.id,
            event_type="telemetry",
            message=f"Телеметрия: {lat:.5f}, {lon:.5f}, {altitude} м",
            lat=lat, lon=lon, altitude=altitude
        )
        db.add(log)

    await db.commit()
    await db.refresh(drone)
    return drone


@router.delete("/{drone_id}", status_code=204)
async def delete_drone(drone_id: UUID, db: AsyncSession = Depends(get_db)):
    """Снятие БВС с учёта (только если нет активных полётов)."""
    result = await db.execute(select(Drone).where(Drone.id == drone_id))
    drone = result.scalar_one_or_none()
    if not drone:
        raise HTTPException(404, "БВС не найден")

    active = await db.execute(
        select(Flight).where(
            Flight.drone_id == drone_id,
            Flight.status.in_(["planned", "approved", "in_progress"])
        )
    )
    if active.scalars().first():
        raise HTTPException(400, "Нельзя удалить БВС с активными полётами")

    await db.delete(drone)
    await db.commit()