"""
Security utilities for Expense Tracker

Provides password hashing, JWT token creation/validation, and security helpers.
Uses passlib with bcrypt for password hashing and python-jose for JWT operations.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union

import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException, status
from passlib.context import CryptContext
import logging

logger = logging.getLogger(__name__)

# Load configuration from environment variables
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

# Warn if using default JWT secret in production
if JWT_SECRET == "your-super-secret-jwt-key-change-in-production":
    logger.warning("⚠️  Using default JWT secret! Set JWT_SECRET environment variable in production")

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SecurityError(Exception):
    """Base exception for security-related errors"""
    pass


class TokenError(SecurityError):
    """Exception for token-related errors"""
    pass


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with salt

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string

    Raises:
        SecurityError: If password is invalid
    """
    if not password or not isinstance(password, str):
        raise SecurityError("Password must be a non-empty string")

    if len(password) < 8:
        raise SecurityError("Password must be at least 8 characters long")

    if len(password) > 128:
        raise SecurityError("Password must be less than 128 characters")

    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Password hashing failed: {e}")
        raise SecurityError("Failed to hash password")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    if not plain_password or not hashed_password:
        return False

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False


def generate_token_id() -> str:
    """
    Generate a unique token ID using UUID4

    Returns:
        UUID4 string for token identification
    """
    return str(uuid.uuid4())


def create_access_token(
    data: Dict[str, Any], 
    expires_minutes: Optional[int] = None,
    token_id: Optional[str] = None
) -> str:
    """
    Create a JWT access token

    Args:
        data: Payload data to include in token
        expires_minutes: Token expiration in minutes (default from env)
        token_id: Optional token ID for tracking (generates if not provided)

    Returns:
        Encoded JWT token string

    Raises:
        TokenError: If token creation fails
    """
    try:
        # Set expiration time
        if expires_minutes is None:
            expires_minutes = ACCESS_TOKEN_EXPIRE_MINUTES

        expire = datetime.utcnow() + timedelta(minutes=expires_minutes)

        # Generate token ID if not provided
        if token_id is None:
            token_id = generate_token_id()

        # Create payload
        payload = {
            **data,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": token_id,  # JWT ID for token tracking
            "type": "access"
        }

        # Encode token
        encoded_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return encoded_jwt

    except Exception as e:
        logger.error(f"Access token creation failed: {e}")
        raise TokenError("Failed to create access token")


