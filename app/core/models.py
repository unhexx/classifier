"""
Pydantic модели (схемы) для API и внутреннего использования.

Все ответы и запросы строго типизированы.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class StructuredContext(BaseModel):
    """Структурированный контекст проблемы (опционально)."""

    description: str | None = Field(None, description="Общее описание")
    symptoms: list[str] = Field(default_factory=list, description="Список симптомов")
    device: str | None = Field(None, description="Тип или модель устройства")
    observed: str | None = Field(None, description="Наблюдаемое поведение / метрики")

    def to_text(self) -> str:
        """Собирает единый текст для скоринга."""
        parts: list[str] = []
        if self.description:
            parts.append(self.description)
        if self.device:
            parts.append(f"устройство: {self.device}")
        if self.observed:
            parts.append(f"наблюдается: {self.observed}")
        parts.extend(self.symptoms)
        return " ".join(parts).strip()


class ScoringWeights(BaseModel):
    """Веса гибридного скорера (опционально на запрос)."""

    keyword: float | None = Field(None, ge=0.0, le=1.0)
    fuzzy: float | None = Field(None, ge=0.0, le=1.0)
    trigram: float | None = Field(None, ge=0.0, le=1.0)
    embedding: float | None = Field(None, ge=0.0, le=1.0)


class ClassifyRequest(BaseModel):
    """Запрос на классификацию."""

    catalog: str = Field(..., description="Наименование справочника (например: servers, network)")
    context: str | list[str] | StructuredContext | None = Field(
        None, description="Описание проблемы / симптомы / контекст"
    )
    top_k: int | None = Field(None, ge=1, le=20, description="Сколько результатов вернуть")
    min_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Минимальная уверенность для включения в результат"
    )
    weights: ScoringWeights | None = Field(None, description="Переопределение весов скорера")
    include_scoring_details: bool = Field(
        False, description="Включить детали скоринга в ответ (для отладки)"
    )

    @model_validator(mode="after")
    def validate_context_present(self) -> "ClassifyRequest":
        if self.context is None:
            raise ValueError("Необходимо указать context (строка, список или StructuredContext)")
        return self

    def resolved_context_text(self) -> str:
        """Нормализует контекст в единую строку."""
        ctx = self.context
        if ctx is None:
            return ""
        if isinstance(ctx, StructuredContext):
            return ctx.to_text()
        if isinstance(ctx, list):
            return " ".join(str(item).strip() for item in ctx if str(item).strip())
        return str(ctx).strip()


class FaultMatch(BaseModel):
    """Одна найденная типовая неисправность с объяснением совпадения."""

    code: str
    title: str
    description: str
    category: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    matched_reasons: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class ClassifyResponse(BaseModel):
    """Ответ классификатора."""

    catalog: str
    context: str
    matches: list[FaultMatch]
    total_candidates: int
    processing_time_ms: float | None = None
    scoring_weights: dict[str, float] | None = None


class FaultRead(BaseModel):
    """Полное представление неисправности (для просмотра справочника)."""

    code: str
    title: str
    description: str
    symptoms: list[str]
    keywords: list[str]
    category: str | None = None
    recommended_actions: list[str]
    meta: dict[str, Any] | None = None


class FaultCreate(BaseModel):
    """Создание новой неисправности в справочнике."""

    code: str = Field(..., min_length=3, max_length=32)
    title: str = Field(..., min_length=3)
    description: str = Field(..., min_length=5)
    symptoms: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    category: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    meta: dict[str, Any] | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()


class FaultUpdate(BaseModel):
    """Обновление существующей неисправности."""

    title: str | None = None
    description: str | None = None
    symptoms: list[str] | None = None
    keywords: list[str] | None = None
    category: str | None = None
    recommended_actions: list[str] | None = None
    meta: dict[str, Any] | None = None


class CatalogInfo(BaseModel):
    """Краткая информация о справочнике."""

    name: str
    version: str
    description: str | None = None
    fault_count: int


class HistoryEntry(BaseModel):
    """Запись журнала классификаций."""

    id: int
    catalog_name: str
    context: str
    top_matches: list[dict[str, Any]]
    top_confidence: float | None = None
    processing_time_ms: float | None = None
    created_at: str


class ConfigResponse(BaseModel):
    """Публичная конфигурация сервиса."""

    version: str
    default_top_k: int
    default_min_confidence: float
    scoring_weights: dict[str, float]
    enable_classification_logging: bool
    max_context_length: int