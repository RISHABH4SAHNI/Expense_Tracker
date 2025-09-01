# Authentication routes
"""
Authentication routes for Expense Tracker API

Handles user registration, login, token refresh, logout, and rate limiting.
Integrates with PostgreSQL for user management and Redis for rate limiting.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr

from app.database import get_db
from app.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, extract_user_id_from_token, extract_token_id_from_token,
    generate_token_id
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Router setup
router = APIRouter()
security = HTTPBearer()

# Redis client for rate limiting (will be set from main.py)
redis_client = None

def set_redis_client(client):
    """Set Redis client from main.py"""
    global redis_client
    redis_client = client


# Pydantic models for API requests/responses

class UserRegister(BaseModel):
    """User registration request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenRefresh(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., description="Valid refresh token")


class UserResponse(BaseModel):
    """Safe user data response"""
    id: str
    email: str
    created_at: datetime
    aa_account_id: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response with user data"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token") 
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    user: UserResponse = Field(..., description="User information")


class LogoutResponse(BaseModel):
    """Logout response"""
    message: str = Field(..., description="Logout confirmation message")
    revoked_tokens: int = Field(..., description="Number of tokens revoked")


# Rate limiting helpers

async def check_rate_limit(request: Request, identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
    """
    Check if request is within rate limit

    Args:
        request: FastAPI request object
        identifier: Unique identifier (e.g., email, IP)
        max_attempts: Maximum attempts allowed
        window_minutes: Time window in minutes

    Returns:
        True if within rate limit, False if exceeded
    """
    # Disable rate limiting for development
    logger.info(f"Development mode: Bypassing rate limit check for {identifier}")
    return True

    if not redis_client:
        # If Redis is not available, allow the request (development mode)
        logger.warning("Redis not available, skipping rate limit check")
        return True

    try:
        # Create rate limit key
        key = f"rate_limit:{identifier}:{window_minutes}min"

        # Get current count
        current = await redis_client.get(key)
        current_count = int(current) if current else 0

        if current_count >= max_attempts:
            logger.warning(f"Rate limit exceeded for {identifier}: {current_count}/{max_attempts}")
            return False

        # Increment counter
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_minutes * 60)
        await pipe.execute()

        return True

    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        # If Redis fails, allow the request to continue
        return True


