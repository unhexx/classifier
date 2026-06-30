"""
Реестр каталогов и построение быстрых индексов в памяти.

После загрузки из БД все неисправности одного каталога держатся
в памяти для молниеносной классификации.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FaultRecord:
    """Лёгкая копия неисправности для скоринга (без ORM)."""

    code: str
    title: str
    description: str
    symptoms: list[str]
    keywords: list[str]
    category: str | None
    failure_mode: str | None
    recommended_actions: list[str]
    # Полный текст для fuzzy (кешируем)
    _search_text: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        parts = [self.title, self.description] + self.symptoms + self.keywords
        if self.failure_mode:
            parts.append(self.failure_mode)
        if self.category:
            parts.append(self.category)
        self._search_text = " ".join(parts).lower()


@dataclass
class CatalogIndex:
    """Индекс одного справочника."""

    name: str
    version: str
    faults: list[FaultRecord] = field(default_factory=list)
    # Быстрый доступ по коду
    by_code: dict[str, FaultRecord] = field(default_factory=dict)


class CatalogRegistry:
    """
    Глобальный реестр загруженных каталогов.

    Строит индексы один раз при старте сервиса.
    """

    def __init__(self) -> None:
        self._catalogs: dict[str, CatalogIndex] = {}
        self.embedding_engine: Optional[Any] = None
        self._embeddings_precomputed: bool = False

    def load_from_db(self, db) -> None:
        """Загружает все каталоги и строит индексы."""
        import logging
        from app.core.config import settings
        from app.core.embeddings import create_embedding_engine_from_settings

        logger = logging.getLogger(__name__)

        self._catalogs.clear()
        self._embeddings_precomputed = False

        from app.db.models import Catalog
        from app.db.models import Fault as FaultORM

        catalogs = db.query(Catalog).all()
        for cat in catalogs:
            faults_orm = db.query(FaultORM).filter(FaultORM.catalog_name == cat.name).all()
            records: list[FaultRecord] = []
            by_code: dict[str, FaultRecord] = {}

            for f in faults_orm:
                rec = FaultRecord(
                    code=f.code,
                    title=f.title,
                    description=f.description,
                    symptoms=f.symptoms or [],
                    keywords=f.keywords or [],
                    category=f.category,
                    failure_mode=f.failure_mode,
                    recommended_actions=f.recommended_actions or [],
                )
                records.append(rec)
                by_code[rec.code] = rec

            index = CatalogIndex(
                name=cat.name, version=cat.version, faults=records, by_code=by_code
            )
            self._catalogs[cat.name] = index

        # TASK-011: Initialize and precompute embeddings
        try:
            if settings.enable_embeddings:
                self.embedding_engine = create_embedding_engine_from_settings(settings)
                all_records = []
                for idx in self._catalogs.values():
                    all_records.extend(idx.faults)
                if all_records:
                    self.embedding_engine.precompute_catalog(all_records)
                    self._embeddings_precomputed = True
                    logger.info("Embedding precomputation completed for all catalogs")
        except Exception as e:
            logger.warning(f"Embedding initialization skipped or failed: {e}")

    def get(self, name: str) -> CatalogIndex | None:
        return self._catalogs.get(name.lower())

    def list_catalogs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": idx.name,
                "version": idx.version,
                "fault_count": len(idx.faults),
            }
            for idx in self._catalogs.values()
        ]

    @property
    def names(self) -> list[str]:
        return list(self._catalogs.keys())

    def get_embedding_engine(self) -> Optional[Any]:
        return self.embedding_engine

    @property
    def embeddings_ready(self) -> bool:
        return self._embeddings_precomputed and self.embedding_engine is not None


# Глобальный экземпляр (инициализируется в lifespan)
catalog_registry = CatalogRegistry()
