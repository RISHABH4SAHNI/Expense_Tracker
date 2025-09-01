/**
 * Firebase Configuration
 * 
 * Initializes Firebase app with Auth and Firestore
 * Uses environment variables for security
 */

import { initializeApp } from 'firebase/app';
import { getAuth, initializeAuth, getReactNativePersistence } from 'firebase/auth';
import { getFirestore, connectFirestoreEmulator } from 'firebase/firestore';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

// Firebase configuration from environment variables
const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.EXPO_PUBLIC_FIREBASE_MEASUREMENT_ID
};

// Validate configuration
const validateConfig = () => {
  const requiredKeys = ['apiKey', 'authDomain', 'projectId', 'storageBucket', 'messagingSenderId', 'appId'];
  const missingKeys = requiredKeys.filter(key => !firebaseConfig[key] || firebaseConfig[key].includes('placeholder'));

  // Check if we're using placeholder values
  const hasPlaceholders = requiredKeys.some(key => 
    firebaseConfig[key] && firebaseConfig[key].includes('placeholder')
  );

  if (missingKeys.length > 0) {
    console.error('❌ Missing Firebase configuration keys:', missingKeys);
    console.error('Please check your .env file and ensure all required Firebase environment variables are set.');
    console.warn('⚠️  Firebase services will be disabled until proper configuration is provided');
    return false;
  }

  if (hasPlaceholders) {
    console.warn('⚠️  Using placeholder Firebase configuration. Firebase services will be disabled.');
    console.warn('Please update your .env file with actual Firebase project configuration.');
    return false;
  }

  console.log('✅ Firebase configuration validated');
  return true;
};

// Check if Firebase should be initialized
const shouldInitializeFirebase = validateConfig();
let app, auth, db;

// Initialize Firebase only if configuration is valid
if (shouldInitializeFirebase) {
  console.log('🔄 Initializing Firebase...');
  app = initializeApp(firebaseConfig);

  // Initialize Auth with persistence
  if (Platform.OS === 'web') {
    auth = getAuth(app);
  } else {
    auth = initializeAuth(app, {
      persistence: getReactNativePersistence(AsyncStorage)
    });
  }

  // Initialize Firestore
  db = getFirestore(app);

  // Development: Connect to Firestore emulator if running locally
  const __DEV__ = process.env.NODE_ENV === 'development';
  if (__DEV__ && !db._delegate._databaseId.projectId.includes('demo-')) {
    console.log('🔧 Development mode: Consider using Firestore emulator');
    // Uncomment to use emulator:
    // connectFirestoreEmulator(db, 'localhost', 8080);
  }

  console.log('🔥 Firebase initialized successfully');
} else {
  console.log('🔥 Firebase initialization skipped - using local storage only');
  // Set to null so other parts of the app can check
  app = null;
  auth = null;
  db = null;
}

export { app, auth, db, shouldInitializeFirebase };