/**
 * SQLite Database wrapper for Expense Tracker
 * Handles transactions, merchant overrides, and provides encryption key management
 */

import * as SQLite from 'expo-sqlite';
import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Database configuration
const DATABASE_NAME = 'ExpenseTracker.db';
const ENCRYPTION_KEY_NAME = 'expense_tracker_key';

// Global database instance
let db = null;
let encryptionKey = null;

/**
 * Generate a secure encryption key
 */
const generateEncryptionKey = async () => {
  try {
    // Generate a random UUID as encryption key
    const key = Crypto.randomUUID();
    return key;
  } catch (error) {
    console.warn('⚠️ Crypto.randomUUID not available, using fallback');
    // Fallback to timestamp-based key
    return 'expense_tracker_' + Date.now() + '_' + Math.random().toString(36);
  }
};

/**
 * Initialize encryption key
 */
const initializeEncryptionKey = async () => {
  try {
    // Try SecureStore first (iOS Keychain, Android Keystore)
    encryptionKey = await SecureStore.getItemAsync(ENCRYPTION_KEY_NAME);
    if (!encryptionKey) {
      encryptionKey = await generateEncryptionKey();
      // Store in SecureStore
      await SecureStore.setItemAsync(ENCRYPTION_KEY_NAME, encryptionKey);
      console.log('🔐 New encryption key generated and stored securely');
    } else {
      console.log('🔐 Encryption key loaded from secure storage');
    }
  } catch (error) {
    console.warn('⚠️ SecureStore not available, using AsyncStorage fallback');
    
    // Fallback to AsyncStorage if SecureStore fails
    try {
      encryptionKey = await AsyncStorage.getItem(ENCRYPTION_KEY_NAME);
      if (!encryptionKey) {
        encryptionKey = await generateEncryptionKey();
        await AsyncStorage.setItem(ENCRYPTION_KEY_NAME, encryptionKey);
        console.log('🔐 New encryption key generated and stored in AsyncStorage');
      } else {
        console.log('🔐 Encryption key loaded from AsyncStorage');
      }
    } catch (fallbackError) {
      console.error('❌ Failed to initialize encryption key:', fallbackError);
      // Use a default key for development (not recommended for production)
      encryptionKey = 'development_key_replace_in_production_' + Date.now();
      console.log('🔐 Using fallback development key');
    }
  }
};

/**
 * Check and perform database migrations
 */
const migrateDatabase = async () => {
  try {
    // Get current table schema
    const tableInfo = await db.getAllAsync("PRAGMA table_info(transactions)");
    const columns = tableInfo.map(col => col.name);
    
    console.log('📊 Current table columns:', columns);
    
    // Check if merchant column exists
    if (!columns.includes('merchant')) {
      console.log('🔄 Adding merchant column...');
      await db.execAsync('ALTER TABLE transactions ADD COLUMN merchant TEXT DEFAULT ""');
    }
    
    // Check if account_id column exists
    if (!columns.includes('account_id')) {
      console.log('🔄 Adding account_id column...');
      await db.execAsync('ALTER TABLE transactions ADD COLUMN account_id TEXT');
    }
    
    // Check if transaction_id column exists
    if (!columns.includes('transaction_id')) {
      console.log('🔄 Adding transaction_id column...');
      await db.execAsync('ALTER TABLE transactions ADD COLUMN transaction_id TEXT');
    }
    
    // Check if metadata column exists
    if (!columns.includes('metadata')) {
      console.log('🔄 Adding metadata column...');
      await db.execAsync('ALTER TABLE transactions ADD COLUMN metadata TEXT');
    }
    
    // Check if updated_at column exists
    if (!columns.includes('updated_at')) {
      console.log('🔄 Adding updated_at column...');
      await db.execAsync('ALTER TABLE transactions ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP');
    }
    
    console.log('✅ Database migration completed');
    
  } catch (error) {
    console.error('❌ Error during database migration:', error);
    throw error;
  }
};

