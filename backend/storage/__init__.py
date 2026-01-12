"""
Storage abstraction layer for AstraGuard-AI.

Provides a clean interface for storage operations with multiple implementations:
- RedisAdapter: Production Redis-backed storage
- MemoryStorage: In-memory storage for tests and local development
"""

from backend.storage.interface import Storage
from backend.storage.redis_adapter import RedisAdapter
from backend.storage.memory import MemoryStorage

__all__ = ["Storage", "RedisAdapter", "MemoryStorage"]
