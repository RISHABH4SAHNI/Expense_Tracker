import React, { createContext, useReducer, useEffect } from 'react';
import authService from '../services/auth';
// Import Firebase v9 modular API for authentication
import { auth, initializationError } from '../config/firebaseConfig';
import { 
  signInWithEmailAndPassword, 
  signInWithCustomToken,
  signOut,
  onAuthStateChanged,
  createUserWithEmailAndPassword
} from 'firebase/auth';
import AsyncStorage from '@react-native-async-storage/async-storage';

console.log('📱 AuthContext: Loaded with Firebase compat auth');

// Initial state
const initialState = {
  isLoading: true,
  isSignedIn: false, // Always start as not signed in - require explicit authentication
  user: null,
  error: null,
};

// Action types
const AuthActionTypes = {
  RESTORE_TOKEN: 'RESTORE_TOKEN',
  SIGN_IN: 'SIGN_IN',
  SIGN_OUT: 'SIGN_OUT',
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  UPDATE_USER: 'UPDATE_USER',
};

// Firebase Auth helper functions
const firebaseSignInWithEmail = async (email, password) => {
  try {
    if (!auth) {
      throw new Error('Firebase Auth not initialized');
    }

    console.log('🔄 Signing in with email and password...');
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    console.log('✅ Firebase email sign-in successful');
    return userCredential.user;
  } catch (error) {
    console.error('❌ Firebase email sign-in failed:', error);
    throw new Error(`Firebase sign-in failed: ${error.message}`);
  }
};

const firebaseSignInWithCustomToken = async (customToken) => {
  try {
    if (!auth) {
      throw new Error('Firebase Auth not initialized');
    }

    console.log('🔄 Signing in with custom token...');
    const userCredential = await signInWithCustomToken(auth, customToken);
    console.log('✅ Firebase custom token sign-in successful');

    // Store the custom token for future use
    await AsyncStorage.setItem('firebase_custom_token', customToken);

    return userCredential.user;
  } catch (error) {
    console.error('❌ Firebase custom token sign-in failed:', error);
    throw new Error(`Firebase custom token sign-in failed: ${error.message}`);
  }
};

const firebaseSignOut = async () => {
  try {
    if (!auth) {
      console.warn('⚠️ Firebase Auth not initialized, skipping sign out');
      return;
    }

    console.log('🔄 Signing out from Firebase...');
    await signOut(auth);

    // Clear stored custom token
    await AsyncStorage.removeItem('firebase_custom_token');

    console.log('✅ Firebase sign-out successful');
  } catch (error) {
    console.error('❌ Firebase sign-out failed:', error);
    throw new Error(`Firebase sign-out failed: ${error.message}`);
  }
};

const firebaseCreateUser = async (email, password) => {
  try {
    if (!auth) {
      throw new Error('Firebase Auth not initialized');
    }

    console.log('🔄 Creating Firebase user...');
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    console.log('✅ Firebase user creation successful');
    return userCredential.user;
  } catch (error) {
    console.error('❌ Firebase user creation failed:', error);
    throw new Error(`Firebase user creation failed: ${error.message}`);
  }
};

// Reducer
const authReducer = (prevState, action) => {
  switch (action.type) {
    case AuthActionTypes.RESTORE_TOKEN:
      return {
        ...prevState,
        user: action.user,
        isSignedIn: !!action.user,
        isLoading: false,
      };
    case AuthActionTypes.SIGN_IN:
      return {
        ...prevState,
        isSignedIn: true,
        user: action.user,
        isLoading: false,
        error: null,
      };
    case AuthActionTypes.SIGN_OUT:
      return {
        ...prevState,
        isSignedIn: false,
        user: null,
        isLoading: false,
        error: null,
      };
    case AuthActionTypes.SET_LOADING:
      return {
        ...prevState,
        isLoading: action.isLoading,
      };
    case AuthActionTypes.SET_ERROR:
      return {
        ...prevState,
        error: action.error,
        isLoading: false,
      };
    case AuthActionTypes.UPDATE_USER:
      return {
        ...prevState,
        user: action.user,
      };
    default:
      return prevState;
  }
};

