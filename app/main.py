from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import select

from app.core.database import engine, Base, async_session
from app.core.config import get_settings
from app.api.routes import drones, flights, zones, monitoring
from app.services.simulator import FlightSimulator
from app.models.models import Drone

settings = get_settings()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WS подключён. Всего: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for c in self.active_connections:
            try:
                await c.send_json(message)
            except Exception:
                dead.append(c)
        for d in dead:
            self.disconnect(d)

    async def broadcast_telemetry(self, drones: list[dict]):
        await self.broadcast({"type": "telemetry", "data": drones})


manager = ConnectionManager()
simulator = FlightSimulator(interval=2.0, on_update=manager.broadcast_telemetry)


async def _load_live_drones() -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(Drone).where(Drone.status == "in_flight")
        )
        drones = result.scalars().all()
        return [
            {
                "drone_id": str(d.id),
                "drone_name": d.name,
                "lat": d.last_lat,
                "lon": d.last_lon,
                "altitude": d.last_altitude,
                "status": d.status,
            }
            for d in drones
            if d.last_lat is not None and d.last_lon is not None
        ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await simulator.start()
    logger.info("Приложение запущено")
    yield
    await simulator.stop()
    await engine.dispose()
    logger.info("Приложение остановлено")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(drones.router,     prefix="/api", tags=["drones"])
app.include_router(flights.router,    prefix="/api", tags=["flights"])
app.include_router(zones.router,      prefix="/api", tags=["zones"])
app.include_router(monitoring.router, prefix="/api", tags=["monitoring"])
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.websocket("/ws/monitoring")
async def websocket_monitoring(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        snapshot = await _load_live_drones()
        await websocket.send_json({"type": "telemetry", "data": snapshot})
    except Exception as e:
        logger.warning(f"Не удалось отправить снимок: {e}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/monitoring")
async def monitoring_page(request: Request):
    return templates.TemplateResponse("monitoring.html", {"request": request})


@app.get("/journal")
async def journal_page(request: Request):
    return templates.TemplateResponse("journal.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}