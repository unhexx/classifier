"""
Локальная CPU-модель очистки персональных данных (ПД).

Работает полностью на CPU без обращения к внешним сервисам.
Комбинирует базовые паттерны и дообученные правила из обратной связи контролёра.
"""

import re
import time
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class PdEntity:
    """Обнаруженная сущность персональных данных."""

    entity_type: str
    original: str
    replacement: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class PdCleaningResult:
    """Результат очистки контекста от ПД."""

    original_text: str
    cleaned_text: str
    entities: list[PdEntity] = field(default_factory=list)
    processing_time_ms: float = 0.0
    model_version: str = "pd-cpu-v1"


class LocalPdCleaner:
    """
    Локальная модель очистки ПД на CPU.

    Использует детерминированные паттерны + дообученные правила.
    """

    BASE_PATTERNS: ClassVar[list[tuple[str, str, str, float]]] = [
        # (entity_type, regex, replacement, confidence)
        ("email", r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "[EMAIL]", 0.98),
        ("phone", r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b", "[PHONE]", 0.95),
        ("phone", r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{4}\b", "[PHONE]", 0.85),
        ("snils", r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}\b", "[SNILS]", 0.92),
        ("passport", r"\b\d{2}[\s]?\d{2}[\s]?\d{6}\b", "[PASSPORT]", 0.90),
        ("inn", r"\b\d{10}\b", "[INN]", 0.80),
        ("inn", r"\b\d{12}\b", "[INN]", 0.80),
        ("ip", r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP]", 0.88),
        ("card", r"\b(?:\d{4}[\s\-]?){3}\d{4}\b", "[CARD]", 0.93),
        (
            "fio",
            r"\b[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2}\b",
            "[FIO]",
            0.75,
        ),
        (
            "fio",
            r"\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.",
            "[FIO]",
            0.80,
        ),
        (
            "address",
            r"\b(?:ул\.|улица|пр\.|проспект|пер\.|переулок|д\.|дом|кв\.|квартира)\s+[\wА-Яа-яё\-\d\s,.]+",
            "[ADDRESS]",
            0.70,
        ),
    ]

    def __init__(self) -> None:
        self._learned_patterns: list[tuple[str, str, str, float]] = []

    def load_learned_patterns(self, patterns: list[tuple[str, str, str, float]]) -> None:
        """Загружает дообученные паттерны из БД."""
        self._learned_patterns = patterns

    @property
    def all_patterns(self) -> list[tuple[str, str, str, float]]:
        return self._learned_patterns + self.BASE_PATTERNS

    def clean(self, text: str) -> PdCleaningResult:
        """Очищает текст от ПД, возвращая результат с детализацией."""
        start = time.perf_counter()
        if not text:
            return PdCleaningResult(original_text="", cleaned_text="")

        entities: list[PdEntity] = []
        for entity_type, pattern, replacement, confidence in self.all_patterns:
            # ФИО ищем только с заглавной буквы (без IGNORECASE)
            flags = 0 if entity_type == "fio" else re.IGNORECASE
            for match in re.finditer(pattern, text, flags):
                entities.append(
                    PdEntity(
                        entity_type=entity_type,
                        original=match.group(),
                        replacement=replacement,
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence,
                    )
                )

        # Убираем перекрытия — оставляем более длинные совпадения
        entities.sort(key=lambda e: (e.start, -(e.end - e.start)))
        filtered: list[PdEntity] = []
        last_end = -1
        for ent in entities:
            if ent.start >= last_end:
                filtered.append(ent)
                last_end = ent.end

        # Замена справа налево, чтобы не сбивать индексы
        cleaned = text
        for ent in sorted(filtered, key=lambda e: e.start, reverse=True):
            cleaned = cleaned[: ent.start] + ent.replacement + cleaned[ent.end :]

        elapsed = (time.perf_counter() - start) * 1000
        return PdCleaningResult(
            original_text=text,
            cleaned_text=cleaned,
            entities=filtered,
            processing_time_ms=round(elapsed, 2),
        )


# Глобальный экземпляр
pd_cleaner = LocalPdCleaner()