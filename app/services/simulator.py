"""
Симулятор движения БВС по активным полётным заданиям.
"""
import asyncio
from datetime import datetime, timezone
from typing import Callable, Awaitable
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.models import Drone, Flight, FlightLog


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FlightSimulator:
    STEP_DEG = 0.0003
    ALT_SMOOTHING = 0.15

    def __init__(
        self,
        interval: float = 2.0,
        on_update: Callable[[list[dict]], Awaitable[None]] | None = None,
    ):
        self.interval = interval
        self.on_update = on_update
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"[Simulator] запущен, интервал {self.interval}s")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[Simulator] остановлен")

    async def _loop(self):
        while self._running:
            try:
                await self._step()
            except Exception as e:
                logger.exception(f"[Simulator] ошибка тика: {e}")
            await asyncio.sleep(self.interval)

    async def _step(self):
        async with async_session() as session:
            flights_res = await session.execute(
                select(Flight).where(Flight.status == "in_progress")
            )
            flights = flights_res.scalars().all()
            if not flights:
                return

            updated_drones: list[dict] = []

            for flight in flights:
                drone_res = await session.execute(
                    select(Drone).where(Drone.id == flight.drone_id)
                )
                drone = drone_res.scalar_one_or_none()
                if not drone:
                    continue

                waypoints = flight.route_waypoints or []
                if not waypoints:
                    continue

                if drone.last_lat is None or drone.last_lon is None:
                    wp0 = waypoints[0]
                    drone.last_lat = wp0["lat"]
                    drone.last_lon = wp0["lon"]
                    drone.last_altitude = wp0.get("alt", 100)
                    drone.last_telemetry_at = utcnow_naive()

                next_idx = self._next_waypoint_index(drone, waypoints)

                if next_idx is None:
                    await self._finish_flight(session, flight, drone)
                    updated_drones.append(self._to_dict(drone))
                    continue

                target = waypoints[next_idx]
                await self._move_towards(session, flight, drone, target, next_idx)
                updated_drones.append(self._to_dict(drone))

            await session.commit()

            if updated_drones and self.on_update:
                try:
                    await self.on_update(updated_drones)
                except Exception as e:
                    logger.error(f"[Simulator] ошибка broadcast: {e}")

    def _next_waypoint_index(self, drone: Drone, waypoints: list[dict]) -> int | None:
        for i, wp in enumerate(waypoints):
            d = ((wp["lat"] - drone.last_lat) ** 2
                 + (wp["lon"] - drone.last_lon) ** 2) ** 0.5
            if d > self.STEP_DEG:
                return i
        return None

    async def _move_towards(
        self,
        session: AsyncSession,
        flight: Flight,
        drone: Drone,
        target: dict,
        target_idx: int,
    ):
        dlat = target["lat"] - drone.last_lat
        dlon = target["lon"] - drone.last_lon
        dist = (dlat ** 2 + dlon ** 2) ** 0.5

        if dist <= self.STEP_DEG:
            drone.last_lat = target["lat"]
            drone.last_lon = target["lon"]
            if target.get("alt") is not None:
                drone.last_altitude = target["alt"]

            session.add(FlightLog(
                flight_id=flight.id,
                event_type="waypoint_reached",
                message=f"Достигнута путевая точка №{target_idx + 1}",
                lat=target["lat"],
                lon=target["lon"],
                altitude=target.get("alt"),
                timestamp=utcnow_naive(),
            ))
            logger.info(f"[Simulator] {drone.name}: точка №{target_idx + 1}")
        else:
            drone.last_lat += dlat / dist * self.STEP_DEG
            drone.last_lon += dlon / dist * self.STEP_DEG
            if target.get("alt") is not None:
                target_alt = target["alt"]
                drone.last_altitude = (
                    drone.last_altitude
                    + (target_alt - drone.last_altitude) * self.ALT_SMOOTHING
                )

        drone.last_telemetry_at = utcnow_naive()

    async def _finish_flight(
        self, session: AsyncSession, flight: Flight, drone: Drone
    ):
        flight.status = "completed"
        flight.actual_end = utcnow_naive()
        drone.status = "idle"
        drone.last_altitude = 0.0

        session.add(FlightLog(
            flight_id=flight.id,
            event_type="status_change",
            message="Полёт завершён, посадка выполнена",
            lat=drone.last_lat,
            lon=drone.last_lon,
            altitude=0.0,
            timestamp=utcnow_naive(),
        ))
        logger.info(f"[Simulator] {drone.name}: полёт завершён")

    def _to_dict(self, drone: Drone) -> dict:
        return {
            "drone_id": str(drone.id),
            "drone_name": drone.name,
            "lat": drone.last_lat,
            "lon": drone.last_lon,
            "altitude": drone.last_altitude,
            "status": drone.status,
        }