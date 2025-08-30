-- Database initialization script for Expense Tracker

-- Create database and user (run as postgres superuser)
-- CREATE DATABASE expensedb;
-- CREATE USER expenseuser WITH PASSWORD 'expensepass';
-- GRANT ALL PRIVILEGES ON DATABASE expensedb TO expenseuser;

-- Connect to expensedb and run the following:

-- Enable UUID extension for generating unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
CREATE TYPE transaction_type AS ENUM ('debit', 'credit');
CREATE TYPE transaction_category AS ENUM (
    'food', 'transport', 'shopping', 'entertainment', 
    'bills', 'healthcare', 'education', 'salary', 
    'investment', 'other'
);

-- Create users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Account Aggregator integration fields
    refresh_token_hash VARCHAR(255),
    aa_consent_token VARCHAR(255),
    aa_account_id VARCHAR(255)
);

-- Create session_tokens table for JWT management
CREATE TABLE IF NOT EXISTS session_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_id VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- Create indexes for session_tokens table
CREATE INDEX IF NOT EXISTS idx_session_tokens_user_expires ON session_tokens(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_session_tokens_token_id ON session_tokens(token_id);
CREATE INDEX IF NOT EXISTS idx_session_tokens_expires_at ON session_tokens(expires_at);
);

-- Create accounts table
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(255) UNIQUE NOT NULL,
    account_name VARCHAR(255),
    bank_name VARCHAR(255),
    account_type VARCHAR(50),
    balance DECIMAL(15,2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'INR',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Raw transaction data from bank API
    bank_transaction_id VARCHAR(255) UNIQUE NOT NULL,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    amount DECIMAL(15,2) NOT NULL CHECK (amount > 0),
    type transaction_type NOT NULL,
    raw_desc TEXT NOT NULL,
    account_id VARCHAR(255) NOT NULL,

    -- Processed fields
    merchant VARCHAR(255),
    category transaction_category,
    processed_at TIMESTAMP WITH TIME ZONE,

    -- System fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key to accounts table
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_ts ON transactions(ts DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant ON transactions(merchant);
CREATE INDEX IF NOT EXISTS idx_transactions_amount ON transactions(amount);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);

-- Create sync_logs table to track synchronization operations
CREATE TABLE IF NOT EXISTS sync_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id VARCHAR(255) NOT NULL,
    from_date DATE NOT NULL,
    to_date DATE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL, -- 'success', 'partial', 'failed'
    inserted_count INTEGER DEFAULT 0,
    updated_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    error_details JSONB,
    sync_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create index for sync logs
CREATE INDEX IF NOT EXISTS idx_sync_logs_account_id ON sync_logs(account_id);
CREATE INDEX IF NOT EXISTS idx_sync_logs_timestamp ON sync_logs(sync_timestamp DESC);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers to automatically update updated_at
CREATE TRIGGER update_accounts_updated_at 
    BEFORE UPDATE ON accounts 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_transactions_updated_at 
    BEFORE UPDATE ON transactions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Clean up expired session tokens (run periodically)
-- DELETE FROM session_tokens WHERE expires_at < CURRENT_TIMESTAMP;

CREATE TRIGGER update_transactions_updated_at 
    BEFORE UPDATE ON transactions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for development (optional)
INSERT INTO accounts (account_id, account_name, bank_name, account_type, balance) 
VALUES 
    ('acc_12345', 'Primary Savings', 'HDFC Bank', 'savings', 25000.00),
    ('acc_67890', 'Salary Account', 'ICICI Bank', 'current', 45000.00)
ON CONFLICT (account_id) DO NOTHING;

-- Sample transactions for development
INSERT INTO transactions (
    bank_transaction_id, ts, amount, type, raw_desc, account_id, 
    merchant, category, processed_at
) VALUES 
    ('txn_001', '2024-01-15 10:30:00+05:30', 250.00, 'debit', 'SWIGGY*ORDER', 'acc_12345', 'Swiggy', 'food', CURRENT_TIMESTAMP),
    ('txn_002', '2024-01-14 15:45:00+05:30', 1200.00, 'debit', 'BIG BAZAAR MUMBAI', 'acc_12345', 'Big Bazaar', 'shopping', CURRENT_TIMESTAMP),
    ('txn_003', '2024-01-13 09:15:00+05:30', 50000.00, 'credit', 'SALARY CREDIT', 'acc_67890', null, 'salary', CURRENT_TIMESTAMP)
ON CONFLICT (bank_transaction_id) DO NOTHING;

-- Insert sample user for development (password: 'testpassword123')
INSERT INTO users (email, password_hash) 
VALUES (
    'test@example.com', 
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6.6Y8r1xCC'
) ON CONFLICT (email) DO NOTHING;

-- Note: The password hash above is for 'testpassword123'
-- In production, users should register through the API with proper password hashing

-- Cleanup query for session tokens (can be run periodically)
-- DELETE FROM session_tokens WHERE expires_at < CURRENT_TIMESTAMP;