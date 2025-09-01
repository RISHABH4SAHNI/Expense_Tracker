/**
 * Common Transaction Service
 * 
 * Unified service for handling transactions from both manual entry and AA integration.
 * This service acts as a central hub for all transaction operations.
 */

import { addTransaction as addManualTransaction } from '../../features/manual/manualTransactionService';
import { isAAIntegrationAvailable, aaService } from '../../integrations/aa';
import { insertTransaction, getTransactions } from '../../storage/db';

/**
 * Transaction data model
 * Used by both manual entry and AA integration
 */
export const TRANSACTION_MODEL = {
  id: null,                    // Auto-generated ID
  type: '',                    // 'income' | 'expense'
  amount: 0,                   // Transaction amount (positive number)
  category: '',                // Transaction category
  description: '',             // Transaction description
  date: '',                    // Transaction date (ISO string)
  notes: '',                   // Optional notes
  merchant: '',                // Merchant name (from AA or manual)
  account_id: '',              // Account ID ('manual' for manual entries)
  transaction_id: null,        // External transaction ID (AA)
  metadata: null,              // Additional metadata (JSON string)
  created_at: '',              // Creation timestamp
  updated_at: ''               // Last update timestamp
};

/**
 * Add a transaction (routes to appropriate service)
 * @param {Object} transactionData - Transaction data
 * @param {string} source - 'manual' | 'aa'
 * @returns {Promise<number>} Transaction ID
 */
export const addTransaction = async (transactionData, source = 'manual') => {
  try {
    console.log(`📝 [TransactionService] Adding ${source} transaction`);

    if (source === 'manual') {
      return await addManualTransaction(transactionData);
    } else if (source === 'aa') {
      // TODO: Switch AA integration ON here when permission is granted
      if (isAAIntegrationAvailable()) {
        // Handle AA transaction
        return await insertTransaction({
          ...transactionData,
          account_id: transactionData.account_id || 'aa_account',
          metadata: JSON.stringify({
            source: 'aa',
            imported_at: new Date().toISOString(),
            ...transactionData.metadata
          })
        });
      } else {
        throw new Error('AA integration is currently disabled');
      }
    } else {
      throw new Error(`Unknown transaction source: ${source}`);
    }
  } catch (error) {
    console.error(`❌ [TransactionService] Error adding ${source} transaction:`, error);
    throw error;
  }
};

/**
 * Get all transactions with optional filters
 * @param {Object} filters - Filter options
 * @returns {Promise<Array>} Transactions list
 */
export const getAllTransactions = async (filters = {}) => {
  try {
    console.log('📋 [TransactionService] Fetching transactions with filters:', filters);

    let transactions = await getTransactions();

    // Apply filters
    if (filters.source) {
      transactions = transactions.filter(t => {
        if (filters.source === 'manual') {
          return t.account_id === 'manual';
        } else if (filters.source === 'aa') {
          return t.account_id !== 'manual';
        }
        return true;
      });
    }

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
    console.error('❌ [TransactionService] Error fetching transactions:', error);
    throw error;
  }
};

export default {
  addTransaction,
  getAllTransactions,
  TRANSACTION_MODEL
};