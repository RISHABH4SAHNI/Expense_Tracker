/**
 * Storage service - high-level wrapper around the database
 * This maintains backward compatibility while using the new database wrapper
 */

import {
  initDB as initDatabase,
  insertTransaction,
  getTransactions as getTransactionsFromDB,
  getStats
} from '../storage/db';

// Re-export initDatabase for backward compatibility
const initDB = initDatabase;

// Get all transactions
const getTransactions = async () => {
  try {
    return await getTransactionsFromDB();
  } catch (error) {
    console.error('Error getting transactions:', error);
    throw error;
  }
};

// Add a new transaction (wrapper for backward compatibility)
const addTransaction = async (transaction) => {
  return await insertTransaction(transaction);
};

export { initDB as initDatabase, getTransactions, addTransaction };
