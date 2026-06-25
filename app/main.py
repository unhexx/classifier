"""
Точка входа FastAPI сервиса.

Здесь происходит:
- инициализация БД
- загрузка справочников из сидов
- построение индексов
- регистрация маршрутов
"""

from contextlib import asynccontextmanager
from typing import Any

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
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
def classify(request: ClassifyRequest, db: Session = Depends(get_db)) -> ClassifyResponse:
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
    return result


@app.get("/api/v1/history", response_model=list[HistoryEntry], tags=["classification"])
def classification_history(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[HistoryEntry]:
    """Последние записи журнала классификаций."""
    return get_classification_history(db, limit=limit)


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