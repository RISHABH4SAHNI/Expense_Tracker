/**
 * Firebase Services Entry Point
 * 
 * Exports all Firebase-related services
 */

// Auth service
export {
  signupUser,
  loginUser,
  logoutUser,
  resetPassword,
  getCurrentUser,
  onAuthStateChange
} from './authService';

// Firestore service
export { addExpense, getExpenses, updateExpense, deleteExpense, listenToExpenses } from './firestoreService';