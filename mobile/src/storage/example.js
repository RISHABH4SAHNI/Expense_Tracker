/**
 * Example usage of the SQLite wrapper
 * 
 * This file demonstrates how to use all the database functions
 * and can be imported into your components for testing
 */

import {
  initDB,
  insertTransaction,
  getTransactions,
  setMerchantOverride,
  getMerchantOverride,
  getMerchantOverrides,
  getStats,
  clearAllData
} from './db';

import { TRANSACTION_CATEGORIES, TRANSACTION_TYPES, TransactionUtils } from './types';

/**
 * Example: Initialize database and add sample data
 */
export const setupSampleData = async () => {
  try {
    console.log('🚀 Setting up sample data...');

    // Initialize database
    await initDB();

    // Add sample transactions
    const sampleTransactions = [
      {
        amount: 2500.00,
        description: 'Monthly salary',
        merchant: 'Tech Corp Inc',
        category: TRANSACTION_CATEGORIES.SALARY,
        type: TRANSACTION_TYPES.INCOME,
        date: new Date().toISOString(),
        metadata: { payPeriod: 'monthly', employeeId: '12345' }
      },
      {
        amount: 45.67,
        description: 'Grocery shopping',
        merchant: 'Whole Foods Market',
        category: TRANSACTION_CATEGORIES.GROCERIES,
        type: TRANSACTION_TYPES.EXPENSE,
        date: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), // Yesterday
        metadata: { items: 15, paymentMethod: 'credit' }
      },
      {
        amount: 12.50,
        description: 'Coffee and pastry',
        merchant: 'Starbucks',
        category: TRANSACTION_CATEGORIES.FOOD_DINING,
        type: TRANSACTION_TYPES.EXPENSE,
        date: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      },
      {
        amount: 89.99,
        description: 'Monthly internet bill',
        merchant: 'Comcast',
        category: TRANSACTION_CATEGORIES.UTILITIES,
        type: TRANSACTION_TYPES.EXPENSE,
        date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(), // 1 week ago
      }
    ];

    // Insert transactions
    for (const tx of sampleTransactions) {
      const validation = TransactionUtils.validateTransaction(tx);
      if (validation.isValid) {
        await insertTransaction(tx);
      } else {
        console.error('❌ Invalid transaction:', validation.errors);
      }
    }

    // Set up merchant overrides
    await setMerchantOverride('Starbucks', TRANSACTION_CATEGORIES.FOOD_DINING);
    await setMerchantOverride('McDonald\'s', TRANSACTION_CATEGORIES.FOOD_DINING);
    await setMerchantOverride('Shell Gas Station', TRANSACTION_CATEGORIES.TRANSPORTATION);

    console.log('✅ Sample data setup complete!');

  } catch (error) {
    console.error('❌ Error setting up sample data:', error);
  }
};

/**
 * Example: Demonstrate all database operations
 */
export const demonstrateOperations = async () => {
  try {
    console.log('🔍 Demonstrating database operations...');

    // Get all transactions
    const allTransactions = await getTransactions();
    console.log(`📊 Total transactions: ${allTransactions.length}`);

    // Get transactions with pagination
    const recentTransactions = await getTransactions({ limit: 2, offset: 0 });
    console.log(`📊 Recent transactions (limit 2):`, recentTransactions);

    // Get only expenses
    const expenses = await getTransactions({ type: TRANSACTION_TYPES.EXPENSE });
    console.log(`💸 Total expenses: ${expenses.length}`);

    // Get transactions for a specific category
    const foodTransactions = await getTransactions({ 
      category: TRANSACTION_CATEGORIES.FOOD_DINING 
    });
    console.log(`🍔 Food transactions: ${foodTransactions.length}`);

    // Get merchant overrides
    const overrides = await getMerchantOverrides();
    console.log(`🏪 Merchant overrides:`, overrides);

    // Get specific merchant override
    const starbucksOverride = await getMerchantOverride('Starbucks');
    console.log(`☕ Starbucks override:`, starbucksOverride);

    // Get database statistics
    const stats = await getStats();
    console.log(`📈 Database stats:`, stats);

    // Format amounts for display
    allTransactions.forEach(tx => {
      const formattedAmount = TransactionUtils.formatAmount(tx.amount, tx.type);
      console.log(`💰 ${tx.description}: ${formattedAmount}`);
    });

  } catch (error) {
    console.error('❌ Error demonstrating operations:', error);
  }
};

/**
 * Example: Test merchant override functionality
 */
export const testMerchantOverrides = async () => {
  try {
    console.log('🧪 Testing merchant overrides...');

    // Add a transaction with a new merchant
    const testTransaction = {
      amount: 25.99,
      description: 'Fast food lunch',
      merchant: 'Burger King',
      category: TRANSACTION_CATEGORIES.MISCELLANEOUS, // Will be overridden
      type: TRANSACTION_TYPES.EXPENSE,
      date: new Date().toISOString()
    };

    await insertTransaction(testTransaction);
    console.log('✅ Test transaction added');

    // Set merchant override
    await setMerchantOverride('Burger King', TRANSACTION_CATEGORIES.FOOD_DINING);
    console.log('✅ Merchant override set');

    // Add another transaction from the same merchant
    const anotherTransaction = {
      ...testTransaction,
      amount: 8.99,
      description: 'Coffee',
      category: TRANSACTION_CATEGORIES.MISCELLANEOUS // Will be automatically overridden
    };

    await insertTransaction(anotherTransaction);
    console.log('✅ Second transaction added with auto-override');

    // Verify the override worked
    const burgerKingTransactions = await getTransactions({ merchant: 'Burger King' });
    console.log('🍔 Burger King transactions:', burgerKingTransactions);

  } catch (error) {
    console.error('❌ Error testing merchant overrides:', error);
  }
};