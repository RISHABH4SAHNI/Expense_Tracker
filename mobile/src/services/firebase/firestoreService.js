/**
 * Firestore Database Service
 * 
 * Handles all Firestore operations for expenses/transactions:
 * - Add expense/transaction
 * - Get user expenses
 * - Update expense
 * - Delete expense
 * - Real-time listeners
 */

import {
  collection,
  doc,
  addDoc,
  getDocs,
  getDoc,
  updateDoc,
  deleteDoc,
  query,
  where,
  orderBy,
  limit,
  onSnapshot,
  serverTimestamp,
  writeBatch
} from 'firebase/firestore';
import { db } from '../../config/firebaseConfig';
import { getCurrentUser } from './authService';

// Collection names
const EXPENSES_COLLECTION = 'expenses';
const USERS_COLLECTION = 'users';

/**
 * Ensure user is authenticated
 * @throws {Error} If user is not authenticated
 */
const ensureAuthenticated = () => {
  const user = getCurrentUser();
  if (!user) {
    throw new Error('User must be authenticated to perform this operation');
  }
  return user;
};

/**
 * Add a new expense/transaction to Firestore
 * @param {Object} expenseData - Expense data
 * @returns {Promise<string>} Document ID
 */
export const addExpense = async (expenseData) => {
  try {
    const user = ensureAuthenticated();
    console.log('🔄 [Firestore] Adding expense...');

    // Prepare expense document
    const expense = {
      ...expenseData,
      userId: user.uid,
      userEmail: user.email,
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
      // Ensure required fields have defaults
      type: expenseData.type || 'expense',
      amount: parseFloat(expenseData.amount) || 0,
      category: expenseData.category || 'Other',
      description: expenseData.description || '',
      date: expenseData.date || new Date().toISOString().split('T')[0],
      notes: expenseData.notes || '',
      source: expenseData.source || 'manual' // 'manual' or 'aa'
    };

    // Add to Firestore
    const docRef = await addDoc(collection(db, EXPENSES_COLLECTION), expense);

    console.log('✅ [Firestore] Expense added with ID:', docRef.id);
    return docRef.id;
  } catch (error) {
    console.error('❌ [Firestore] Error adding expense:', error);
    throw new Error('Failed to save expense to cloud storage');
  }
};

/**
 * Get all expenses for the current user
 * @param {Object} filters - Filter options
 * @returns {Promise<Array>} List of expenses
 */
export const getExpenses = async (filters = {}) => {
  try {
    const user = ensureAuthenticated();
    console.log('🔄 [Firestore] Fetching expenses...');

    // Build query
    let q = query(
      collection(db, EXPENSES_COLLECTION),
      where('userId', '==', user.uid),
      orderBy('createdAt', 'desc')
    );

    // Apply filters
    if (filters.type) {
      q = query(q, where('type', '==', filters.type));
    }

    if (filters.category) {
      q = query(q, where('category', '==', filters.category));
    }

    if (filters.limit) {
      q = query(q, limit(filters.limit));
    }

    // Execute query
    const querySnapshot = await getDocs(q);
    const expenses = [];

    querySnapshot.forEach((doc) => {
      expenses.push({
        id: doc.id,
        ...doc.data(),
        // Convert Firestore timestamps to JavaScript dates
        createdAt: doc.data().createdAt?.toDate(),
        updatedAt: doc.data().updatedAt?.toDate()
      });
    });

    console.log(`✅ [Firestore] Retrieved ${expenses.length} expenses`);
    return expenses;
  } catch (error) {
    console.error('❌ [Firestore] Error fetching expenses:', error);
    throw new Error('Failed to fetch expenses from cloud storage');
  }
};

/**
 * Update an existing expense
 * @param {string} expenseId - Expense document ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<boolean>} Success status
 */
export const updateExpense = async (expenseId, updates) => {
  try {
    const user = ensureAuthenticated();
    console.log('🔄 [Firestore] Updating expense:', expenseId);

    const expenseRef = doc(db, EXPENSES_COLLECTION, expenseId);

    // Verify expense belongs to current user
    const expenseDoc = await getDoc(expenseRef);
    if (!expenseDoc.exists()) {
      throw new Error('Expense not found');
    }

    if (expenseDoc.data().userId !== user.uid) {
      throw new Error('You can only update your own expenses');
    }

    // Update document
    await updateDoc(expenseRef, {
      ...updates,
      updatedAt: serverTimestamp()
    });

    console.log('✅ [Firestore] Expense updated successfully');
    return true;
  } catch (error) {
    console.error('❌ [Firestore] Error updating expense:', error);
    throw new Error('Failed to update expense');
  }
};

/**
 * Delete an expense
 * @param {string} expenseId - Expense document ID
 * @returns {Promise<boolean>} Success status
 */
export const deleteExpense = async (expenseId) => {
  try {
    const user = ensureAuthenticated();
    console.log('🔄 [Firestore] Deleting expense:', expenseId);

    const expenseRef = doc(db, EXPENSES_COLLECTION, expenseId);

    // Verify expense belongs to current user
    const expenseDoc = await getDoc(expenseRef);
    if (!expenseDoc.exists()) {
      throw new Error('Expense not found');
    }

    if (expenseDoc.data().userId !== user.uid) {
      throw new Error('You can only delete your own expenses');
    }

    // Delete document
    await deleteDoc(expenseRef);

    console.log('✅ [Firestore] Expense deleted successfully');
    return true;
  } catch (error) {
    console.error('❌ [Firestore] Error deleting expense:', error);
    throw new Error('Failed to delete expense');
  }
};

/**
 * Listen to real-time expense updates
 * @param {Function} callback - Callback function for updates
 * @param {Object} filters - Filter options
 * @returns {Function} Unsubscribe function
 */
export const listenToExpenses = (callback, filters = {}) => {
  try {
    const user = ensureAuthenticated();
    console.log('🔄 [Firestore] Setting up real-time listener...');

    // Build query
    let q = query(
      collection(db, EXPENSES_COLLECTION),
      where('userId', '==', user.uid),
      orderBy('createdAt', 'desc')
    );

    // Apply filters
    if (filters.type) {
      q = query(q, where('type', '==', filters.type));
    }

    if (filters.limit) {
      q = query(q, limit(filters.limit));
    }

    // Set up listener
    const unsubscribe = onSnapshot(q, (querySnapshot) => {
      const expenses = [];
      querySnapshot.forEach((doc) => {
        expenses.push({
          id: doc.id,
          ...doc.data(),
          createdAt: doc.data().createdAt?.toDate(),
          updatedAt: doc.data().updatedAt?.toDate()
        });
      });

      console.log(`🔄 [Firestore] Real-time update: ${expenses.length} expenses`);
      callback(expenses);
    }, (error) => {
      console.error('❌ [Firestore] Real-time listener error:', error);
      callback(null, error);
    });

    console.log('✅ [Firestore] Real-time listener active');
    return unsubscribe;
  } catch (error) {
    console.error('❌ [Firestore] Error setting up listener:', error);
    throw new Error('Failed to set up real-time updates');
  }
};

export default {
  addExpense,
  getExpenses,
  updateExpense,
  deleteExpense,
  listenToExpenses
};