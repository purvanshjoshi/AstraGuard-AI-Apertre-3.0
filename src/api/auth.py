"""
API Authentication Module

Provides FastAPI integration for authentication and authorization.
Uses core authentication logic for API key management and RBAC.
"""

import os
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable, Awaitable
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import APIKeyHeader
import logging
from core.auth import APIKey, APIKeyManager
from core.secrets import get_secret

logger = logging.getLogger(__name__)

# Global API key manager instance
_api_key_manager: Optional[APIKeyManager] = None

def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# FastAPI security scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    request: Request, 
    api_key: Optional[str] = Depends(api_key_header)
) -> APIKey:
    """
    FastAPI dependency for validating API keys.

    Retrieves the 'X-API-Key' header, validates it against the active key store,
    checks for expiration and rate limits, and returns the key object if valid.

    Args:
        request (Request): The incoming FastAPI request.
        api_key (str): The raw API key string from the header.

    Returns:
        APIKey: The validated API key object containing metadata and permissions.

    Raises:
        HTTPException(401): If the key is missing from headers.
        HTTPException(401): If the key is invalid, expired, or rate-limited.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header."
        )

    key_manager = get_api_key_manager()

    try:
        # Validate the key
        key = key_manager.validate_key(api_key)

        # Check rate limit
        key_manager.check_rate_limit(api_key)

        return key
    except ValueError as e:
        # Log authentication failures with debugging context
        logger.warning(
            f"Authentication failed: {e}",
            extra={
                "api_key_prefix": api_key[:8] + "..." if len(api_key) > 8 else api_key,
                "client_ip": request.client.host if request.client else "unknown",
                "endpoint": request.url.path
            }
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )



def require_permission(permission: str) -> Callable[[APIKey], Awaitable[APIKey]]:

    """
    Create a dependency that requires a specific permission scope.

    Used as a decorator or dependency in FastAPI routes to enforce granular
    access control (RbAC) based on the permissions associated with the API key.

    Args:
        permission (str): The permission identifier (e.g., 'read', 'write', 'admin').

    Returns:
        Callable: A FastAPI dependency function that validates the permission.
    """
    async def permission_checker(api_key: APIKey = Depends(get_api_key)) -> APIKey:
        if permission not in api_key.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return api_key

    return permission_checker


# Initialize API keys from environment variable (optional)
def initialize_from_env() -> None:
    """Initialize API keys from environment variables."""
    api_keys_env: Optional[str] = get_secret("api_keys")
    
    if api_keys_env:
        try:
            # Expected format: name1:key1,name2:key2
            key_manager = get_api_key_manager()
            initialized_count = 0
            
            for key_pair in api_keys_env.split(","):
                key_pair = key_pair.strip()
                
                # Skip empty entries
                if not key_pair:
                    continue
                    
                # Validate format
                if ":" not in key_pair:
                    logger.warning(f"Skipping malformed API key pair (missing colon): '{key_pair[:20]}...'")
                    continue
                    
                name_part, key_value_part = key_pair.split(":", 1)
                name = name_part.strip()
                key_value = key_value_part.strip()
                
                # Skip entries with empty name or value
                if not name or not key_value:
                    logger.warning("Skipping API key pair with empty name or value")
                    continue

                # Check if key already exists
                if key_value not in key_manager.api_keys:
                    key = APIKey(
                        key=key_value,
                        name=name,
                        created_at=datetime.now(),
                        permissions={"read", "write"},
                        metadata={"source": "environment"}
                    )
                    key_manager.api_keys[key_value] = key
                    key_hash = hashlib.sha256(key_value.encode()).hexdigest()
                    key_manager.key_hashes[key_hash] = key_value
                    initialized_count += 1

            # MOVED OUTSIDE LOOP - was incorrectly inside the loop before
            key_manager._save_keys()  # type: ignore[attr-defined]
            logger.info(
                f"Initialized {initialized_count} API keys from environment",
                extra={"initialized_count": initialized_count}
            )

        except ValueError as e:
            # Invalid format in environment variable
            logger.error(f"Invalid API key format in environment variable: {e}", exc_info=True)
        except OSError as e:
            # File system errors when saving keys
            logger.error(f"Failed to save API keys to storage: {e}", exc_info=True)
        except Exception as e:
            # Intentionally broad: catch unexpected errors to prevent startup failure
            # This allows the application to start even if API key initialization fails
            logger.error(f"Unexpected error initializing API keys from environment: {e}", exc_info=True)
