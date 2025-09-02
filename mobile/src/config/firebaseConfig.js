/**
 * Firebase Configuration - Compat API Approach
 * Using Firebase compat API for better Expo compatibility
 */

import firebase from 'firebase/compat/app';
import 'firebase/compat/auth';
import 'firebase/compat/firestore';

console.log('🔥 Loading Firebase Config (Compat API)...');

// Firebase configuration
const firebaseConfig = {
  apiKey: 'AIzaSyBd4yYwTCpvc_3DCqKhcs6wppq9cSFM6NY',
  authDomain: 'expense-tracker-45860.firebaseapp.com',
  projectId: 'expense-tracker-45860',
  storageBucket: 'expense-tracker-45860.firebasestorage.app',
  messagingSenderId: '459767973678',
  appId: '1:459767973678:web:0c172117e0a8e0c6a29cbf',
  measurementId: 'G-VVXQCLLZMC'
};

// Initialize Firebase with compat API
let app, auth, db;
let initializationError = null;

try {
  console.log('🔄 Initializing Firebase with compat API...');

  // Check if Firebase is already initialized
  if (!firebase.apps.length) {
    app = firebase.initializeApp(firebaseConfig);
    console.log('✅ Firebase app initialized');
  } else {
    app = firebase.app();
    console.log('✅ Firebase app already initialized');
  }

  console.log('🔄 Getting Firebase Auth...');
  auth = firebase.auth();
  console.log('✅ Firebase Auth ready');

  console.log('🔄 Getting Firestore...');
  db = firebase.firestore();
  console.log('✅ Firestore ready');

  console.log('🎉 Firebase setup complete with compat API!');

  // Test auth availability
  console.log('🔍 Auth instance type:', typeof auth);
  console.log('🔍 Auth methods available:', !!auth.signInWithEmailAndPassword);

  // Add Firebase v9 compatible methods for custom token support
  auth.signInWithCustomToken = async (customToken) => {
    try {
      console.log('🔄 Signing in with custom token (compat)...');
      const result = await auth.signInWithCustomToken(customToken);
      console.log('✅ Custom token sign-in successful');
      return result;
    } catch (error) {
      console.error('❌ Custom token sign-in failed:', error);
      throw error;
    }
  };

} catch (error) {
  console.error('❌ Firebase initialization failed:', error);
  console.error('Error details:', error.message);
  console.error('Error code:', error.code);

  // Log more detailed error info for debugging
  if (error.stack) {
    console.error('Stack trace:', error.stack);
  }

  initializationError = error;
  app = null;
  auth = null;
  db = null;
}

// Export Firebase instances and utilities
export { app, auth, db, initializationError };
