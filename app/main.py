"""
Точка входа FastAPI сервиса.

Здесь происходит:
- инициализация БД
- загрузка справочников из сидов
- построение индексов
- регистрация маршрутов
"""

from contextlib import asynccontextmanager
from typing import Any, List

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.v1.admin import router as admin_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.pd import router as pd_router
from app.core.catalog import catalog_registry
from app.core.classifier import engine
from app.core.config import settings
from app.core.models import (
    CatalogInfo,
    ClassifyRequest,
    ClassifyResponse,
    ConfigResponse,
    FaultRead,
    HistoryEntry,
)
from app.db.seeds import ensure_catalogs_loaded
from app.db.session import SessionLocal, get_db, init_db
from app.services.classify_service import classify_context, get_classification_history

from collections import deque
import time
from typing import Any, Dict, List


class ConnectionManager:
    """Simple WebSocket connection manager for live events (classifications, etc.)."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast JSON message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # client probably disconnected
                self.disconnect(connection)


manager = ConnectionManager()


class LiveStats:
    """In-memory live metrics collector for UI dashboard + WS pushes (lightweight, no DB on hotpath)."""
    def __init__(self):
        self.classifications: int = 0
        self.pd_cleaned_total: int = 0
        self.total_processing_ms: float = 0.0
        self.recent_ts: deque[float] = deque(maxlen=200)  # timestamps for rolling rate (last ~minutes)
        self.catalog_counts: Dict[str, int] = {}
        self.pd_type_counts: Dict[str, int] = {}
        self.ws_connections: int = 0

    def record_classification(self, catalog: str, processing_ms: float | None, pd_entities: list[dict] | None):
        self.classifications += 1
        ts = time.time()
        self.recent_ts.append(ts)
        if catalog:
            self.catalog_counts[catalog] = self.catalog_counts.get(catalog, 0) + 1
        if processing_ms:
            self.total_processing_ms += float(processing_ms)
        for e in (pd_entities or []):
            t = e.get("entity_type") or "unknown"
            self.pd_type_counts[t] = self.pd_type_counts.get(t, 0) + 1

    def record_pd_clean(self, count: int):
        self.pd_cleaned_total += max(0, int(count or 0))

    def get_rolling_rate_per_min(self) -> float:
        if not self.recent_ts:
            return 0.0
        now = time.time()
        # count events in last 60s
        window = 60.0
        recent = [t for t in self.recent_ts if now - t <= window]
        # rate per minute
        return round(len(recent) * (60.0 / window) if recent else 0.0, 1)

    def get_avg_processing_ms(self) -> float:
        if self.classifications == 0:
            return 0.0
        return round(self.total_processing_ms / self.classifications, 1)

    def snapshot(self) -> dict:
        return {
            "classifications": self.classifications,
            "pd_cleaned": self.pd_cleaned_total,
            "rate_per_min": self.get_rolling_rate_per_min(),
            "avg_processing_ms": self.get_avg_processing_ms(),
            "catalog_counts": dict(self.catalog_counts),
            "pd_type_counts": dict(self.pd_type_counts),
            "ws_clients": self.ws_connections,
        }


live_stats = LiveStats()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: подготовка при старте."""
    print("Инициализация базы данных...")
    init_db()

    with SessionLocal() as db:
        added = ensure_catalogs_loaded(db)
        if added:
            print(f"Добавлены/обновлены неисправности: {added}")

        print("Построение индексов каталогов...")
        catalog_registry.load_from_db(db)

    print(f"Готово. Доступные справочники: {catalog_registry.names}")
    yield
    print("Завершение работы сервиса.")


app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
    lifespan=lifespan,
)

app.include_router(admin_router)
app.include_router(pd_router)
app.include_router(feedback_router)

_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/ui", tags=["ui"], include_in_schema=False)
def controller_ui():
    """Интерфейс контролёра для проверки очистки ПД и дообучения."""
    ui_path = Path(__file__).parent / "static" / "ui.html"
    return FileResponse(ui_path)


@app.get("/health", tags=["system"])
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": settings.app_version,
        "catalogs": catalog_registry.names,
        "pd_cleaning_enabled": settings.enable_pd_cleaning,
        "pd_model_version": settings.pd_model_version,
    }


