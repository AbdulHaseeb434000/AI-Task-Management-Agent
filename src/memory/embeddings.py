"""Embeddings Service - Semantic search using vector embeddings.

Provides:
- Text to embedding conversion using OpenAI
- Cosine similarity for semantic search
- Embedding storage and retrieval
"""

import logging
import numpy as np
from typing import Optional, List, Tuple
from dataclasses import dataclass

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    text: str
    embedding: List[float]
    model: str
    dimensions: int


@dataclass
class SimilarityMatch:
    """A similarity search match."""
    id: str
    content: str
    score: float
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class EmbeddingService:
    """Service for generating and comparing embeddings.

    Uses OpenAI's text-embedding-3-small model by default.
    Falls back to keyword matching if embeddings unavailable.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ):
        """Initialize embedding service.

        Args:
            model: OpenAI embedding model name.
            dimensions: Embedding vector dimensions.
        """
        self.model = model
        self.dimensions = dimensions
        self._client = None
        self._enabled = bool(settings.openai_api_key)

    @property
    def client(self):
        """Lazy-load OpenAI client."""
        if self._client is None and self._enabled:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=settings.openai_api_key)
            except ImportError:
                logger.warning("OpenAI package not installed, embeddings disabled")
                self._enabled = False
        return self._client

    @property
    def enabled(self) -> bool:
        """Check if embeddings are available."""
        return self._enabled

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            List of floats representing the embedding, or None if unavailable.
        """
        if not self.enabled or not text:
            return None

        try:
            # Truncate long text (model limit ~8k tokens)
            truncated = text[:30000]  # Rough approximation

            response = await self.client.embeddings.create(
                model=self.model,
                input=truncated,
            )

            return response.data[0].embedding

        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            return None

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embeddings (None for failed items).
        """
        if not self.enabled or not texts:
            return [None] * len(texts)

        try:
            # Truncate and filter empty
            valid_texts = []
            indices = []
            for i, text in enumerate(texts):
                if text:
                    valid_texts.append(text[:30000])
                    indices.append(i)

            if not valid_texts:
                return [None] * len(texts)

            response = await self.client.embeddings.create(
                model=self.model,
                input=valid_texts,
            )

            # Map results back to original indices
            results = [None] * len(texts)
            for i, embedding_data in enumerate(response.data):
                original_idx = indices[i]
                results[original_idx] = embedding_data.embedding

            return results

        except Exception as e:
            logger.warning(f"Failed to generate batch embeddings: {e}")
            return [None] * len(texts)

    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.

        Returns:
            Similarity score between -1 and 1.
        """
        if not embedding1 or not embedding2:
            return 0.0

        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(dot_product / (norm1 * norm2))

        except Exception as e:
            logger.warning(f"Failed to calculate similarity: {e}")
            return 0.0

    def find_similar(
        self,
        query_embedding: List[float],
        candidates: List[Tuple[str, str, List[float], dict]],
        top_k: int = 10,
        min_score: float = 0.5,
    ) -> List[SimilarityMatch]:
        """Find similar items by embedding similarity.

        Args:
            query_embedding: The query embedding vector.
            candidates: List of (id, content, embedding, metadata) tuples.
            top_k: Maximum results to return.
            min_score: Minimum similarity score threshold.

        Returns:
            List of SimilarityMatch objects, sorted by score.
        """
        if not query_embedding:
            return []

        matches = []

        for item_id, content, embedding, metadata in candidates:
            if embedding:
                score = self.cosine_similarity(query_embedding, embedding)
                if score >= min_score:
                    matches.append(SimilarityMatch(
                        id=item_id,
                        content=content,
                        score=score,
                        metadata=metadata or {},
                    ))

        # Sort by score descending
        matches.sort(key=lambda x: x.score, reverse=True)

        return matches[:top_k]

    def keyword_fallback_score(
        self,
        query: str,
        content: str,
    ) -> float:
        """Calculate keyword-based similarity as fallback.

        Args:
            query: Search query.
            content: Content to compare against.

        Returns:
            Similarity score between 0 and 1.
        """
        if not query or not content:
            return 0.0

        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        # Jaccard similarity
        intersection = query_words & content_words
        union = query_words | content_words

        if not union:
            return 0.0

        return len(intersection) / len(union)


# Global instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
