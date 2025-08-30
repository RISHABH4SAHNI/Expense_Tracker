import * as SQLite from 'expo-sqlite';

let db = null;

// Initialize the database
const initDatabase = async () => {
  try {
    db = await SQLite.openDatabaseAsync('expense_tracker.db');
    
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
    
    console.log('Database initialized successfully');
  } catch (error) {
    console.error('Error initializing database:', error);
    throw error;
  }
};

// Get all transactions
const getTransactions = async () => {
  try {
    if (!db) {
      await initDatabase();
    }
    
    const result = await db.getAllAsync(
      'SELECT * FROM transactions ORDER BY date DESC, created_at DESC'
    );
    
    return result || [];
  } catch (error) {
    console.error('Error getting transactions:', error);
    throw error;
  }
};

// Add a new transaction
const addTransaction = async (transaction) => {
  try {
    if (!db) {
      await initDatabase();
    }
    
    const result = await db.runAsync(
      'INSERT INTO transactions (amount, description, category, type, date) VALUES (?, ?, ?, ?, ?)',
      [transaction.amount, transaction.description, transaction.category, transaction.type, transaction.date]
    );
    
    return result.lastInsertRowId;
  } catch (error) {
    console.error('Error adding transaction:', error);
    throw error;
  }
};

// Clear all transactions
const clearTransactions = async () => {
  try {
    if (!db) {
      await initDatabase();
    }
    
    await db.runAsync('DELETE FROM transactions');
    console.log('All transactions cleared');
  } catch (error) {
    console.error('Error clearing transactions:', error);
    throw error;
  }
};

export { initDatabase, getTransactions, addTransaction, clearTransactions };
