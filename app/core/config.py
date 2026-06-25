"""
Конфигурация сервиса классификации.

Использует pydantic-settings для чтения переменных окружения
и .env файлов. Все настройки имеют разумные значения по умолчанию
для работы "из коробки".
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Основные настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- База данных ---
    database_url: str = "sqlite:///./data/classifier.db"

    # --- Данные справочников ---
    seed_dir: Path = Path(__file__).parent.parent.parent / "data" / "catalogs"

    # --- Классификация ---
    default_top_k: int = 5
    default_min_confidence: float = 0.25
    max_context_length: int = 8000

    # Веса гибридного скорера (можно переопределять через ENV)
    weight_keyword: float = 0.35
    weight_fuzzy: float = 0.40
    weight_trigram: float = 0.25
    weight_embedding: float = 0.0

    enable_embeddings: bool = False
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Аудит ---
    enable_classification_logging: bool = True
    history_max_entries: int = 100

    # --- Очистка ПД (локальная CPU-модель) ---
    enable_pd_cleaning: bool = True
    enable_pd_cleaning_log: bool = True
    pd_model_version: str = "pd-cpu-v1"
    training_export_dir: Path = Path(__file__).parent.parent.parent / "data" / "training"

    # --- Сервер ---
    app_title: str = "Unhexx Classifier"
    app_version: str = "0.3.0"
    app_description: str = (
        "Унифицированный сервис классификации с предварительной очисткой контекста "
        "от персональных данных локальной CPU-моделью. "
        "Интерфейс контролёра для проверки очистки ПД и дообучения модели."
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


settings = Settings()

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
(settings.seed_dir).mkdir(parents=True, exist_ok=True)