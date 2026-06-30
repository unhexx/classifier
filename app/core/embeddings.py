"""
app/core/embeddings.py

EmbeddingEngine for unified-classifier (CPU-only via ONNX / sentence-transformers).
Implements TASK-011.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except ImportError:
    HAS_ST = False
    logger.warning("sentence-transformers not installed. Install with: pip install 'sentence-transformers[onnx]'")

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False


_MODEL_CACHE: Dict[str, Any] = {}


class EmbeddingEngine:
    """
    CPU-friendly embedding engine with precomputation and pruning support.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        device: str = "cpu",
        use_onnx: bool = True,
        cache_dir: Optional[Path] = None,
        normalize: bool = True,
    ):
        self.model_name = model_name
        self.device = device
        self.use_onnx = use_onnx and HAS_ORT
        self.normalize = normalize
        self.cache_dir = cache_dir or Path.home() / ".cache" / "unified-classifier" / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.model: Optional[SentenceTransformer] = None
        self._dim: Optional[int] = None
        self._precomputed: Dict[str, np.ndarray] = {}

        self._load_model()

    def _load_model(self) -> None:
        if not HAS_ST:
            logger.error("sentence-transformers is required for EmbeddingEngine.")
            self.model = None
            self._dim = 384
            return

        cache_key = f"{self.model_name}_{self.device}_{self.use_onnx}"
        if cache_key in _MODEL_CACHE:
            self.model, self._dim = _MODEL_CACHE[cache_key]
            logger.info(f"Using cached embedding model: {self.model_name}")
            return

        try:
            model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=str(self.cache_dir),
            )
            if self.use_onnx and hasattr(model, "to_onnx"):
                try:
                    model = model.to_onnx()
                except Exception as e:
                    logger.info(f"ONNX optimization skipped: {e}")

            get_dim = getattr(model, "get_embedding_dimension", None)
            if callable(get_dim):
                self._dim = get_dim()
            else:
                self._dim = model.get_sentence_embedding_dimension()
            self.model = model
            _MODEL_CACHE[cache_key] = (model, self._dim)
            logger.info(
                f"Embedding model loaded: {self.model_name} "
                f"(dim={self._dim}, device={self.device}, onnx={self.use_onnx})"
            )
        except Exception as e:
            logger.error(f"Failed to load embedding model {self.model_name}: {e}")
            self.model = None
            self._dim = 384

    @property
    def dim(self) -> int:
        return self._dim or 384

    def encode_text(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            return np.zeros(self.dim, dtype=np.float32)

        if self.model is None:
            logger.warning("Embedding model not available — returning zero vector")
            return np.zeros(self.dim, dtype=np.float32)

        vec = self.model.encode(
            [text],
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        )[0]

        if self.normalize and np.linalg.norm(vec) > 0:
            vec = vec / np.linalg.norm(vec)
        return vec.astype(np.float32)

    def precompute_catalog(
        self,
        records: List[Any],
        id_key: str = "code",
        text_key: str = "_search_text",
    ) -> None:
        """Precompute embeddings for the entire catalog. Called once at startup."""
        texts: List[str] = []
        ids: List[str] = []

        for rec in records:
            if isinstance(rec, dict):
                rid = rec.get(id_key)
                txt = rec.get(text_key) or rec.get("search_text", "")
            else:
                rid = getattr(rec, id_key, None)
                txt = getattr(rec, text_key, getattr(rec, "_search_text", getattr(rec, "search_text", "")))

            if rid and txt:
                ids.append(str(rid))
                texts.append(txt)

        if not texts:
            self._precomputed.clear()
            return

        current_texts_hash = hash(tuple(texts))
        if hasattr(self, "_last_texts_hash") and self._last_texts_hash == current_texts_hash and self._precomputed:
            logger.info("Catalog texts are unchanged; skipping embedding precomputation.")
            return
        self._last_texts_hash = current_texts_hash
        self._precomputed.clear()

        if self.model is None:
            for rid in ids:
                self._precomputed[rid] = np.zeros(self.dim, dtype=np.float32)
            return

        logger.info(f"Precomputing embeddings for {len(texts)} FaultRecords...")
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
            batch_size=32,
        )

        for rid, emb in zip(ids, embeddings):
            if self.normalize and np.linalg.norm(emb) > 0:
                emb = emb / np.linalg.norm(emb)
            self._precomputed[rid] = emb.astype(np.float32)

        logger.info(f"Precomputed {len(self._precomputed)} embeddings "
                    f"(~{len(self._precomputed) * self.dim * 4 / 1024:.1f} KB)")

    def similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        if vec1 is None or vec2 is None or vec1.size == 0 or vec2.size == 0:
            return 0.0
        return float(np.dot(vec1, vec2))

    def score_against_catalog(
        self,
        context_embedding: np.ndarray,
        candidate_ids: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[tuple[str, float]]:
        """Score against (optionally pruned) catalog. Use with candidate_ids from fast signals."""
        if not self._precomputed:
            logger.warning("No precomputed embeddings. Call precompute_catalog() first.")
            return []

        ids_to_score = candidate_ids or list(self._precomputed.keys())
        scores: List[tuple[str, float]] = []

        for fid in ids_to_score:
            if fid not in self._precomputed:
                continue
            sc = self.similarity(context_embedding, self._precomputed[fid])
            scores.append((fid, sc))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_precomputed(self, fault_id: str) -> Optional[np.ndarray]:
        return self._precomputed.get(str(fault_id))


def create_embedding_engine_from_settings(settings: Any) -> EmbeddingEngine:
    model_name = getattr(settings, "embedding_model_name", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    use_onnx = getattr(settings, "embedding_use_onnx", True)
    return EmbeddingEngine(model_name=model_name, use_onnx=use_onnx)
