/**
 * Type definitions and utilities for the database layer
 */

/**
 * Transaction type definition
 * @typedef {Object} Transaction
 * @property {number} [id] - Auto-generated ID
 * @property {number} amount - Transaction amount (positive for income, positive for expenses too)
 * @property {string} [description] - Transaction description
 * @property {string} [merchant] - Merchant/vendor name
 * @property {string} [category] - Transaction category (e.g., 'Food', 'Transport', 'Entertainment')
 * @property {'income'|'expense'} type - Transaction type
 * @property {string} date - Transaction date (ISO string)
 * @property {string} [account_id] - Account identifier
 * @property {string} [transaction_id] - Unique transaction identifier
 * @property {Object} [metadata] - Additional metadata
 * @property {string} [created_at] - Auto-generated creation timestamp
 * @property {string} [updated_at] - Auto-generated update timestamp
 */

/**
 * Merchant override type definition
 * @typedef {Object} MerchantOverride
 * @property {number} [id] - Auto-generated ID
 * @property {string} merchant - Merchant name
 * @property {string} category - Category to override with
 * @property {string} [created_at] - Auto-generated creation timestamp
 * @property {string} [updated_at] - Auto-generated update timestamp
 */

/**
 * Common transaction categories
 */
export const TRANSACTION_CATEGORIES = {
  // Expense categories
  FOOD_DINING: 'Food & Dining',
  GROCERIES: 'Groceries',
  TRANSPORTATION: 'Transportation',
  ENTERTAINMENT: 'Entertainment',
  SHOPPING: 'Shopping',
  UTILITIES: 'Utilities',
  HEALTHCARE: 'Healthcare',
  EDUCATION: 'Education',
  TRAVEL: 'Travel',
  SUBSCRIPTIONS: 'Subscriptions',
  INSURANCE: 'Insurance',
  RENT_MORTGAGE: 'Rent/Mortgage',
  TAXES: 'Taxes',
  MISCELLANEOUS: 'Miscellaneous',

  // Income categories
  SALARY: 'Salary',
  FREELANCE: 'Freelance',
  BUSINESS: 'Business',
  INVESTMENT: 'Investment',
  GIFT: 'Gift',
  REFUND: 'Refund',
  OTHER_INCOME: 'Other Income'
};

/**
 * Transaction types
 */
export const TRANSACTION_TYPES = {
  INCOME: 'income',
  EXPENSE: 'expense'
};

/**
 * Utility functions for transaction handling
 */
export const TransactionUtils = {
  /**
   * Format amount for display
   * @param {number} amount - Amount to format
   * @param {string} type - Transaction type
   * @returns {string} Formatted amount with sign
   */
  formatAmount: (amount, type) => {
    const sign = type === TRANSACTION_TYPES.INCOME ? '+' : '-';
    return `${sign}$${Math.abs(amount).toFixed(2)}`;
  },

  /**
   * Create a new transaction object with defaults
   * @param {Partial<Transaction>} transaction - Transaction data
   * @returns {Transaction} Complete transaction object
   */
  createTransaction: (transaction) => ({
    amount: 0,
    description: '',
    merchant: '',
    category: '',
    type: TRANSACTION_TYPES.EXPENSE,
    date: new Date().toISOString(),
    metadata: null,
    ...transaction
  }),

  /**
   * Validate transaction data
   * @param {Transaction} transaction - Transaction to validate
   * @returns {Object} Validation result with isValid and errors
   */
  validateTransaction: (transaction) => {
    const errors = [];

    if (!transaction.amount || typeof transaction.amount !== 'number') {
      errors.push('Amount is required and must be a number');
    }

    if (transaction.amount <= 0) {
      errors.push('Amount must be greater than 0');
    }

    if (!transaction.type || !Object.values(TRANSACTION_TYPES).includes(transaction.type)) {
      errors.push('Type must be either "income" or "expense"');
    }

    if (!transaction.date) {
      errors.push('Date is required');
    }

    try {
      new Date(transaction.date);
    } catch (e) {
      errors.push('Date must be a valid ISO string');
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }
};