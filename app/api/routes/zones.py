from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime
import json

from app.core.database import get_db
from app.models.models import RestrictedZone
from app.schemas.schemas import ZoneCreate, ZoneResponse, ZoneGeoJSON

router = APIRouter(prefix="/zones", tags=["zones"])


def _polygon_wkt(coordinates: list) -> str:
    """GeoJSON Polygon → WKT для PostGIS."""
    ring = coordinates[0]
    pairs = ", ".join(f"{pt[0]} {pt[1]}" for pt in ring)
    return f"SRID=4326;POLYGON(({pairs}))"


@router.get("", response_model=list[ZoneResponse])
async def list_zones(
    zone_type: str | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Список зон ограничения полётов."""
    query = select(RestrictedZone)
    if zone_type:
        query = query.where(RestrictedZone.zone_type == zone_type)
    if active_only:
        now = datetime.utcnow()
        query = query.where(
            (RestrictedZone.valid_from.is_(None)) | (RestrictedZone.valid_from <= now),
            (RestrictedZone.valid_until.is_(None)) | (RestrictedZone.valid_until >= now),
        )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/geojson")
async def zones_geojson(db: AsyncSession = Depends(get_db)):
    """Зоны в формате GeoJSON FeatureCollection (для Leaflet)."""
    result = await db.execute(select(RestrictedZone))
    zones = result.scalars().all()

    from geoalchemy2.shape import to_shape

    features = []
    for z in zones:
        try:
            shape = to_shape(z.geometry)
            features.append({
                "type": "Feature",
                "id": str(z.id),
                "properties": {
                    "name": z.name,
                    "zone_type": z.zone_type,
                    "lower_limit_m": z.lower_limit_m,
                    "upper_limit_m": z.upper_limit_m,
                    "description": z.description,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[list(pt) for pt in shape.exterior.coords]],
                },
            })
        except Exception:
            continue

    return {"type": "FeatureCollection", "features": features}


@router.post("", response_model=ZoneResponse, status_code=201)
async def create_zone(data: ZoneCreate, db: AsyncSession = Depends(get_db)):
    """Ручное добавление зоны ограничения."""
    zone = RestrictedZone(
        name=data.name,
        zone_type=data.zone_type,
        geometry=_polygon_wkt(data.geometry["coordinates"]),
        lower_limit_m=data.lower_limit_m,
        upper_limit_m=data.upper_limit_m,
        description=data.description,
        source="manual",
        valid_from=data.valid_from,
        valid_until=data.valid_until,
    )
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    return zone


@router.post("/import/geojson", status_code=201)
async def import_geojson(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Массовый импорт зон из GeoJSON-файла."""
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "Некорректный GeoJSON")

    features = data.get("features", [])
    if not features:
        raise HTTPException(400, "Файл не содержит features")

    created = 0
    for feat in features:
        geom = feat.get("geometry", {})
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        props = feat.get("properties", {})

        try:
            zone = RestrictedZone(
                name=props.get("name", "Импортированная зона"),
                zone_type=props.get("zone_type", "temporary"),
                geometry=_polygon_wkt(
                    geom["coordinates"] if geom["type"] == "Polygon"
                    else geom["coordinates"][0]
                ),
                lower_limit_m=props.get("lower_limit_m", 0),
                upper_limit_m=props.get("upper_limit_m", 10000),
                description=props.get("description"),
                source="import",
            )
            db.add(zone)
            created += 1
        except Exception:
            continue

    await db.commit()
    return {"imported": created}


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(zone_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RestrictedZone).where(RestrictedZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(404, "Зона не найдена")
    return zone


@router.delete("/{zone_id}", status_code=204)
async def delete_zone(zone_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RestrictedZone).where(RestrictedZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(404, "Зона не найдена")
    await db.delete(zone)
    await db.commit()