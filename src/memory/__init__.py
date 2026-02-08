"""Tiered Memory System.

Provides hot, warm, and cold memory tiers for efficient context management.
"""

from src.memory.hot import HotMemory, HotMemoryState
from src.memory.warm import WarmMemory, WarmMemoryResult
from src.memory.cold import ColdMemory
from src.memory.manager import MemoryManager, get_memory_manager
from src.memory.embeddings import EmbeddingService, get_embedding_service, SimilarityMatch

__all__ = [
    # Hot memory
    "HotMemory",
    "HotMemoryState",
    # Warm memory
    "WarmMemory",
    "WarmMemoryResult",
    # Cold memory
    "ColdMemory",
    # Manager
    "MemoryManager",
    "get_memory_manager",
    # Embeddings
    "EmbeddingService",
    "get_embedding_service",
    "SimilarityMatch",
]
