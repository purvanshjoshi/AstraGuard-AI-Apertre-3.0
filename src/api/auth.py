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
        # Validate API key presence
    if not api_key:
        logger.warning(
            "API key authentication failed: Missing API key header",
            extra={"operation": "get_api_key", "reason": "missing_header"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header."
        )
    
    # Validate API key format
    if not isinstance(api_key, str) or len(api_key.strip()) == 0:
        logger.warning(
            "API key authentication failed: Invalid key format",
            extra={"operation": "get_api_key", "reason": "invalid_format"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header."
        )
    
    api_key = api_key.strip()
    key_prefix = api_key[:8] if len(api_key) >= 8 else api_key[:4]

    try:
        key_manager = get_api_key_manager()
    except Exception as e:
        logger.error(
            f"Failed to get API key manager: {e}",
            extra={"operation": "get_api_key_manager", "error_type": type(e).__name__}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication error"
        )

    try:
        # Validate the key
        key = key_manager.validate_key(api_key)
        logger.debug(
            f"API key validated successfully",
            extra={"operation": "validate_key", "key_prefix": key_prefix, "key_name": key.name}
        )
    except ValueError as e:
        logger.warning(
            f"API key validation failed: {e}",
            extra={"operation": "validate_key", "key_prefix": key_prefix, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except AttributeError as e:
        logger.error(
            f"API key manager misconfiguration: {e}",
            extra={"operation": "validate_key", "error_type": "AttributeError"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication error"
        )

    try:
        # Check rate limit
        key_manager.check_rate_limit(api_key)
        logger.debug(
            f"Rate limit check passed",
            extra={"operation": "check_rate_limit", "key_prefix": key_prefix}
        )
    except ValueError as e:
        logger.warning(
            f"Rate limit exceeded: {e}",
            extra={"operation": "check_rate_limit", "key_prefix": key_prefix, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    return key




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
def initialize_from_env():
    """Initialize API keys from environment variables."""
    try:
        api_keys_env = get_secret("api_keys")
    except KeyError as e:
        logger.debug(
            f"No API keys found in secrets: {e}",
            extra={"operation": "get_secret", "key": "api_keys"}
        )
        return
    except Exception as e:
        logger.error(
            f"Failed to retrieve API keys from secrets: {e}",
            extra={"operation": "get_secret", "error_type": type(e).__name__}
        )
        return
    
    if not api_keys_env:
        logger.debug("API keys environment variable is empty")
        return
    
    try:
        # Expected format: name1:key1,name2:key2
        key_manager = get_api_key_manager()
        keys_added = 0
        
        for key_pair in api_keys_env.split(","):
            key_pair = key_pair.strip()
            
            if not key_pair:
                continue  # Skip empty entries
            
            if ":" not in key_pair:
                logger.warning(
                    f"Skipping malformed key pair (missing colon): {key_pair[:20]}...",
                    extra={"operation": "parse_key_pair", "format_expected": "name:key"}
                )
                continue
            
            try:
                name, key_value = key_pair.split(":", 1)
                name = name.strip()
                key_value = key_value.strip()
                
                # Validate key components
                if not name:
                    logger.warning(
                        "Skipping key pair with empty name",
                        extra={"operation": "validate_key_pair"}
                    )
                    continue
                
                if not key_value or len(key_value) < 8:
                    logger.warning(
                        f"Skipping key pair '{name}' with invalid key value (too short or empty)",
                        extra={"operation": "validate_key_pair", "key_name": name}
                    )
                    continue
                
                # Check if key already exists
                if key_value in key_manager.api_keys:
                    logger.debug(
                        f"Skipping duplicate key '{name}' (already exists)",
                        extra={"operation": "check_duplicate", "key_name": name}
                    )
                    continue
                
                key = APIKey(
                    key=key_value,
                    name=name,
                    created_at=datetime.now(),
                    permissions={"read", "write"},
                    metadata={"source": "environment"}
                )
                key_manager.api_keys[key_value] = key
                key_manager.key_hashes[hashlib.sha256(key_value.encode()).hexdigest()] = key_value
                keys_added += 1
                
            except ValueError as e:
                logger.warning(
                    f"Failed to parse key pair: {e}",
                    extra={"operation": "parse_key_pair", "key_pair_preview": key_pair[:20]}
                )
                continue
        
        # Save keys if any were added
        if keys_added > 0:
            try:
                key_manager._save_keys()
                logger.info(
                    f"Initialized {keys_added} API key(s) from environment",
                    extra={"operation": "save_keys", "count": keys_added}
                )
            except IOError as e:
                logger.error(
                    f"Failed to save API keys to file: {e}",
                    extra={"operation": "save_keys", "error_type": "IOError"}
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error saving API keys: {e}",
                    extra={"operation": "save_keys", "error_type": type(e).__name__}
                )
        else:
            logger.debug("No new API keys added from environment")
    
    except AttributeError as e:
        logger.error(
            f"API key manager not properly initialized: {e}",
            extra={"operation": "get_api_key_manager", "error_type": "AttributeError"}
        )
    except Exception as e:
        logger.error(
            f"Unexpected error during API key initialization: {e}",
            extra={"operation": "initialize_from_env", "error_type": type(e).__name__}
        )