def create_refresh_token(
    data: Dict[str, Any], 
    expires_days: Optional[int] = None,
    token_id: Optional[str] = None
) -> str:
    """
    Create a JWT refresh token

    Args:
        data: Payload data to include in token
        expires_days: Token expiration in days (default from env)
        token_id: Optional token ID for tracking (generates if not provided)

    Returns:
        Encoded JWT refresh token string

    Raises:
        TokenError: If token creation fails
    """
    try:
        # Set expiration time
        if expires_days is None:
            expires_days = REFRESH_TOKEN_EXPIRE_DAYS

        expire = datetime.utcnow() + timedelta(days=expires_days)

        # Generate token ID if not provided
        if token_id is None:
            token_id = generate_token_id()

        # Create payload (minimal data for refresh tokens)
        payload = {
            "sub": data.get("sub"),  # Subject (usually user ID)
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": token_id,
            "type": "refresh"
        }

        # Encode token
        encoded_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return encoded_jwt

    except Exception as e:
        logger.error(f"Refresh token creation failed: {e}")
        raise TokenError("Failed to create refresh token")


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token

    Args:
        token: JWT token string to decode

    Returns:
        Decoded token payload as dictionary

    Raises:
        HTTPException: If token is invalid, expired, or malformed
    """
    try:
        # Decode token
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Validate required claims
        if "sub" not in payload:
            raise TokenError("Token missing subject claim")

        if "jti" not in payload:
            raise TokenError("Token missing ID claim")

        if "type" not in payload:
            raise TokenError("Token missing type claim")

        # Validate expiration (jose should handle this, but double-check)
        if "exp" in payload:
            exp_timestamp = payload["exp"]
            if datetime.fromtimestamp(exp_timestamp) < datetime.utcnow():
                raise TokenError("Token has expired")

        return payload

    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenError as e:
        logger.warning(f"Token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def extract_user_id_from_token(token: str) -> str:
    """
    Extract user ID from JWT token

    Args:
        token: JWT token string

    Returns:
        User ID string from token subject

    Raises:
        HTTPException: If token is invalid or missing user ID
    """
    payload = decode_token(token)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


def extract_token_id_from_token(token: str) -> str:
    """
    Extract token ID from JWT token

    Args:
        token: JWT token string

    Returns:
        Token ID string from JWT ID claim

    Raises:
        HTTPException: If token is invalid or missing token ID
    """
    payload = decode_token(token)
    token_id = payload.get("jti")

    if not token_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_id


# Configuration info for debugging
def get_security_config() -> Dict[str, Any]:
    """
    Get current security configuration (for debugging/info)

    Returns:
        Dictionary with security configuration (excludes secret)
    """
    return {
        "jwt_algorithm": JWT_ALGORITHM,
        "access_token_expire_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "refresh_token_expire_days": REFRESH_TOKEN_EXPIRE_DAYS,
        "jwt_secret_set": bool(JWT_SECRET and JWT_SECRET != "your-super-secret-jwt-key-change-in-production"),
        "password_schemes": pwd_context.schemes(),
    }


if __name__ == "__main__":
    # Test the security functions
    print("🔐 Testing security functions...")

    # Test password hashing
    test_password = "testpassword123"
    hashed = hash_password(test_password)
    print(f"✅ Password hashed: {hashed[:50]}...")

    # Test password verification
    is_valid = verify_password(test_password, hashed)
    print(f"✅ Password verification: {is_valid}")

    # Test token creation
    test_data = {"sub": "user123", "email": "test@example.com"}
    access_token = create_access_token(test_data)
    refresh_token = create_refresh_token(test_data)
    print(f"✅ Access token created: {access_token[:50]}...")
    print(f"✅ Refresh token created: {refresh_token[:50]}...")

    # Test token decoding
    decoded_access = decode_token(access_token)
    decoded_refresh = decode_token(refresh_token)
    print(f"✅ Access token decoded: {decoded_access['sub']}")
    print(f"✅ Refresh token decoded: {decoded_refresh['sub']}")

    # Show configuration
    config = get_security_config()
    print(f"✅ Security config: {config}")

    print("🎉 All security tests passed!")
"""
Security utilities for JWT token handling and password management

Provides functions for JWT creation, validation, password hashing,
and token management for the authentication system.
"""

import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, status

# Configure logging
logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    try:
        # Generate salt and hash password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Password hashing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password hashing failed"
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False


def generate_token_id() -> str:
    """Generate a unique token ID"""
    return str(uuid.uuid4())


def create_access_token(data: Dict[str, Any], token_id: Optional[str] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Token payload data
        token_id: Optional token ID for tracking

    Returns:
        JWT token string
    """
    try:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
            "jti": token_id or generate_token_id()
        })

        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"Access token creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token creation failed"
        )


def create_refresh_token(data: Dict[str, Any], token_id: Optional[str] = None) -> str:
    """
    Create a JWT refresh token

    Args:
        data: Token payload data
        token_id: Optional token ID for tracking

    Returns:
        JWT refresh token string
    """
    try:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": token_id or generate_token_id()
        })

        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"Refresh token creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token creation failed"
        )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token

    Args:
        token: JWT token string

    Returns:
        Token payload dictionary

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def extract_user_id_from_token(token: str) -> Optional[str]:
    """Extract user ID from token without full validation"""
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except:
        return None


def extract_token_id_from_token(token: str) -> Optional[str]:
    """Extract token ID from token without full validation"""
    try:
        payload = decode_token(token)
        return payload.get("jti")
    except:
        return None