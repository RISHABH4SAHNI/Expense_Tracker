"""
Authentication dependencies for FastAPI routes

Provides reusable authentication dependencies and decorators for protecting routes.
Handles JWT token parsing, validation, blacklist checking, and user loading.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from functools import wraps

import asyncpg
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import get_db
from app.security import decode_token, extract_user_id_from_token, extract_token_id_from_token

# Configure logging
logger = logging.getLogger(__name__)

# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    """
    Authenticated user data container

    Provides a clean interface for accessing user data in protected routes.
    """

    def __init__(self, user_data: Dict[str, Any], token_payload: Dict[str, Any]):
        self._user_data = user_data
        self._token_payload = token_payload

    @property
    def id(self) -> str:
        """User UUID"""
        return str(self._user_data["id"])

    @property
    def email(self) -> str:
        """User email address"""
        return self._user_data["email"]

    @property
    def created_at(self) -> datetime:
        """User account creation timestamp"""
        return self._user_data["created_at"]

    @property
    def aa_account_id(self) -> Optional[str]:
        """Account Aggregator account ID (if linked)"""
        return self._user_data.get("aa_account_id")

    @property
    def token_id(self) -> str:
        """Current JWT token ID"""
        return self._token_payload.get("jti", "")

    @property
    def token_type(self) -> str:
        """Token type (access/refresh)"""
        return self._token_payload.get("type", "access")

    @property
    def is_authenticated(self) -> bool:
        """Always True for authenticated users"""
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at,
            "aa_account_id": self.aa_account_id,
            "token_id": self.token_id,
            "token_type": self.token_type,
            "is_authenticated": self.is_authenticated
        }

    def __str__(self) -> str:
        return f"AuthenticatedUser(id={self.id}, email={self.email})"

    def __repr__(self) -> str:
        return self.__str__()


async def _is_token_blacklisted(db: asyncpg.Connection, token_id: str) -> bool:
    """
    Check if a token is blacklisted in the database

    Args:
        db: Database connection
        token_id: JWT token ID to check

    Returns:
        True if token is blacklisted, False otherwise
    """
    try:
        result = await db.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM session_tokens 
                WHERE token_id = $1 AND expires_at > $2
            )
        """, token_id, datetime.utcnow())

        return bool(result)

    except Exception as e:
        logger.error(f"Token blacklist check failed: {e}")
        # In case of database error, assume token is not blacklisted
        # This prevents authentication from failing due to DB issues
        return False


async def _load_user_from_db(db: asyncpg.Connection, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Load user data from database

    Args:
        db: Database connection
        user_id: User UUID to load

    Returns:
        User data dictionary or None if not found
    """
    try:
        result = await db.fetchrow("""
            SELECT id, email, created_at, updated_at, aa_account_id
            FROM users 
            WHERE id = $1
        """, user_id)

        if not result:
            return None

        return {
            "id": str(result["id"]),
            "email": result["email"],
            "created_at": result["created_at"],
            "updated_at": result["updated_at"],
            "aa_account_id": result.get("aa_account_id")
        }

    except Exception as e:
        logger.error(f"User lookup failed for {user_id}: {e}")
        return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: asyncpg.Connection = Depends(get_db)
) -> AuthenticatedUser:
    """
    FastAPI dependency to get the current authenticated user

    Validates JWT token, checks blacklist, loads user data, and attaches to request state.

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials
        db: Database connection

    Returns:
        AuthenticatedUser instance with user data and token info

    Raises:
        HTTPException: 401 if authentication fails
    """
    # Check if credentials are provided
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Decode and validate JWT token
        token_payload = decode_token(credentials.credentials)
        user_id = token_payload.get("sub")
        token_id = token_payload.get("jti")

        if not user_id or not token_id:
            logger.warning("Token missing required claims (sub or jti)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if token is blacklisted (if database is available)
        if db and await _is_token_blacklisted(db, token_id):
            logger.warning(f"Blacklisted token used: {token_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Load user data from database
        user_data = None
        if db:
            user_data = await _load_user_from_db(db, user_id)
            if not user_data:
                logger.warning(f"User not found in database: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # Development mode - create mock user data
            logger.info("Development mode: Using mock user data")
            user_data = {
                "id": user_id,
                "email": token_payload.get("email", "dev@example.com"),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "aa_account_id": None
            }

        # Create authenticated user instance
        authenticated_user = AuthenticatedUser(user_data, token_payload)

        # Attach user to request state for easy access in route handlers
        request.state.user = authenticated_user

        logger.debug(f"Authentication successful: {authenticated_user}")
        return authenticated_user

    except HTTPException:
        # Re-raise HTTP exceptions (already have proper status/detail)
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: asyncpg.Connection = Depends(get_db)
) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency to get the current user if authenticated

    Similar to get_current_user but returns None instead of raising 401 if not authenticated.
    Useful for endpoints that work with or without authentication.

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials (optional)
        db: Database connection

    Returns:
        AuthenticatedUser instance if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        # If authentication fails, return None instead of raising
        return None


def require_user() -> Callable:
    """
    Decorator/helper for routes that require authentication

    This is a convenience function that returns the get_current_user dependency.
    Use this in route definitions for better readability.

    Usage:
        @router.get("/protected")
        async def protected_route(user: AuthenticatedUser = Depends(require_user())):
            return {"message": f"Hello {user.email}"}

    Returns:
        FastAPI dependency function
    """
    return get_current_user


def require_admin() -> Callable:
    """
    Decorator/helper for routes that require admin authentication

    Note: Currently returns the same as require_user() since we don't have
    role-based authentication yet. This is a placeholder for future enhancement.

    Returns:
        FastAPI dependency function
    """
    # TODO: Implement role-based authentication
    # For now, just require any authenticated user
    return get_current_user


# Convenience aliases for common authentication patterns
AuthDep = Depends(get_current_user)  # For type hints: user: AuthenticatedUser = AuthDep
OptionalAuthDep = Depends(get_optional_user)  # For optional auth: user: Optional[AuthenticatedUser] = OptionalAuthDep


# Export commonly used items
__all__ = [
    "AuthenticatedUser",
    "get_current_user", 
    "get_optional_user",
    "require_user",
    "require_admin",
    "AuthDep",
    "OptionalAuthDep"
]
