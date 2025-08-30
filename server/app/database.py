import asyncpg
from fastapi import Depends
from typing import AsyncGenerator

# Global database pool (set in main.py lifespan)
db_pool = None

def set_db_pool(pool):
    """Set the global database pool"""
    global db_pool
    db_pool = pool

async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """Database dependency for FastAPI routes"""
    if not db_pool:
        # Return a mock connection for development
        yield None
        return

    async with db_pool.acquire() as connection:
        yield connection

async def init_db(pool: asyncpg.Pool):
    """Initialize database tables"""
    if not pool:
        return

    set_db_pool(pool)

    async with pool.acquire() as connection:
        # Create enum types
        await connection.execute("""
            DO $$ BEGIN
                CREATE TYPE transaction_type AS ENUM ('debit', 'credit');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)

        await connection.execute("""
            DO $$ BEGIN
                CREATE TYPE transaction_category AS ENUM (
                    'food', 'transport', 'shopping', 'entertainment', 
                    'bills', 'healthcare', 'education', 'salary', 
                    'investment', 'other'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)

        # Create users table
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                aa_account_id VARCHAR(255) UNIQUE,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create session_tokens table for JWT blacklisting
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS session_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_id VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create accounts table
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_id VARCHAR(255) UNIQUE NOT NULL,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                account_name VARCHAR(255),
                bank_name VARCHAR(255),
                account_type VARCHAR(50),
                balance DECIMAL(15,2) DEFAULT 0.00,
                currency VARCHAR(3) DEFAULT 'INR',
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create transactions table with user association
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                bank_transaction_id VARCHAR(255) UNIQUE NOT NULL,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                ts TIMESTAMP WITH TIME ZONE NOT NULL,
                amount DECIMAL(15,2) NOT NULL CHECK (amount > 0),
                type transaction_type NOT NULL,
                raw_desc TEXT NOT NULL,
                account_id VARCHAR(255) NOT NULL,
                merchant VARCHAR(255),
                category transaction_category,
                processed_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for performance
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_tokens_user_id ON session_tokens(user_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_tokens_token_id ON session_tokens(token_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_tokens_expires_at ON session_tokens(expires_at)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_ts ON transactions(ts DESC)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category)
        """)

        print("✅ Database tables initialized successfully")
        print("   - Users table with authentication support")
        print("   - Session tokens table for JWT blacklisting")
        print("   - Accounts table with user association")
        print("   - Transactions table with user association")
        print("   - All indexes created for optimal performance")

async def close_db():
    """Close database connections"""
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None