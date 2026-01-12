"""
In-memory storage implementation for testing and local development.

Provides a lightweight, thread-safe storage implementation that mimics
Redis behavior without requiring an external service.
"""

import asyncio
import fnmatch
import logging
import time
from typing import Optional, Any, List, Dict
from datetime import datetime

from backend.storage.interface import Storage

logger = logging.getLogger(__name__)


class MemoryStorage:
    """
    In-memory storage for tests and local development.
    
    This implementation provides the same interface as RedisAdapter but
    stores everything in memory. Useful for testing without Redis dependency.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}  # key -> expiry timestamp
        self._lock = asyncio.Lock()
        self.connected = True

    async def connect(self) -> bool:
        """
        No-op for in-memory storage (always connected).
        
        Returns:
            Always True
        """
        self.connected = True
        logger.debug("Memory storage initialized")
        return True

    async def close(self):
        """
        Clear in-memory storage.
        """
        async with self._lock:
            self._data.clear()
            self._expiry.clear()
        self.connected = False
        logger.debug("Memory storage cleared")

    def _is_expired(self, key: str) -> bool:
        """
        Check if a key has expired.
        
        Args:
            key: The key to check
            
        Returns:
            True if expired, False otherwise
        """
        if key not in self._expiry:
            return False
        return time.time() >= self._expiry[key]

    def _cleanup_expired(self, key: str):
        """
        Remove expired key from storage.
        
        Args:
            key: The key to cleanup
        """
        if self._is_expired(key):
            self._data.pop(key, None)
            self._expiry.pop(key, None)

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value by key.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The stored value or None if not found/expired
        """
        async with self._lock:
            self._cleanup_expired(key)
            value = self._data.get(key)
            if value is not None:
                logger.debug(f"Retrieved key {key}")
            return value

    async def set(
        self,
        key: str,
        value: Any,
        *,
        expire: Optional[int] = None
    ) -> bool:
        """
        Store a value with optional expiration.
        
        Args:
            key: The key to store under
            value: The value to store
            expire: Optional TTL in seconds
            
        Returns:
            Always True (in-memory storage always succeeds)
        """
        async with self._lock:
            self._data[key] = value
            if expire is not None:
                self._expiry[key] = time.time() + expire
            else:
                self._expiry.pop(key, None)
            logger.debug(f"Set key {key}" + (f" with TTL {expire}s" if expire else ""))
            return True

    async def delete(self, key: str) -> bool:
        """
        Delete a key.
        
        Args:
            key: The key to delete
            
        Returns:
            True if key was deleted, False if key didn't exist
        """
        async with self._lock:
            existed = key in self._data
            self._data.pop(key, None)
            self._expiry.pop(key, None)
            if existed:
                logger.debug(f"Deleted key {key}")
            return existed

    async def scan_keys(self, pattern: str) -> List[str]:
        """
        Scan for keys matching a glob pattern.
        
        Args:
            pattern: Glob-style pattern (e.g., "prefix:*")
            
        Returns:
            List of matching keys
        """
        async with self._lock:
            # Clean up expired keys first
            expired_keys = [k for k in self._data.keys() if self._is_expired(k)]
            for key in expired_keys:
                self._cleanup_expired(key)
            
            # Match pattern using fnmatch (glob-style matching)
            matching_keys = [
                key for key in self._data.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
            logger.debug(f"Scanned {len(matching_keys)} keys matching {pattern}")
            return matching_keys

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration on an existing key.
        
        Args:
            key: The key to set expiration on
            seconds: TTL in seconds
            
        Returns:
            True if expiration was set, False if key doesn't exist
        """
        async with self._lock:
            if key not in self._data or self._is_expired(key):
                return False
            self._expiry[key] = time.time() + seconds
            logger.debug(f"Set expiration on {key} to {seconds}s")
            return True

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists.
        
        Args:
            key: The key to check
            
        Returns:
            True if key exists and not expired, False otherwise
        """
        async with self._lock:
            self._cleanup_expired(key)
            return key in self._data

    async def health_check(self) -> bool:
        """
        Check if storage is healthy.
        
        Returns:
            Always True for in-memory storage
        """
        return self.connected

    async def clear_all(self):
        """
        Clear all data (useful for testing).
        """
        async with self._lock:
            self._data.clear()
            self._expiry.clear()
            logger.debug("Cleared all data from memory storage")
