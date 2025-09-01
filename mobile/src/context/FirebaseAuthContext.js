/**
 * Firebase Authentication Context
 * 
 * Provides authentication state and methods throughout the app
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  signupUser,
  loginUser,
  logoutUser,
  resetPassword,
  getCurrentUser,
  onAuthStateChange
} from '../services/firebase/authService';

const FirebaseAuthContext = createContext();

export const useFirebaseAuth = () => {
  const context = useContext(FirebaseAuthContext);
  if (!context) {
    throw new Error('useFirebaseAuth must be used within a FirebaseAuthProvider');
  }
  return context;
};

export const FirebaseAuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initializing, setInitializing] = useState(true);

  // Monitor authentication state
  useEffect(() => {
    console.log('🔄 [AuthContext] Setting up auth state listener...');

    const unsubscribe = onAuthStateChange((user) => {
      console.log('🔄 [AuthContext] Auth state changed:', user ? 'authenticated' : 'not authenticated');
      setUser(user);
      if (initializing) {
        setInitializing(false);
      }
      setLoading(false);
    });

    // Cleanup subscription on unmount
    return unsubscribe;
  }, [initializing]);

  // Sign up function
  const signup = async (email, password, displayName) => {
    setLoading(true);
    try {
      const result = await signupUser(email, password, displayName);
      return result;
    } finally {
      setLoading(false);
    }
  };

  // Login function
  const login = async (email, password) => {
    setLoading(true);
    try {
      const result = await loginUser(email, password);
      return result;
    } finally {
      setLoading(false);
    }
  };

  // Logout function
  const logout = async () => {
    setLoading(true);
    try {
      await logoutUser();
    } finally {
      setLoading(false);
    }
  };

  const value = {
    user,
    loading,
    initializing,
    signup,
    login,
    logout,
    resetPassword,
    getCurrentUser,
    // Auth state helpers
    isAuthenticated: !!user,
    userEmail: user?.email,
    userDisplayName: user?.displayName,
    userId: user?.uid
  };

  return <FirebaseAuthContext.Provider value={value}>{children}</FirebaseAuthContext.Provider>;
};