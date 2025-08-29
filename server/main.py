from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncpg
import redis.asyncio as redis
from app.routes import transactions, qa
from app.database import get_db, init_db, close_db
import os

# Global connections
db_pool = None
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global db_pool, redis_client

    # Startup
    database_url = os.getenv("DATABASE_URL", "postgresql://expenseuser:expensepass@localhost:5432/expensedb")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Try to connect to PostgreSQL (optional for development)
    try:
        db_pool = await asyncpg.create_pool(database_url)
        await init_db(db_pool)
        print("✅ Connected to PostgreSQL")
    except Exception as e:
        print(f"⚠️  PostgreSQL connection failed: {e}")
        print("⚠️  Running without database (development mode)")

    # Try to connect to Redis (optional for development)
    try:
        redis_client = redis.from_url(redis_url)
        await redis_client.ping()
        print("✅ Connected to Redis")

        # Pass Redis client to transactions module
        from app.routes.transactions import set_redis_client
        set_redis_client(redis_client)

    except Exception as e:
        print(f"⚠️  Redis connection failed: {e}")
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
    description="Mobile-first personal finance app with AI-powered features",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for Expo development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:19006"],  # Expo default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"ok": True}

# Include routers
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(qa.router, prefix="/qa", tags=["qa"])

# Import and include jobs router
from app.routes import jobs
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])

# Example: Run with uvicorn main:app --reload --host 0.0.0.0 --port 8000