/**
 * Firebase Helper Functions
 * 
 * Utility functions for common Firebase operations
 */

import { signupUser, loginUser, addExpense, getExpenses } from '../services/firebase';

/**
 * Helper function to handle Firebase errors
 * @param {Error} error - Firebase error
 * @returns {string} User-friendly error message
 */
export const handleFirebaseError = (error) => {
  console.error('Firebase Error:', error);

  // Common Firebase error messages
  const errorMessages = {
    'auth/network-request-failed': 'Network error. Please check your internet connection.',
    'auth/too-many-requests': 'Too many attempts. Please try again later.',
    'firestore/unavailable': 'Database temporarily unavailable. Please try again.',
    'firestore/permission-denied': 'You do not have permission to perform this action.',
  };

  return errorMessages[error.code] || error.message || 'An unexpected error occurred';
};

/**
 * Quick signup helper with error handling
 * @param {string} email 
 * @param {string} password 
 * @param {string} displayName 
 * @returns {Promise<Object>}
 */
export const quickSignup = async (email, password, displayName) => {
  try {
    return await signupUser(email, password, displayName);
  } catch (error) {
    throw new Error(handleFirebaseError(error));
  }
};

/**
 * Quick login helper with error handling
 * @param {string} email 
 * @param {string} password 
 * @returns {Promise<Object>}
 */
export const quickLogin = async (email, password) => {
  try {
    return await loginUser(email, password);
  } catch (error) {
    throw new Error(handleFirebaseError(error));
  }
};

/**
 * Quick add expense helper with error handling
 * @param {Object} expenseData 
 * @returns {Promise<string>}
 */
export const quickAddExpense = async (expenseData) => {
  try {
    return await addExpense(expenseData);
  } catch (error) {
    throw new Error(handleFirebaseError(error));
  }
};

/**
 * Quick get expenses helper with error handling
 * @param {Object} filters 
 * @returns {Promise<Array>}
 */
export const quickGetExpenses = async (filters = {}) => {
  try {
    return await getExpenses(filters);
  } catch (error) {
    throw new Error(handleFirebaseError(error));
  }
};

export default {
  handleFirebaseError,
  quickSignup,
  quickLogin,
  quickAddExpense,
  quickGetExpenses
};