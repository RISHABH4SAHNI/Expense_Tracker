/**
 * Manual Transaction Service
 * 
 * Handles CRUD operations for manually entered transactions.
 * Stores data locally and syncs with Firebase when available.
 */

import { insertTransaction, getTransactions } from '../../storage/db';
import { addExpense as addFirebaseExpense, getCurrentUser } from '../../services/firebase';

// Transaction categories
export const TRANSACTION_CATEGORIES = {
  INCOME: [
    'Salary',
    'Freelance',
    'Investment',
    'Business',
    'Rental',
    'Gift',
    'Bonus',
    'Other Income'
  ],
  EXPENSE: [
    'Food & Dining',
    'Transportation',
    'Shopping',
    'Entertainment',
    'Bills & Utilities',
    'Healthcare',
    'Education',
    'Travel',
    'Insurance',
    'Investment',
    'Other Expense'
  ]
};

/**
 * Validate transaction data
 * @param {Object} transaction - Transaction to validate
 * @returns {Object} Validation result
 */
const validateTransaction = (transaction) => {
  const errors = [];

  if (!transaction.type || !['income', 'expense'].includes(transaction.type)) {
    errors.push('Transaction type must be either "income" or "expense"');
  }

  if (!transaction.amount || transaction.amount <= 0) {
    errors.push('Amount must be a positive number');
  }

  if (!transaction.category || transaction.category.trim() === '') {
    errors.push('Category is required');
  }

  if (!transaction.date) {
    errors.push('Date is required');
  }

  // Validate date format
  if (transaction.date && isNaN(new Date(transaction.date).getTime())) {
    errors.push('Date must be in a valid format (YYYY-MM-DD)');
  }

  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * Add a new manual transaction
 * @param {Object} transactionData - Transaction data
 * @returns {Promise<number>} Transaction ID
 */
export const addTransaction = async (transactionData) => {
  try {
    // Validate input
    const validation = validateTransaction(transactionData);
    if (!validation.isValid) {
      throw new Error(`Validation failed: ${validation.errors.join(', ')}`);
    }

    // Prepare transaction object
    const transaction = {
      type: transactionData.type,
      amount: parseFloat(transactionData.amount),
      category: transactionData.category.trim(),
      description: transactionData.description?.trim() || '',
      merchant: transactionData.merchant?.trim() || transactionData.description?.trim() || '',
      date: transactionData.date,
      notes: transactionData.notes?.trim() || '',
      // Mark as manual entry
      account_id: 'manual',
      transaction_id: null,
      metadata: JSON.stringify({
        source: 'manual',
        created_by: 'user',
        created_at: new Date().toISOString()
      })
    };

    // Insert into local database
    const transactionId = await insertTransaction(transaction);
    console.log('✅ Transaction saved locally with ID:', transactionId);

    // Sync with Firebase if user is authenticated
    try {
      const currentUser = getCurrentUser();
      if (currentUser) {
        console.log('🔄 [TransactionService] Attempting Firebase sync...');
        await addFirebaseExpense({
          ...transaction,
          localId: transactionId // Keep reference to local ID
        });
        console.log('✅ [TransactionService] Transaction synced to Firebase');
      } else {
        console.log('ℹ️ [TransactionService] Firebase user not available, operating in offline mode');
      }
    } catch (firebaseError) {
      console.warn('⚠️ [TransactionService] Firebase sync failed, continuing in offline mode:', firebaseError.message);
    }

    console.log('✅ [TransactionService] Manual transaction processed successfully:', transactionId);
    return transactionId;
  } catch (error) {
    console.error('❌ Error adding manual transaction:', error);
    // Re-throw with more user-friendly message if possible
    if (error.message.includes('Validation failed')) {
      throw error; // Keep validation errors as-is
    }
    throw error;
  }
};

/**
 * Edit an existing transaction
 * @param {number} transactionId - Transaction ID
 * @param {Object} updatedData - Updated transaction data
 * @returns {Promise<boolean>} Success status
 */
export const editTransaction = async (transactionId, updatedData) => {
  try {
    // TODO: Implement edit functionality
    // This requires adding UPDATE functionality to the database layer
    console.log('🔄 Edit transaction not yet implemented');
    throw new Error('Edit functionality coming soon');
  } catch (error) {
    console.error('❌ Error editing transaction:', error);
    throw error;
  }
};

/**
 * Delete a transaction
 * @param {number} transactionId - Transaction ID
 * @returns {Promise<boolean>} Success status
 */
export const deleteTransaction = async (transactionId) => {
  try {
    // TODO: Implement delete functionality
    // This requires adding DELETE functionality to the database layer
    console.log('🔄 Delete transaction not yet implemented');
    throw new Error('Delete functionality coming soon');
  } catch (error) {
    console.error('❌ Error deleting transaction:', error);
    throw error;
  }
};

/**
 * List transactions with optional filters
 * @param {Object} filters - Filter options
 * @returns {Promise<Array>} Filtered transactions
 */
export const listTransactions = async (filters = {}) => {
  try {
    let transactions = await getTransactions();

    // Apply filters
    if (filters.type) {
      transactions = transactions.filter(t => t.type === filters.type);
    }

    if (filters.category) {
      transactions = transactions.filter(t => t.category === filters.category);
    }

    if (filters.dateFrom || filters.dateTo) {
      transactions = transactions.filter(t => {
        const transactionDate = new Date(t.date);
        let matchesDate = true;

        if (filters.dateFrom) {
          matchesDate = matchesDate && transactionDate >= new Date(filters.dateFrom);
        }

        if (filters.dateTo) {
          matchesDate = matchesDate && transactionDate <= new Date(filters.dateTo);
        }

        return matchesDate;
      });
    }

    return transactions;
  } catch (error) {
    console.error('❌ Error listing transactions:', error);
    throw error;
  }
};

export default {
  addTransaction,
  editTransaction,
  deleteTransaction,
  listTransactions,
  TRANSACTION_CATEGORIES
};