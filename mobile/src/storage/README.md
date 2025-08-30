# SQLite Database Wrapper for Expo

A comprehensive SQLite wrapper for Expo applications with encryption key management, merchant overrides, and pagination support.

## Features

- ✅ Modern expo-sqlite async API
- 🔐 Encryption key management with SecureStore/AsyncStorage
- 🏪 Merchant category overrides
- 📊 Pagination and filtering support
- 🚀 Performance optimized with indexes
- 🔄 Future SQLCipher compatibility
- 📝 TypeScript-like type definitions
- 🧪 Comprehensive examples and tests

## Installation

Required dependencies:
```bash
npx expo install expo-sqlite expo-secure-store @react-native-async-storage/async-storage
```

## Basic Usage

### Initialize Database

```javascript
import { initDB } from '../storage/db';

// Initialize database (call once on app startup)
await initDB();
```

### Insert Transactions

```javascript
import { insertTransaction } from '../storage/db';
import { TRANSACTION_TYPES, TRANSACTION_CATEGORIES } from '../storage/types';

const transaction = {
  amount: 45.67,
  description: 'Grocery shopping',
  merchant: 'Whole Foods Market',
  category: TRANSACTION_CATEGORIES.GROCERIES,
  type: TRANSACTION_TYPES.EXPENSE,
  date: new Date().toISOString(),
  metadata: { items: 15, paymentMethod: 'credit' }
};

const transactionId = await insertTransaction(transaction);
```

### Get Transactions with Pagination

```javascript
import { getTransactions } from '../storage/db';

// Get all transactions
const allTransactions = await getTransactions();

// Get with pagination
const recentTransactions = await getTransactions({
  limit: 20,
  offset: 0
});

// Get with filters
const expenses = await getTransactions({
  type: 'expense',
  category: 'Food & Dining',
  startDate: '2023-01-01',
  limit: 50
});
```

### Merchant Overrides

```javascript
import { setMerchantOverride, getMerchantOverrides } from '../storage/db';

// Set an override so all Starbucks transactions are categorized as "Food & Dining"
await setMerchantOverride('Starbucks', 'Food & Dining');

// Get all overrides
const overrides = await getMerchantOverrides();
```

## API Reference

### Core Functions

#### `initDB()`
Initializes the database, creates tables, and sets up encryption key.
- Creates `transactions` and `merchant_overrides` tables
- Sets up database indexes for performance
- Initializes encryption key management

#### `insertTransaction(transaction)`
Inserts a new transaction into the database.

**Parameters:**
- `transaction` (Object): Transaction data
  - `amount` (number): Transaction amount
  - `description` (string): Transaction description
  - `merchant` (string): Merchant name
  - `category` (string): Transaction category
  - `type` ('income'|'expense'): Transaction type
  - `date` (string): ISO date string
  - `account_id` (string, optional): Account identifier
  - `transaction_id` (string, optional): Unique transaction ID
  - `metadata` (Object, optional): Additional metadata

**Returns:** `Promise<number>` - The inserted transaction ID

#### `getTransactions(options)`
Retrieves transactions with optional filtering and pagination.

**Parameters:**
- `options` (Object, optional):
  - `limit` (number): Maximum results (default: 50)
  - `offset` (number): Results to skip (default: 0)
  - `type` (string): Filter by 'income' or 'expense'
  - `category` (string): Filter by category
  - `startDate` (string): Filter transactions after this date
  - `endDate` (string): Filter transactions before this date

**Returns:** `Promise<Array>` - Array of transaction objects

#### `setMerchantOverride(merchant, category)`
Sets a category override for a specific merchant.

**Parameters:**
- `merchant` (string): Merchant name
- `category` (string): Category to override with

#### `getMerchantOverrides()`
Gets all merchant category overrides.

**Returns:** `Promise<Array>` - Array of override objects

#### `getStats()`
Gets database statistics including totals and counts.

**Returns:** `Promise<Object>` - Statistics object with totals

## Database Schema

### Transactions Table
```sql
CREATE TABLE transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  amount REAL NOT NULL,
  description TEXT,
  merchant TEXT,
  category TEXT,
  type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
  date TEXT NOT NULL,
  account_id TEXT,
  transaction_id TEXT UNIQUE,
  metadata TEXT, -- JSON string
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Merchant Overrides Table
```sql
CREATE TABLE merchant_overrides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  merchant TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Security & Encryption

### Encryption Key Management
- Uses Expo SecureStore for secure key storage
- Falls back to AsyncStorage if SecureStore is unavailable
- Generates 256-bit encryption keys
- Ready for SQLCipher integration

### Future SQLCipher Integration
To upgrade to full database encryption using SQLCipher:

1. Replace `expo-sqlite` with `@op-engineering/op-sqlite`
2. Uncomment the encryption line in `initDB()`:
   ```javascript
   await db.execAsync(`PRAGMA key = '${encryptionKey}';`);