// Create context
export const AuthContext = createContext();

// AuthProvider component
export const AuthProvider = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // Listen to Firebase Auth state changes
  useEffect(() => {
    if (!auth) {
      console.warn('⚠️ Firebase Auth not available, skipping auth state listener');
      return;
    }

    console.log('👂 Setting up Firebase Auth state listener...');
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      console.log('🔄 Firebase Auth state changed:', firebaseUser ? 'signed in' : 'signed out');
      // You can sync Firebase user state with your local auth state here if needed
    });

    return () => {
      unsubscribe();
    };
  }, []);

  // Restore token on app start
  useEffect(() => {
    const bootstrapAsync = async () => {
      try {
        console.log('🔄 [AuthContext] Bootstrapping authentication...');
        const user = await authService.getCurrentUser();
        const isAuthenticated = await authService.isAuthenticated();

        console.log('🔍 [AuthContext] User from storage:', user ? 'found' : 'not found');
        console.log('🔍 [AuthContext] Is authenticated:', isAuthenticated);

        // Force strict authentication - require BOTH user data AND valid token
        if (user && isAuthenticated) {
          console.log('✅ [AuthContext] User authenticated, restoring session');
          dispatch({ type: AuthActionTypes.RESTORE_TOKEN, user });
        } else {
          console.log('❌ [AuthContext] No valid authentication found, requiring login');
          dispatch({ type: AuthActionTypes.RESTORE_TOKEN, user: null });
        }
      } catch (error) {
        console.error('Error restoring auth state:', error);
        dispatch({ type: AuthActionTypes.RESTORE_TOKEN, user: null });
      }
    };

    bootstrapAsync();
  }, []);

  // Monitor Firebase auth state for proper sync (but don't force sign out immediately)
  useEffect(() => {
    if (!auth) return;

    let timeoutId;
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      console.log('🔥 [AuthContext] Firebase auth state:', firebaseUser ? 'signed in' : 'signed out');

      // Give Firebase 30 seconds to sync after login before forcing sign out
      if (!firebaseUser && state.isSignedIn) {
        timeoutId = setTimeout(() => {
          console.log('⚠️ [AuthContext] Firebase sync timeout - allowing offline mode');
          // Don't force sign out - allow offline mode
        }, 30000); // 30 second grace period
      } else if (firebaseUser && timeoutId) {
        clearTimeout(timeoutId);
      }
    });

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
      unsubscribe();
    };
  }, [state.isSignedIn]);

  // Helper function to get stored custom token
  const getStoredCustomToken = async () => {
    try {
      return await AsyncStorage.getItem('firebase_custom_token');
    } catch (error) {
      console.error('❌ Error getting stored custom token:', error);
      return null;
    }
  };

  // Helper function to attempt Firebase auth restoration
  const restoreFirebaseAuth = async (user) => {
    try {
      // Check if we have a stored custom token
      const customToken = await getStoredCustomToken();
      if (customToken) {
        console.log('🔄 Attempting to restore Firebase auth with stored custom token...');
        await firebaseSignInWithCustomToken(customToken);
        return true;
      }
      return false;
    } catch (error) {
      console.warn('⚠️ Failed to restore Firebase auth:', error.message);
      // Clear invalid token
      await AsyncStorage.removeItem('firebase_custom_token');
      return false;
    }
  };

  // Auth context methods
  const authContext = {
    ...state,
    signIn: async (user) => {
      try {
        dispatch({ type: AuthActionTypes.SIGN_IN, user });
        console.log('✅ [AuthContext] User signed in:', user.email);

        // Try to sync with Firebase Auth using fresh firebase_token
        console.log('🔄 Attempting Firebase Auth sync...');

        // Priority 1: Use fresh firebase_token from login response
        if (user.firebase_token) {
          try {
            console.log('🔥 Using fresh Firebase custom token...');
            await firebaseSignInWithCustomToken(user.firebase_token);
            // Store the custom token for future use
            await AsyncStorage.setItem('firebase_custom_token', user.firebase_token);
            console.log('🔥 [AuthContext] Firebase authentication synced with fresh token');
          } catch (firebaseError) {
            console.warn('⚠️ Firebase custom token sync failed:', firebaseError.message);
          }
        } else {
          // Priority 2: Try to restore from stored token
          const restored = await restoreFirebaseAuth(user);
          if (!restored) {
            console.log('⚠️ No Firebase token available - Firebase sync skipped');
            console.log('ℹ️ Transactions will be saved locally only');
            // Don't attempt email/password as it's not enabled
            // Don't throw error here as main auth succeeded
          }
        }

        console.log('✅ Firebase Auth sync completed');
      } catch (error) {
        console.error('Sign in error:', error);
        dispatch({ type: AuthActionTypes.SET_ERROR, error: error.message });
      }
    },
    signInWithCustomToken: async (customToken, userData) => {
      try {
        const firebaseUser = await firebaseSignInWithCustomToken(customToken);
        dispatch({ type: AuthActionTypes.SIGN_IN, user: userData || { email: firebaseUser.email, uid: firebaseUser.uid } });
      } catch (error) {
        console.error('Custom token sign in error:', error);
        dispatch({ type: AuthActionTypes.SET_ERROR, error: error.message });
      }
    },
    signOut: async () => {
      try {
        dispatch({ type: AuthActionTypes.SET_LOADING, isLoading: true });

        console.log('🚪 [AuthContext] Signing out...');

        // Clear Firebase custom token from storage
        try {
          await AsyncStorage.removeItem('firebase_custom_token');
        } catch (error) {
          console.warn('Failed to clear Firebase custom token:', error);
        }

        // Sign out from Firebase Auth first
        try {
          await firebaseSignOut();
        } catch (fbError) {
          console.warn('Firebase signout failed:', fbError);
        }

        // Clear Firebase custom token from storage
        try {
          await AsyncStorage.removeItem('firebase_custom_token');

        } catch (error) {
          console.warn('Failed to clear Firebase custom token:', error);
        }

        await authService.logout();
        dispatch({ type: AuthActionTypes.SIGN_OUT });
      } catch (error) {
        console.error('Sign out error:', error);
        // Still sign out locally even if server logout fails
        dispatch({ type: AuthActionTypes.SIGN_OUT });
      }
    },
    refreshToken: async () => {
      try {
        const result = await authService.refresh();
        if (result.success) {
          const user = await authService.getCurrentUser();
          dispatch({ type: AuthActionTypes.UPDATE_USER, user });
          return true;
        }
        return false;
      } catch (error) {
        console.error('Token refresh error:', error);
        // If refresh fails, sign out
        dispatch({ type: AuthActionTypes.SIGN_OUT });
        return false;
      }
    },
    createFirebaseUser: async (email, password, additionalUserData) => {
      try {
        dispatch({ type: AuthActionTypes.SET_LOADING, isLoading: true });

        const firebaseUser = await firebaseCreateUser(email, password);
        const userData = {
          uid: firebaseUser.uid,
          email: firebaseUser.email,
          ...additionalUserData
        };

        dispatch({ type: AuthActionTypes.SIGN_IN, user: userData });
        return { success: true, user: userData };
      } catch (error) {
        console.error('Create Firebase user error:', error);
        dispatch({ type: AuthActionTypes.SET_ERROR, error: error.message });
        return { success: false, error: error.message };
      }
    },
    updateUser: (user) => {
      dispatch({ type: AuthActionTypes.UPDATE_USER, user });
    },
  };

  return (
    <AuthContext.Provider value={authContext}>
      {children}
    </AuthContext.Provider>
  );
};

// Export Firebase auth helper functions for use in other components
export { firebaseSignInWithEmail, firebaseSignInWithCustomToken, firebaseSignOut, firebaseCreateUser };