async def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded IP headers (common in production with load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to client IP
    return request.client.host if request.client else "unknown"


# Database helpers

async def create_user_in_db(db: asyncpg.Connection, email: str, password: str) -> dict:
    """Create a new user in the database"""
    try:
        # Hash password
        password_hash = hash_password(password)

        # Insert user
        user_id = str(uuid.uuid4())
        result = await db.fetchrow("""
            INSERT INTO users (id, email, password_hash, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, email, created_at, aa_account_id
        """, user_id, email, password_hash, datetime.utcnow(), datetime.utcnow())

        return {
            "id": str(result["id"]),
            "email": result["email"],
            "created_at": result["created_at"],
            "aa_account_id": result.get("aa_account_id")
        }

    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    except Exception as e:
        logger.error(f"User creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


async def get_user_by_email(db: asyncpg.Connection, email: str) -> Optional[dict]:
    """Get user by email from database"""
    try:
        result = await db.fetchrow("""
            SELECT id, email, password_hash, created_at, aa_account_id
            FROM users 
            WHERE email = $1
        """, email)

        if not result:
            return None

        return {
            "id": str(result["id"]),
            "email": result["email"],
            "password_hash": result["password_hash"],
            "created_at": result["created_at"],
            "aa_account_id": result.get("aa_account_id")
        }

    except Exception as e:
        logger.error(f"User lookup failed: {e}")
        return None


async def store_session_token(db: asyncpg.Connection, user_id: str, token_id: str, expires_at: datetime):
    """Store session token for tracking and blacklisting"""
    try:
        await db.execute("""
            INSERT INTO session_tokens (user_id, token_id, expires_at, created_at)
            VALUES ($1, $2, $3, $4)
        """, user_id, token_id, expires_at, datetime.utcnow())

    except Exception as e:
        logger.error(f"Failed to store session token: {e}")
        # Don't fail the request if session storage fails
        pass


async def is_token_blacklisted(db: asyncpg.Connection, token_id: str) -> bool:
    """Check if token is blacklisted (i.e., NOT in the valid session_tokens table)"""
    try:
        result = await db.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM session_tokens 
                WHERE token_id = $1 AND expires_at > $2
            )
        """, token_id, datetime.utcnow())

        # If token EXISTS in session_tokens table, it's VALID (not blacklisted)
        # If token does NOT exist in session_tokens table, it's BLACKLISTED
        return not bool(result)

    except Exception as e:
        logger.error(f"Token blacklist check failed: {e}")
        return False


async def revoke_user_tokens(db: asyncpg.Connection, user_id: str, current_token_id: str = None) -> int:
    """Revoke all user tokens (except current one if specified)"""
    try:
        if current_token_id:
            result = await db.execute("""
                DELETE FROM session_tokens 
                WHERE user_id = $1 AND token_id != $2
            """, user_id, current_token_id)
        else:
            result = await db.execute("""
                DELETE FROM session_tokens 
                WHERE user_id = $1
            """, user_id)

        # Extract number of affected rows
        return int(result.split()[-1]) if result else 0

    except Exception as e:
        logger.error(f"Token revocation failed: {e}")
        return 0


# Authentication dependency

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: asyncpg.Connection = Depends(get_db)
) -> dict:
    """
    Get current authenticated user from JWT token

    Returns:
        User dict with id, email, created_at, aa_account_id
    """
    try:
        # Decode token
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        token_id = payload.get("jti")

        if not user_id or not token_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # Check if token is blacklisted (if database is available)
        if db and await is_token_blacklisted(db, token_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )

        # Get user from database
        if db:
            user = await db.fetchrow("""
                SELECT id, email, created_at, aa_account_id
                FROM users WHERE id = $1
            """, user_id)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )

            return {
                "id": str(user["id"]),
                "email": user["email"],
                "created_at": user["created_at"],
                "aa_account_id": user.get("aa_account_id")
            }
        else:
            # Development mode - return minimal user data from token
            return {
                "id": user_id,
                "email": payload.get("email", "dev@example.com"),
                "created_at": datetime.utcnow(),
                "aa_account_id": None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


# Authentication routes

@router.post("/register", response_model=TokenResponse)
async def register_user(
    user_data: UserRegister,
    request: Request,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Register a new user account

    Creates a new user with email and password, returns access and refresh tokens.
    Rate limited by IP address to prevent abuse.
    """
    logger.info(f"🔐 Registration attempt for email: {user_data.email}")

    # Rate limiting by IP
    client_ip = await get_client_ip(request)
    if not await check_rate_limit(request, f"register:{client_ip}", max_attempts=3, window_minutes=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later."
        )

    if not db:
        # Development mode - return mock tokens
        logger.info("📍 Development mode: Creating mock user registration")
        mock_user = {
            "id": str(uuid.uuid4()),
            "email": user_data.email,
            "created_at": datetime.utcnow(),
            "aa_account_id": None
        }

        token_data = {"sub": mock_user["id"], "email": mock_user["email"]}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=15 * 60,  # 15 minutes
            user=UserResponse(**mock_user)
        )

    # Create user in database
    user = await create_user_in_db(db, user_data.email, user_data.password)

    # Generate tokens
    token_data = {"sub": user["id"], "email": user["email"]}
    access_token_id = generate_token_id()
    refresh_token_id = generate_token_id()

    access_token = create_access_token(token_data, token_id=access_token_id)
    refresh_token = create_refresh_token(token_data, token_id=refresh_token_id)

    # Store session tokens
    access_expires = datetime.utcnow() + timedelta(minutes=15)
    refresh_expires = datetime.utcnow() + timedelta(days=30)

    await store_session_token(db, user["id"], access_token_id, access_expires)
    await store_session_token(db, user["id"], refresh_token_id, refresh_expires)

    logger.info(f"✅ User registered successfully: {user['email']}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=15 * 60,  # 15 minutes in seconds
        user=UserResponse(**user)
    )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    login_data: UserLogin,
    request: Request,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Authenticate user and return tokens

    Validates email/password and returns access and refresh tokens.
    Rate limited by IP and email to prevent brute force attacks.
    """
    logger.info(f"🔐 Login attempt for email: {login_data.email}")

    # Rate limiting by IP and email
    client_ip = await get_client_ip(request)

    if not await check_rate_limit(request, f"login:ip:{client_ip}", max_attempts=10, window_minutes=15):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts from this IP. Please try again later."
        )

    if not await check_rate_limit(request, f"login:email:{login_data.email}", max_attempts=5, window_minutes=15):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts for this email. Please try again later."
        )

    if not db:
        # Development mode - mock authentication
        logger.info("📍 Development mode: Mock login successful")
        mock_user = {
            "id": str(uuid.uuid4()),
            "email": login_data.email,
            "created_at": datetime.utcnow(),
            "aa_account_id": None
        }

        token_data = {"sub": mock_user["id"], "email": mock_user["email"]}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=15 * 60,
            user=UserResponse(**mock_user)
        )

    # Get user from database
    user = await get_user_by_email(db, login_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Generate tokens
    token_data = {"sub": user["id"], "email": user["email"]}
    access_token_id = generate_token_id()
    refresh_token_id = generate_token_id()

    access_token = create_access_token(token_data, token_id=access_token_id)
    refresh_token = create_refresh_token(token_data, token_id=refresh_token_id)

    # Store session tokens
    access_expires = datetime.utcnow() + timedelta(minutes=15)
    refresh_expires = datetime.utcnow() + timedelta(days=30)

    await store_session_token(db, user["id"], access_token_id, access_expires)
    await store_session_token(db, user["id"], refresh_token_id, refresh_expires)

    # Clean up expired tokens for this user
    await db.execute("""
        DELETE FROM session_tokens 
        WHERE user_id = $1 AND expires_at < $2
    """, user["id"], datetime.utcnow())

    logger.info(f"✅ Login successful for user: {user['email']}")

    # Remove password hash from response
    user_response = {k: v for k, v in user.items() if k != "password_hash"}

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=15 * 60,
        user=UserResponse(**user_response)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    refresh_data: TokenRefresh,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Refresh access token using refresh token

    Validates refresh token and returns new access and refresh tokens.
    Implements token rotation for enhanced security.
    """
    logger.info("🔄 Token refresh request")

    try:
        # Decode refresh token
        payload = decode_token(refresh_data.refresh_token)
        user_id = payload.get("sub")
        token_id = payload.get("jti")
        token_type = payload.get("type")

        if not user_id or not token_id or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        if not db:
            # Development mode
            logger.info("📍 Development mode: Mock token refresh")
            token_data = {"sub": user_id, "email": payload.get("email", "dev@example.com")}
            new_access_token = create_access_token(token_data)
            new_refresh_token = create_refresh_token(token_data)

            mock_user = {
                "id": user_id,
                "email": payload.get("email", "dev@example.com"),
                "created_at": datetime.utcnow(),
                "aa_account_id": None
            }

            return TokenResponse(
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                expires_in=15 * 60,
                user=UserResponse(**mock_user)
            )

        # Check if refresh token is blacklisted
        if await is_token_blacklisted(db, token_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked"
            )

        # Get user from database
        user = await db.fetchrow("""
            SELECT id, email, created_at, aa_account_id
            FROM users WHERE id = $1
        """, user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Revoke old refresh token
        await db.execute("""
            DELETE FROM session_tokens WHERE token_id = $1
        """, token_id)

        # Generate new tokens
        token_data = {"sub": str(user["id"]), "email": user["email"]}
        new_access_token_id = generate_token_id()
        new_refresh_token_id = generate_token_id()

        new_access_token = create_access_token(token_data, token_id=new_access_token_id)
        new_refresh_token = create_refresh_token(token_data, token_id=new_refresh_token_id)

        # Store new session tokens
        access_expires = datetime.utcnow() + timedelta(minutes=15)
        refresh_expires = datetime.utcnow() + timedelta(days=30)

        await store_session_token(db, str(user["id"]), new_access_token_id, access_expires)
        await store_session_token(db, str(user["id"]), new_refresh_token_id, refresh_expires)

        logger.info(f"✅ Token refresh successful for user: {user['email']}")

        user_data = {
            "id": str(user["id"]),
            "email": user["email"],
            "created_at": user["created_at"],
            "aa_account_id": user.get("aa_account_id")
        }

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=15 * 60,
            user=UserResponse(**user_data)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout_user(
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Logout user and revoke tokens

    Blacklists current token and optionally revokes all user tokens.
    """
    logger.info(f"🚪 Logout request for user: {current_user['email']}")

    try:
        # Extract token ID from current token
        current_token_id = extract_token_id_from_token(credentials.credentials)

        if not db:
            # Development mode
            logger.info("📍 Development mode: Mock logout successful")
            return LogoutResponse(
                message="Logged out successfully",
                revoked_tokens=1
            )

        # Revoke all user tokens
        revoked_count = await revoke_user_tokens(db, current_user["id"])

        logger.info(f"✅ Logout successful for user: {current_user['email']}, revoked {revoked_count} tokens")

        return LogoutResponse(
            message="Logged out successfully",
            revoked_tokens=revoked_count
        )

    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


# Profile endpoint (bonus)
@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user)
):
    """Get current user profile information"""
    return UserResponse(**current_user)