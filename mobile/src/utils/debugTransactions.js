/**
 * Debug utilities for testing manual transactions
 * Use these functions in the console to test the flow
 */

import { addTransaction } from '../services/transactions/transactionService';
import { initDB, getTransactions, clearAllData } from '../storage/db';

/**
 * Test adding a sample transaction
 */
export const testAddTransaction = async () => {
  try {
    console.log('🧪 Testing manual transaction addition...');

    const sampleTransaction = {
      type: 'expense',
      amount: 25.50,
      category: 'Food & Dining',
      description: 'Lunch at cafe',
      merchant: 'Coffee Shop',
      date: new Date().toISOString().split('T')[0],
      notes: 'Test transaction from debug utility'
    };

    const transactionId = await addTransaction(sampleTransaction, 'manual');
    console.log('✅ Test transaction added with ID:', transactionId);

    // Verify it was saved
    const transactions = await getTransactions();
    const addedTransaction = transactions.find(t => t.id === transactionId);
    console.log('✅ Verified transaction:', addedTransaction);

    return { success: true, transactionId, transaction: addedTransaction };
  } catch (error) {
    console.error('❌ Test transaction failed:', error);
    return { success: false, error: error.message };
  }
};

/**
 * Test the database connection
 */
export const testDatabase = async () => {
  try {
    console.log('🧪 Testing database connection...');
    await initDB();
    console.log('✅ Database initialized successfully');

    const transactions = await getTransactions();
    console.log(`✅ Found ${transactions.length} existing transactions`);

    return { success: true, transactionCount: transactions.length };
  } catch (error) {
    console.error('❌ Database test failed:', error);
    return { success: false, error: error.message };
  }
};

/**
 * Clear all test data (use with caution!)
 */
export const clearTestData = async () => {
  await clearAllData();
  console.log('🧹 All test data cleared');
};

export default { testAddTransaction, testDatabase, clearTestData };