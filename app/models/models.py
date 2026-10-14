import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry
from app.core.database import Base

class Drone(Base):
    __tablename__ = "drones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True)
    model: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="idle")  # idle, in_flight, maintenance
    last_lat: Mapped[float] = mapped_column(Float, nullable=True)
    last_lon: Mapped[float] = mapped_column(Float, nullable=True)
    last_altitude: Mapped[float] = mapped_column(Float, nullable=True)
    last_telemetry_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    flights = relationship("Flight", back_populates="drone")

class RestrictedZone(Base):
    __tablename__ = "restricted_zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    zone_type: Mapped[str] = mapped_column(String(50))  # permanent, temporary, reserved
    geometry = mapped_column(Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False))
    lower_limit_m: Mapped[float] = mapped_column(Float, default=0)
    upper_limit_m: Mapped[float] = mapped_column(Float, default=10000)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(100), default="manual")  # manual, api, bulletin
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Flight(Base):
    __tablename__ = "flights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drones.id"))
    route_geometry = mapped_column(Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=False,))
    route_waypoints: Mapped[dict] = mapped_column(JSONB)  # [{lat, lon, alt}, ...]
    status: Mapped[str] = mapped_column(String(50), default="planned")  # planned, approved, in_progress, completed, rejected
    verification_result: Mapped[dict] = mapped_column(JSONB, nullable=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    actual_start: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    actual_end: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    drone = relationship("Drone", back_populates="flights")

class FlightLog(Base):
    __tablename__ = "flight_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flights.id"))
    event_type: Mapped[str] = mapped_column(String(50))  # takeoff, landing, waypoint_reached, conflict_detected
    message: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)
    altitude: Mapped[float] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)