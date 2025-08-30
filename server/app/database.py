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

        # Create AA enum types
        await connection.execute("""
            DO $$ BEGIN
                CREATE TYPE aa_consent_status AS ENUM (
                    'pending', 'active', 'expired', 'revoked', 'failed'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)

        await connection.execute("""
            DO $$ BEGIN
                CREATE TYPE aa_sync_status AS ENUM (
                    'running', 'completed', 'failed', 'cancelled'
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

        # Create AA consent table
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS aa_consents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                ref_id VARCHAR(255) UNIQUE NOT NULL,
                status aa_consent_status NOT NULL DEFAULT 'pending',
                encrypted_token TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_polled_at TIMESTAMP WITH TIME ZONE
            )
        """)

        # Create AA accounts table
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS aa_accounts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                aa_account_id VARCHAR(255) NOT NULL,
                display_name VARCHAR(255),
                last_sync_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, aa_account_id)
            )
        """)

        # Create AA sync logs table
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS aa_sync_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                account_id UUID REFERENCES aa_accounts(id) ON DELETE CASCADE,
                start_ts TIMESTAMP WITH TIME ZONE NOT NULL,
                end_ts TIMESTAMP WITH TIME ZONE,
                status aa_sync_status NOT NULL DEFAULT 'running',
                inserted_count INTEGER DEFAULT 0 NOT NULL,
                error_text TEXT,
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
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_aa_consents_user_id ON aa_consents(user_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_aa_consents_status ON aa_consents(status)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_aa_consents_ref_id ON aa_consents(ref_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_aa_accounts_user_id ON aa_accounts(user_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_aa_accounts_aa_account_id ON aa_accounts(aa_account_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_aa_sync_logs_user_id ON aa_sync_logs(user_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_aa_sync_logs_account_id ON aa_sync_logs(account_id)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_aa_sync_logs_status ON aa_sync_logs(status)
        """)
        await connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_aa_sync_logs_start_ts ON aa_sync_logs(start_ts)
        """)

        print("✅ Database tables initialized successfully")
        print("   - Users table with authentication support")
        print("   - Session tokens table for JWT blacklisting")
        print("   - Accounts table with user association")
        print("   - Transactions table with user association")
        print("   - AA consent table for Account Aggregator consent management")
        print("   - AA accounts table for Account Aggregator account tracking")
        print("   - AA sync logs table for audit and monitoring")
        print("   - All indexes created for optimal performance")

async def close_db():
    """Close database connections"""
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None