@app.get("/api/v1/config", response_model=ConfigResponse, tags=["system"])
def get_config() -> ConfigResponse:
    """Публичная конфигурация сервиса и весов скорера."""
    return ConfigResponse(
        version=settings.app_version,
        default_top_k=settings.default_top_k,
        default_min_confidence=settings.default_min_confidence,
        scoring_weights={
            "keyword": settings.weight_keyword,
            "fuzzy": settings.weight_fuzzy,
            "trigram": settings.weight_trigram,
            "embedding": settings.weight_embedding,
        },
        enable_classification_logging=settings.enable_classification_logging,
        enable_pd_cleaning=settings.enable_pd_cleaning,
        pd_model_version=settings.pd_model_version,
        max_context_length=settings.max_context_length,
    )


@app.post("/api/v1/classify", response_model=ClassifyResponse, tags=["classification"])
async def classify(request: ClassifyRequest, db: Session = Depends(get_db)) -> ClassifyResponse:
    """Основной метод классификации."""
    if not catalog_registry.get(request.catalog):
        catalog_registry.load_from_db(db)

    context_text = request.resolved_context_text().strip()
    if len(context_text) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Контекст слишком короткий (минимум 3 символа после нормализации)",
        )

    result = classify_context(db, request)
    if result.total_candidates == 0 and catalog_registry.get(request.catalog) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Справочник '{request.catalog}' не найден. "
            f"Доступные: {catalog_registry.names}",
        )

    # Record live metrics (non blocking)
    try:
        pd_list = [e.model_dump() for e in result.pd_entities] if result.pd_entities else []
        live_stats.record_classification(
            catalog=result.catalog,
            processing_ms=result.processing_time_ms,
            pd_entities=pd_list
        )
        live_stats.record_pd_clean(len(pd_list))
    except Exception:
        pass

    # Broadcast live event for connected UIs - rich payload for instant UI update + metrics delta
    try:
        top = result.matches[0] if result.matches else None
        pd_list = [e.model_dump() for e in result.pd_entities] if result.pd_entities else []
        payload = {
            "type": "new_classification",
            "data": {
                "catalog": result.catalog,
                "catalog_name": result.catalog,
                "context": result.context,
                "original_context": result.original_context,
                "pd_entities": pd_list,
                "typical_malfunction": result.typical_malfunction,
                "presumed_typical_malfunction": result.presumed_typical_malfunction,
                "top_matches": [m.model_dump() for m in result.matches] if result.matches else [],
                "top_confidence": top.confidence if top else None,
                "processing_time_ms": result.processing_time_ms,
                "pd_count": len(pd_list),
                "timestamp": None,
            }
        }
        await manager.broadcast(payload)
        # also push updated metrics snapshot
        await manager.broadcast({"type": "metrics_update", "data": live_stats.snapshot()})
    except Exception:
        pass  # non-blocking for UI live updates

    return result


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket for live events (new classifications, etc.). Clients receive JSON pushes."""
    await manager.connect(websocket)
    live_stats.ws_connections = len(manager.active_connections)
    # push initial metrics snapshot on connect
    try:
        await websocket.send_json({"type": "metrics_update", "data": live_stats.snapshot()})
    except Exception:
        pass
    try:
        # Keep connection alive; clients can send pings if needed
        while True:
            await websocket.receive_text()  # simple keepalive
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        live_stats.ws_connections = len(manager.active_connections)


@app.get("/api/v1/history", response_model=list[HistoryEntry], tags=["classification"])
def classification_history(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[HistoryEntry]:
    """Последние записи журнала классификаций (расширенные для UI)."""
    return get_classification_history(db, limit=limit)


@app.get("/api/v1/metrics", tags=["system"])
def get_live_metrics() -> dict:
    """Текущие live метрики (для начальной загрузки UI и polling fallback)."""
    return live_stats.snapshot()


@app.get("/api/v1/catalogs", response_model=list[CatalogInfo], tags=["catalogs"])
def list_catalogs() -> list[CatalogInfo]:
    """Список доступных справочников."""
    raw = catalog_registry.list_catalogs()
    return [CatalogInfo(**c) for c in raw]


@app.get(
    "/api/v1/catalogs/{name}/faults",
    response_model=list[FaultRead],
    tags=["catalogs"],
)
def get_catalog_faults(name: str) -> list[FaultRead]:
    """Возвращает все неисправности из указанного справочника."""
    faults = engine.get_faults_for_catalog(name)
    if not faults:
        raise HTTPException(
            status_code=404,
            detail=f"Справочник '{name}' не найден или пуст.",
        )
    return [FaultRead(**f) for f in faults]


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Ошибка валидации запроса",
            "errors": jsonable_encoder(exc.errors()),
        },
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Ошибка валидации данных", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервиса", "error": str(exc)},
    )