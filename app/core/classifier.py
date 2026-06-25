"""
Ядро классификации типовых неисправностей.

Гибридный подход:
1. Нормализация текста (русский + английский).
2. Ключевое совпадение (Jaccard по ключевым словам + симптомам).
3. Нечёткое сравнение (rapidfuzz).
4. Триграммное перекрытие (ngram overlap).
5. Опционально — простая векторная модель (numpy) или embeddings.

Результат — уверенность в диапазоне [0, 1].
"""

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from rapidfuzz import fuzz

from app.core.catalog import CatalogIndex, FaultRecord, catalog_registry
from app.core.config import settings
from app.core.models import ClassifyRequest, ClassifyResponse, FaultMatch, ScoringWeights


def _normalize(text: str) -> str:
    """Простая, но эффективная нормализация для русского текста."""
    if not text:
        return ""
    text = text.lower()
    allowed = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяabcdefghijklmnopqrstuvwxyz0123456789 ")
    cleaned = "".join(ch if ch in allowed else " " for ch in text)
    return " ".join(cleaned.split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _token_set(text: str) -> set[str]:
    return set(text.split())


def _trigrams(text: str) -> set[str]:
    """Строит множество триграмм для нечёткого лексического сходства."""
    text = text.replace(" ", "_")
    if len(text) < 3:
        return {text} if text else set()
    return {text[i : i + 3] for i in range(len(text) - 2)}


def _trigram_overlap(a: str, b: str) -> float:
    ta, tb = _trigrams(a), _trigrams(b)
    return _jaccard(ta, tb)


@dataclass
class ScoredFault:
    fault: FaultRecord
    score: float
    reasons: list[str]


class HybridScorer:
    """Гибридный скорер с настраиваемыми весами."""

    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self.w_kw = weights.keyword if weights and weights.keyword is not None else settings.weight_keyword
        self.w_fz = weights.fuzzy if weights and weights.fuzzy is not None else settings.weight_fuzzy
        self.w_tri = weights.trigram if weights and weights.trigram is not None else settings.weight_trigram
        self.w_emb = weights.embedding if weights and weights.embedding is not None else settings.weight_embedding

        total = self.w_kw + self.w_fz + self.w_tri + self.w_emb
        if total > 0:
            self.w_kw /= total
            self.w_fz /= total
            self.w_tri /= total
            self.w_emb /= total

    @property
    def weight_dict(self) -> dict[str, float]:
        return {
            "keyword": round(self.w_kw, 4),
            "fuzzy": round(self.w_fz, 4),
            "trigram": round(self.w_tri, 4),
            "embedding": round(self.w_emb, 4),
        }

    def score(self, context: str, fault: FaultRecord) -> tuple[float, list[str]]:
        """Возвращает (confidence, список причин)."""
        ctx = _normalize(context)
        ctx_tokens = _token_set(ctx)

        reasons: list[str] = []
        kw_score = _jaccard(ctx_tokens, _token_set(fault._search_text))
        if kw_score > 0.15:
            reasons.append(f"keyword:jaccard={kw_score:.2f}")

        fz_title = fuzz.partial_ratio(ctx, fault.title) / 100.0
        fz_desc = fuzz.partial_ratio(ctx, fault.description) / 100.0
        fz_sym = max(
            (fuzz.partial_ratio(ctx, s) / 100.0 for s in fault.symptoms), default=0.0
        )
        fz_score = max(fz_title, fz_desc, fz_sym)
        if fz_score > 0.55:
            reasons.append(f"fuzzy={fz_score:.2f}")

        tri_score = _trigram_overlap(ctx, fault._search_text)
        if tri_score > 0.12:
            reasons.append(f"trigram={tri_score:.2f}")

        emb_score = 0.0
        if self.w_emb > 0.01:
            emb_score = self._simple_embedding_score(ctx, fault)
            if emb_score > 0.4:
                reasons.append(f"embedding={emb_score:.2f}")

        final = (
            self.w_kw * kw_score
            + self.w_fz * fz_score
            + self.w_tri * tri_score
            + self.w_emb * emb_score
        )
        final = min(1.0, final * 1.15)

        return round(final, 4), reasons

    def _simple_embedding_score(self, ctx: str, fault: FaultRecord) -> float:
        """Очень лёгкая векторная модель без внешних моделей."""
        all_tokens = list(_token_set(ctx) | _token_set(fault._search_text))
        if not all_tokens:
            return 0.0

        vocab = {t: i for i, t in enumerate(all_tokens)}
        v_ctx = np.zeros(len(vocab))
        v_f = np.zeros(len(vocab))

        for t in _token_set(ctx):
            if t in vocab:
                v_ctx[vocab[t]] += 1
        for t in _token_set(fault._search_text):
            if t in vocab:
                v_f[vocab[t]] += 1

        dot = np.dot(v_ctx, v_f)
        n1 = np.linalg.norm(v_ctx)
        n2 = np.linalg.norm(v_f)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(dot / (n1 * n2))


class ClassifierEngine:
    """Основной сервис классификации."""

    def classify(self, request: ClassifyRequest) -> ClassifyResponse:
        start = time.perf_counter()

        catalog_name = request.catalog.lower().strip()
        index: CatalogIndex | None = catalog_registry.get(catalog_name)

        context_text = _normalize(request.resolved_context_text())
        if len(context_text) > settings.max_context_length:
            context_text = context_text[: settings.max_context_length]

        if index is None:
            return ClassifyResponse(
                catalog=request.catalog,
                context=context_text,
                matches=[],
                total_candidates=0,
            )

        scorer = HybridScorer(request.weights)
        top_k = request.top_k or settings.default_top_k
        min_conf = request.min_confidence or settings.default_min_confidence

        scored: list[ScoredFault] = []
        for fault in index.faults:
            conf, reasons = scorer.score(context_text, fault)
            if conf >= min_conf:
                scored.append(ScoredFault(fault=fault, score=conf, reasons=reasons))

        scored.sort(key=lambda x: x.score, reverse=True)
        top = scored[:top_k]

        matches = [
            FaultMatch(
                code=s.fault.code,
                title=s.fault.title,
                description=s.fault.description,
                category=s.fault.category,
                confidence=s.score,
                matched_reasons=s.reasons if request.include_scoring_details else s.reasons,
                recommended_actions=s.fault.recommended_actions,
            )
            for s in top
        ]

        elapsed = (time.perf_counter() - start) * 1000

        return ClassifyResponse(
            catalog=request.catalog,
            context=context_text,
            matches=matches,
            total_candidates=len(index.faults),
            processing_time_ms=round(elapsed, 2),
            scoring_weights=scorer.weight_dict if request.include_scoring_details else None,
        )

    def get_faults_for_catalog(self, name: str) -> list[dict[str, Any]]:
        idx = catalog_registry.get(name.lower())
        if not idx:
            return []
        return [
            {
                "code": f.code,
                "title": f.title,
                "description": f.description,
                "symptoms": f.symptoms,
                "keywords": f.keywords,
                "category": f.category,
                "recommended_actions": f.recommended_actions,
            }
            for f in idx.faults
        ]


engine = ClassifierEngine()