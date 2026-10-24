"""Dense Embedding Model Adapter.

Provides dense vector representations for queries and document chunks.
Default target model: BAAI/bge-small-en-v1.5 (384 dimensions).
Includes deterministic offline fallback for zero-download test execution.
"""

from abc import ABC, abstractmethod
import hashlib
import math
import re
from typing import List, Optional

EMBEDDING_DIM = 384


class BaseEmbeddingService(ABC):
    """Abstract interface for dense embedding generation."""

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Generate embedding vector for a search query."""
        raise NotImplementedError

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embedding vectors for document passages."""
        raise NotImplementedError


class DeterministicEmbedder(BaseEmbeddingService):
    """Deterministic, lightweight 384-dim embedder for offline execution and testing.

    Projects token n-grams into a 384-dimensional space with L2 normalization.
    Semantically identical texts yield cosine similarity 1.0; overlapping texts yield high similarity.
    """

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    def _text_to_vector(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            vec[0] = 1.0
            return vec

        for i, token in enumerate(tokens):
            h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign * (1.0 / math.sqrt(i + 1))

            # Also hash bigrams for phrase awareness
            if i > 0:
                bi = f"{tokens[i-1]}_{token}"
                bh = int(hashlib.md5(bi.encode()).hexdigest(), 16)
                bidx = bh % self.dim
                bsign = 1.0 if (bh >> 4) % 2 == 0 else -1.0
                vec[bidx] += bsign * 1.5

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        else:
            vec[0] = 1.0
        return vec

    def embed_query(self, query: str) -> List[float]:
        return self._text_to_vector(query)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._text_to_vector(t) for t in texts]


class SentenceTransformerEmbedder(BaseEmbeddingService):
    """Production embedder wrapping sentence-transformers BAAI/bge-small-en-v1.5."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def embed_query(self, query: str) -> List[float]:
        self._load_model()
        vec = self._model.encode(query, normalize_embeddings=True)
        return vec.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        self._load_model()
        vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return vecs.tolist()


class EmbeddingService(BaseEmbeddingService):
    """Configurable embedding facade with automatic fallback to deterministic embedder."""

    def __init__(self, model_name: Optional[str] = None, force_deterministic: bool = False):
        self.model_name = model_name or "BAAI/bge-small-en-v1.5"
        self.force_deterministic = force_deterministic
        self._backend: BaseEmbeddingService = DeterministicEmbedder(EMBEDDING_DIM)

        if not force_deterministic:
            try:
                import sentence_transformers
                self._backend = SentenceTransformerEmbedder(self.model_name)
            except ImportError:
                # Fallback to deterministic embedder
                self._backend = DeterministicEmbedder(EMBEDDING_DIM)

    def set_backend(self, backend: BaseEmbeddingService) -> None:
        """Inject custom embedder (useful for isolated unit testing)."""
        self._backend = backend

    def embed_query(self, query: str) -> List[float]:
        return self._backend.embed_query(query)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._backend.embed_documents(texts)
