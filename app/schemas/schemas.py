"""
Pydantic-схемы для валидации запросов и сериализации ответов.
"""
from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================================
# ОБЩИЕ
# ============================================================
class ORMModel(BaseModel):
    """Базовая модель с поддержкой from_attributes для ORM-объектов."""
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# WAYPOINT (путевая точка)
# ============================================================
class Waypoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Широта (WGS84)")
    lon: float = Field(..., ge=-180, le=180, description="Долгота (WGS84)")
    alt: float = Field(100.0, ge=0, le=20000, description="Высота в метрах")


# ============================================================
# ДРОНЫ (БВС)
# ============================================================
class DroneBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    serial_number: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)


class DroneCreate(DroneBase):
    """Создание нового БВС."""
    pass


class DroneUpdate(BaseModel):
    """Частичное обновление БВС (все поля опциональны)."""
    name: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, pattern="^(idle|in_flight|maintenance)$")
    last_lat: Optional[float] = Field(None, ge=-90, le=90)
    last_lon: Optional[float] = Field(None, ge=-180, le=180)
    last_altitude: Optional[float] = Field(None, ge=0, le=20000)


class DroneResponse(ORMModel):
    """Ответ API по БВС."""
    id: UUID
    name: str
    serial_number: str
    model: str
    status: str
    last_lat: Optional[float] = None
    last_lon: Optional[float] = None
    last_altitude: Optional[float] = None
    last_telemetry_at: Optional[datetime] = None
    created_at: datetime


# ============================================================
# ЗОНЫ ОГРАНИЧЕНИЯ
# ============================================================
class ZoneGeometry(BaseModel):
    """GeoJSON-геометрия зоны (только Polygon)."""
    type: str = Field("Polygon", pattern="^Polygon$")
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def check_ring(cls, v: list) -> list:
        if not v or not v[0] or len(v[0]) < 4:
            raise ValueError("Полигон должен содержать минимум 4 точки")
        # Проверка замкнутости кольца
        first, last = v[0][0], v[0][-1]
        if first != last:
            raise ValueError("Кольцо полигона должно быть замкнуто (первая = последняя точка)")
        return v


class ZoneCreate(BaseModel):
    """Создание зоны ограничения вручную."""
    name: str = Field(..., min_length=1, max_length=200)
    zone_type: str = Field("temporary", pattern="^(permanent|temporary|reserved)$")
    geometry: ZoneGeometry
    lower_limit_m: float = Field(0, ge=0, le=20000)
    upper_limit_m: float = Field(10000, ge=0, le=20000)
    description: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    @field_validator("upper_limit_m")
    @classmethod
    def check_limits(cls, v: float, info) -> float:
        lower = info.data.get("lower_limit_m", 0)
        if v <= lower:
            raise ValueError("upper_limit_m должен быть больше lower_limit_m")
        return v


class ZoneResponse(ORMModel):
    """Ответ API по зоне."""
    id: UUID
    name: str
    zone_type: str
    lower_limit_m: float
    upper_limit_m: float
    description: Optional[str] = None
    source: str
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime


class ZoneGeoJSON(BaseModel):
    """FeatureCollection для Leaflet (не сериализуем через from_attributes)."""
    type: str = "FeatureCollection"
    features: list[dict[str, Any]]


# ============================================================
# ВЕРИФИКАЦИЯ МАРШРУТА
# ============================================================
class VerificationRequest(BaseModel):
    """Запрос на верификацию маршрута."""
    waypoints: list[Waypoint] = Field(..., min_length=2, description="Минимум 2 точки")
    altitude_m: float = Field(100.0, ge=0, le=20000)

    @field_validator("waypoints")
    @classmethod
    def check_waypoints(cls, v: list) -> list:
        if len(v) < 2:
            raise ValueError("Маршрут должен содержать минимум 2 путевые точки")
        return v


class ConflictInfo(BaseModel):
    """Информация об одном конфликте маршрута с зоной."""
    zone_id: Optional[str] = None
    zone_name: str
    zone_type: str
    severity: str  # critical | info
    message: str
    intersection_geometry: Optional[str] = None


class VerificationResponse(BaseModel):
    """Результат верификации."""
    is_valid: bool
    critical_count: int = 0
    total_zones_checked: int = 0
    route_length_m: float = 0.0
    flight_altitude_m: float = 0.0
    conflicts: list[ConflictInfo] = Field(default_factory=list)
    error: Optional[str] = None


# ============================================================
# ПОЛЁТЫ
# ============================================================
class FlightCreate(BaseModel):
    """Создание полётного задания."""
    drone_id: UUID
    waypoints: list[Waypoint] = Field(..., min_length=2)
    altitude_m: float = Field(100.0, ge=0, le=20000)
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("waypoints")
    @classmethod
    def check_waypoints(cls, v: list) -> list:
        if len(v) < 2:
            raise ValueError("Маршрут должен содержать минимум 2 путевые точки")
        return v


class FlightStatusUpdate(BaseModel):
    """Изменение статуса полёта."""
    status: str = Field(
        ...,
        pattern="^(planned|approved|in_progress|completed|rejected|cancelled)$"
    )


class FlightResponse(ORMModel):
    """Ответ API по полёту."""
    id: UUID
    drone_id: UUID
    status: str
    route_waypoints: Optional[Any] = None
    verification_result: Optional[Any] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime


class FlightLogResponse(ORMModel):
    """Событие из журнала полёта."""
    id: UUID
    flight_id: UUID
    event_type: str
    message: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    altitude: Optional[float] = None
    timestamp: datetime