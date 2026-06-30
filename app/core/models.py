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
    profile: str | None = Field(None, description="Наименование профиля весов")
    include_scoring_details: bool = Field(
        False, description="Включить детали скоринга в ответ (для отладки)"
    )
    skip_pd_cleaning: bool = Field(
        False, description="Пропустить очистку ПД (только для отладки в доверенной среде)"
    )
    presumed_typical_malfunction: str | None = Field(
        None, description="Предполагаемая типовая неисправность (от контролёра или initial guess)"
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
    failure_mode: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    matched_reasons: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class PdEntityRead(BaseModel):
    """Обнаруженная сущность ПД."""

    entity_type: str
    original: str
    replacement: str
    start: int
    end: int
    confidence: float = 1.0


class PdCleanRequest(BaseModel):
    """Запрос на предпросмотр очистки ПД."""

    text: str = Field(..., min_length=1)
    save_log: bool = Field(True, description="Сохранить в журнал очистки")


class PdCleanResponse(BaseModel):
    """Результат очистки ПД."""

    original_text: str
    cleaned_text: str
    entities: list[PdEntityRead]
    entity_count: int
    processing_time_ms: float
    model_version: str


class ClassifyResponse(BaseModel):
    """Ответ классификатора."""

    catalog: str
    context: str
    original_context: str | None = None
    pd_entities: list[PdEntityRead] = Field(default_factory=list)
    pd_cleaning_applied: bool = False
    matches: list[FaultMatch]
    total_candidates: int
    processing_time_ms: float | None = None
    scoring_time_ms: float | None = None
    pd_cleaning_time_ms: float | None = None
    scoring_weights: dict[str, float] | None = None
    profile_used: str | None = Field(None, description="Использованный профиль весов")
    typical_malfunction: str | None = Field(None, description="Определённая типовая неисправность (по классификатору)")
    presumed_typical_malfunction: str | None = Field(None, description="Предполагаемая типовая неисправность")


class FaultRead(BaseModel):
    """Полное представление неисправности (для просмотра справочника)."""

    code: str
    title: str
    description: str
    symptoms: list[str]
    keywords: list[str]
    category: str | None = None
    failure_mode: str | None = None
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
    failure_mode: str | None = None
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
    failure_mode: str | None = None
    recommended_actions: list[str] | None = None
    meta: dict[str, Any] | None = None


class CatalogInfo(BaseModel):
    """Краткая информация о справочнике."""

    name: str
    version: str
    description: str | None = None
    fault_count: int


class HistoryEntry(BaseModel):
    """Запись журнала классификаций (расширенная для live UI)."""

    id: int
    catalog_name: str
    context: str
    original_context: str | None = None
    pd_entities: list[dict[str, Any]] = Field(default_factory=list)
    top_matches: list[dict[str, Any]]
    top_confidence: float | None = None
    processing_time_ms: float | None = None
    created_at: str


class FeedbackCreate(BaseModel):
    """Обратная связь контролёра по ошибке очистки ПД."""

    original_text: str = Field(..., min_length=1)
    model_output: str = Field(..., min_length=1)
    corrected_text: str = Field(..., min_length=1)
    entity_type: str | None = Field(None, description="Тип ПД: email, phone, fio, ...")
    missed_fragment: str | None = Field(None, description="Фрагмент, пропущенный моделью")
    controller_notes: str | None = None


class FeedbackEntry(BaseModel):
    """Запись обратной связи."""

    id: int
    original_text: str
    model_output: str
    corrected_text: str
    entity_type: str | None = None
    missed_fragment: str | None = None
    controller_notes: str | None = None
    status: str
    created_at: str


class TrainingExportResponse(BaseModel):
    """Результат экспорта данных для дообучения."""

    export_path: str
    feedback_count: int
    learned_patterns_count: int
    lines: list[str]


class ConfigResponse(BaseModel):
    """Публичная конфигурация сервиса."""

    version: str
    default_top_k: int
    default_min_confidence: float
    scoring_weights: dict[str, float]
    enable_classification_logging: bool
    enable_pd_cleaning: bool
    pd_model_version: str
    max_context_length: int