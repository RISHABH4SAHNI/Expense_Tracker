/**
 * Firebase Authentication Service
 * 
 * Handles user authentication operations:
 * - Sign up with email/password
 * - Login with email/password
 * - Logout
 * - Password reset
 * - Auth state monitoring
 */

import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  sendPasswordResetEmail,
  updateProfile,
  onAuthStateChanged
} from 'firebase/auth';
import { auth } from '../../config/firebaseConfig';

/**
 * Sign up a new user with email and password
 * @param {string} email - User email
 * @param {string} password - User password
 * @param {string} displayName - User display name (optional)
 * @returns {Promise<Object>} User data
 */
export const signupUser = async (email, password, displayName = null) => {
  try {
    console.log('🔄 [Auth] Creating user account...');

    // Create user account
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;

    // Update profile with display name if provided
    if (displayName) {
      await updateProfile(user, { displayName });
      console.log('✅ [Auth] Profile updated with display name');
    }

    console.log('✅ [Auth] User account created successfully');

    return {
      success: true,
      user: {
        uid: user.uid,
        email: user.email,
        displayName: user.displayName || displayName,
        emailVerified: user.emailVerified,
        createdAt: user.metadata.creationTime
      }
    };
  } catch (error) {
    console.error('❌ [Auth] Signup failed:', error);

    // Handle specific Firebase auth errors
    let errorMessage = 'Failed to create account';
    switch (error.code) {
      case 'auth/email-already-in-use':
        errorMessage = 'Email is already registered';
        break;
      case 'auth/weak-password':
        errorMessage = 'Password is too weak';
        break;
      case 'auth/invalid-email':
        errorMessage = 'Invalid email address';
        break;
      default:
        errorMessage = error.message;
    }

    throw new Error(errorMessage);
  }
};

/**
 * Login user with email and password
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<Object>} User data
 */
export const loginUser = async (email, password) => {
  try {
    console.log('🔄 [Auth] Signing in user...');

    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;

    console.log('✅ [Auth] User signed in successfully');

    return {
      success: true,
      user: {
        uid: user.uid,
        email: user.email,
        displayName: user.displayName,
        emailVerified: user.emailVerified,
        lastSignInTime: user.metadata.lastSignInTime
      }
    };
  } catch (error) {
    console.error('❌ [Auth] Login failed:', error);

    // Handle specific Firebase auth errors
    let errorMessage = 'Failed to sign in';
    switch (error.code) {
      case 'auth/user-not-found':
        errorMessage = 'No account found with this email';
        break;
      case 'auth/wrong-password':
        errorMessage = 'Incorrect password';
        break;
      case 'auth/invalid-email':
        errorMessage = 'Invalid email address';
        break;
      case 'auth/too-many-requests':
        errorMessage = 'Too many failed attempts. Please try again later.';
        break;
      default:
        errorMessage = error.message;
    }

    throw new Error(errorMessage);
  }
};

/**
 * Logout current user
 * @returns {Promise<boolean>} Success status
 */
export const logoutUser = async () => {
  try {
    console.log('🔄 [Auth] Signing out user...');
    await signOut(auth);
    console.log('✅ [Auth] User signed out successfully');
    return true;
  } catch (error) {
    console.error('❌ [Auth] Logout failed:', error);
    throw new Error('Failed to sign out');
  }
};

/**
 * Send password reset email
 * @param {string} email - User email
 * @returns {Promise<boolean>} Success status
 */
export const resetPassword = async (email) => {
  try {
    console.log('🔄 [Auth] Sending password reset email...');
    await sendPasswordResetEmail(auth, email);
    console.log('✅ [Auth] Password reset email sent');
    return true;
  } catch (error) {
    console.error('❌ [Auth] Password reset failed:', error);

    let errorMessage = 'Failed to send reset email';
    switch (error.code) {
      case 'auth/user-not-found':
        errorMessage = 'No account found with this email';
        break;
      case 'auth/invalid-email':
        errorMessage = 'Invalid email address';
        break;
      default:
        errorMessage = error.message;
    }

    throw new Error(errorMessage);
  }
};

/**
 * Get current user
 * @returns {Object|null} Current user or null
 */
export const getCurrentUser = () => {
  return auth.currentUser;
};

/**
 * Monitor authentication state changes
 * @param {Function} callback - Callback function to handle auth state changes
 * @returns {Function} Unsubscribe function
 */
export const onAuthStateChange = (callback) => {
  return onAuthStateChanged(auth, callback);
};

export default {
  signupUser,
  loginUser,
  logoutUser,
  resetPassword,
  getCurrentUser,
  onAuthStateChange
};