"""Tests for the embeddings service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.memory.embeddings import (
    EmbeddingService,
    SimilarityMatch,
    get_embedding_service,
)


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    def test_cosine_similarity_identical(self):
        """Test cosine similarity with identical vectors."""
        service = EmbeddingService()

        vec = [1.0, 0.0, 0.0]
        similarity = service.cosine_similarity(vec, vec)

        assert similarity == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity with orthogonal vectors."""
        service = EmbeddingService()

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = service.cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(0.0)

    def test_cosine_similarity_opposite(self):
        """Test cosine similarity with opposite vectors."""
        service = EmbeddingService()

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = service.cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(-1.0)

    def test_cosine_similarity_similar(self):
        """Test cosine similarity with similar vectors."""
        service = EmbeddingService()

        vec1 = [1.0, 1.0, 0.0]
        vec2 = [1.0, 0.8, 0.1]
        similarity = service.cosine_similarity(vec1, vec2)

        # Should be high (close to 1)
        assert similarity > 0.9

    def test_cosine_similarity_empty(self):
        """Test cosine similarity with empty vectors."""
        service = EmbeddingService()

        similarity = service.cosine_similarity([], [1.0])
        assert similarity == 0.0

        similarity = service.cosine_similarity([1.0], [])
        assert similarity == 0.0

    def test_find_similar(self):
        """Test finding similar items."""
        service = EmbeddingService()

        query = [1.0, 0.0, 0.0]
        candidates = [
            ("id1", "content1", [0.9, 0.1, 0.0], {}),  # Very similar
            ("id2", "content2", [0.0, 1.0, 0.0], {}),  # Orthogonal
            ("id3", "content3", [0.7, 0.7, 0.0], {}),  # Somewhat similar
        ]

        matches = service.find_similar(
            query, candidates, top_k=2, min_score=0.5
        )

        assert len(matches) == 2
        assert matches[0].id == "id1"  # Most similar first
        assert matches[0].score > matches[1].score

    def test_find_similar_min_score_filter(self):
        """Test that min_score filters out low matches."""
        service = EmbeddingService()

        query = [1.0, 0.0, 0.0]
        candidates = [
            ("id1", "content1", [0.0, 1.0, 0.0], {}),  # Orthogonal (score ~0)
        ]

        matches = service.find_similar(
            query, candidates, top_k=10, min_score=0.5
        )

        assert len(matches) == 0

    def test_keyword_fallback_score(self):
        """Test keyword-based fallback scoring."""
        service = EmbeddingService()

        # Exact overlap
        score = service.keyword_fallback_score(
            "hello world",
            "hello world"
        )
        assert score == 1.0

        # Partial overlap
        score = service.keyword_fallback_score(
            "hello world",
            "hello there world"
        )
        assert 0.5 < score < 1.0

        # No overlap
        score = service.keyword_fallback_score(
            "hello world",
            "foo bar"
        )
        assert score == 0.0

    def test_keyword_fallback_empty(self):
        """Test keyword fallback with empty strings."""
        service = EmbeddingService()

        assert service.keyword_fallback_score("", "content") == 0.0
        assert service.keyword_fallback_score("query", "") == 0.0


class TestSimilarityMatch:
    """Tests for SimilarityMatch dataclass."""

    def test_similarity_match_creation(self):
        """Test creating a SimilarityMatch."""
        match = SimilarityMatch(
            id="test-id",
            content="test content",
            score=0.85,
            metadata={"key": "value"},
        )

        assert match.id == "test-id"
        assert match.content == "test content"
        assert match.score == 0.85
        assert match.metadata == {"key": "value"}

    def test_similarity_match_default_metadata(self):
        """Test that metadata defaults to empty dict."""
        match = SimilarityMatch(
            id="test-id",
            content="test content",
            score=0.85,
        )

        assert match.metadata == {}


class TestGetEmbeddingService:
    """Tests for get_embedding_service function."""

    def test_returns_singleton(self):
        """Test that get_embedding_service returns a singleton."""
        # Reset global state
        import src.memory.embeddings as emb_module
        emb_module._embedding_service = None

        service1 = get_embedding_service()
        service2 = get_embedding_service()

        assert service1 is service2


@pytest.mark.asyncio
class TestEmbeddingServiceAsync:
    """Async tests for EmbeddingService."""

    async def test_embed_text_disabled(self):
        """Test embedding when service is disabled."""
        with patch.object(
            EmbeddingService, 'enabled', new_callable=lambda: property(lambda self: False)
        ):
            service = EmbeddingService()
            service._enabled = False

            result = await service.embed_text("test text")
            assert result is None

    async def test_embed_text_empty(self):
        """Test embedding empty text."""
        service = EmbeddingService()
        service._enabled = True

        result = await service.embed_text("")
        assert result is None

    async def test_embed_batch_disabled(self):
        """Test batch embedding when service is disabled."""
        service = EmbeddingService()
        service._enabled = False

        results = await service.embed_batch(["text1", "text2"])
        assert results == [None, None]

    async def test_embed_batch_empty(self):
        """Test batch embedding with empty list."""
        service = EmbeddingService()
        service._enabled = False

        results = await service.embed_batch([])
        assert results == []