/**
 * Initialize database and create tables
 */
const initDB = async () => {
  try {
    // Initialize encryption key first
    await initializeEncryptionKey();
    
    // Open database
    db = await SQLite.openDatabaseAsync(DATABASE_NAME);
    
    // Enable foreign keys and WAL mode for better performance
    await db.execAsync('PRAGMA foreign_keys = ON;');
    await db.execAsync('PRAGMA journal_mode = WAL;');
    
    // Create transactions table with basic structure (for new installs)
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        description TEXT,
        category TEXT,
        type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
        date TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );
    `);
    
    // Perform database migrations (add missing columns)
    await migrateDatabase();
    
    // Create merchant overrides table
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS merchant_overrides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );
    `);
    
    // Create indexes for better performance
    try {
      await db.execAsync('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);');
      await db.execAsync('CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);');
      await db.execAsync('CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);');
      
      // Only create merchant index if column exists
      const tableInfo = await db.getAllAsync("PRAGMA table_info(transactions)");
      const columns = tableInfo.map(col => col.name);
      if (columns.includes('merchant')) {
        await db.execAsync('CREATE INDEX IF NOT EXISTS idx_transactions_merchant ON transactions(merchant);');
      }
      
      await db.execAsync('CREATE INDEX IF NOT EXISTS idx_merchant_overrides_merchant ON merchant_overrides(merchant);');
    } catch (indexError) {
      console.warn('⚠️ Some indexes could not be created:', indexError.message);
    }
    
    console.log('✅ Database initialized successfully');
    
  } catch (error) {
    console.error('❌ Error initializing database:', error);
    throw error;
  }
};

/**
 * Insert a new transaction
 */
const insertTransaction = async (transaction) => {
  try {
    if (!db) await initDB();
    
    const {
      amount,
      description = '',
      merchant = '',
      category = '',
      type,
      date,
      account_id = null,
      transaction_id = null,
      metadata = null
    } = transaction;
    
    const result = await db.runAsync(
      'INSERT INTO transactions (amount, description, merchant, category, type, date, account_id, transaction_id, metadata, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
      [amount, description, merchant, category, type, date, account_id, transaction_id, metadata, new Date().toISOString()]
    );
    
    console.log('✅ Transaction inserted with ID:', result.lastInsertRowId);
    return result.lastInsertRowId;
  } catch (error) {
    console.error('❌ Error inserting transaction:', error);
    throw error;
  }
};

/**
 * Get all transactions
 */
const getTransactions = async () => {
  try {
    if (!db) await initDB();
    
    const transactions = await db.getAllAsync(
      'SELECT * FROM transactions ORDER BY date DESC, created_at DESC'
    );
    
    return transactions.map(transaction => ({
      ...transaction,
      amount: parseFloat(transaction.amount)
    }));
  } catch (error) {
    console.error('❌ Error getting transactions:', error);
    throw error;
  }
};

/**
 * Reset database (for development/testing)
 * Drops and recreates all tables
 */
const resetDatabase = async () => {
  try {
    if (!db) await initDB();
    
    await db.execAsync('DROP TABLE IF EXISTS transactions');
    await db.execAsync('DROP TABLE IF EXISTS merchant_overrides');
    
    console.log('🗑️ Database reset - all tables dropped');
    
    // Reinitialize
    await initDB();
    
  } catch (error) {
    console.error('❌ Error resetting database:', error);
    throw error;
  }
};

/**
 * Clear all data (for development/testing)
 */
const clearAllData = async () => {
  try {
    if (!db) await initDB();
    
    await db.execAsync('DELETE FROM transactions');
    await db.execAsync('DELETE FROM merchant_overrides');
    
    console.log('🧹 All data cleared from database');
  } catch (error) {
    console.error('❌ Error clearing data:', error);
    throw error;
  }
};

// Export all functions
export {
  initDB,
  insertTransaction,
  getTransactions,
  clearAllData,
  resetDatabase
};
