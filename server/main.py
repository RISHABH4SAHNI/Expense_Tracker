from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import asyncpg
import redis.asyncio as redis
import logging

from app.routes import transactions, qa, auth, aa, aa_admin
from app.database import get_db, init_db, close_db
import os


# Global connections
db_pool = None
redis_client = None
from app.routes import sync

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to optionally set request.state.user when authentication is present

    This allows routes to access user information without requiring authentication
    by checking request.state.user directly.
    """

    async def dispatch(self, request: Request, call_next):
        # Initialize user state
        request.state.user = None

        # Try to extract user from Authorization header (if present)
        try:
            from app.deps.auth import get_optional_user
            # This will set request.state.user if authentication is valid
            await get_optional_user(request, None, None)
        except Exception:
            # If authentication fails, user remains None
            pass

        response = await call_next(request)
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global db_pool, redis_client

    # Startup
    database_url = os.getenv("DATABASE_URL", "postgresql://expenseuser:expensepass@localhost:5433/expensedb")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Try to connect to PostgreSQL (optional for development)
    try:
        db_pool = await asyncpg.create_pool(database_url)
        await init_db(db_pool)
        print("✅ Connected to PostgreSQL")
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed: {e}")
        print("⚠️  Running without database (development mode)")

    # Try to connect to Redis (optional for development)
    try:
        redis_client = redis.from_url(redis_url)
        await redis_client.ping()
        print("✅ Connected to Redis")

        # Pass Redis client to modules that need it
        from app.routes.transactions import set_redis_client as set_transactions_redis
        from app.routes.auth import set_redis_client as set_auth_redis
        from app.services.sync import set_redis_client as set_sync_redis
        from app.workers.aa_worker import AAWorker

        set_transactions_redis(redis_client)
        set_auth_redis(redis_client)
        set_sync_redis(redis_client)

    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        print("⚠️  Running without Redis (development mode)")

    print("🚀 FastAPI server started successfully!")

    yield

    # Shutdown
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()
    print("❌ Server shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Expense Tracker API",
    description="Mobile-first personal finance app with AI-powered features and secure authentication",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    lifespan=lifespan
)

app.add_middleware(CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",     # React development
        "http://localhost:19006",    # Expo web development  
        "exp://192.168.*",          # Expo mobile development (local network)
        "https://*.expo.dev",        # Expo hosted apps
        "*"                         # Allow all for development (remove in production)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware to set request.state.user
app.add_middleware(AuthMiddleware)

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint with authentication status

    Returns system status and optionally user information if authenticated.
    """
    return {
        "ok": True,
        "timestamp": "2025-08-30T10:59:17Z", 
        "version": "1.0.0",
        "services": {
            "database": bool(db_pool),
            "redis": bool(redis_client),
            "authentication": True
        }
    }

# Authentication status endpoint  
@app.get("/auth-status")
async def auth_status(request: Request):
    """Check authentication status from middleware"""
    user = getattr(request.state, 'user', None)
    return {
        "authenticated": user is not None,
        "user": user.to_dict() if user else None
    }

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(aa.router)  # AA router already has /aa prefix
app.include_router(qa.router, prefix="/qa", tags=["qa"])

# Include dev-only AA routes (only available when DEV_MODE=true)
from app.config import is_dev_mode
if is_dev_mode():
    from app.routes import dev_aa
    app.include_router(dev_aa.router)  # dev_aa router already has /aa/dev prefix

# Import and include jobs router
from app.routes import jobs
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])

# Example: Run with uvicorn main:app --reload --host 0.0.0.0 --port 8000