import React, { createContext, useReducer, useEffect } from 'react';
import authService from '../services/auth';

// Initial state
const initialState = {
  isLoading: true,
  isSignedIn: false,
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

  // Restore token on app start
  useEffect(() => {
    const bootstrapAsync = async () => {
      try {
        const user = await authService.getCurrentUser();
        const isAuthenticated = await authService.isAuthenticated();

        if (user && isAuthenticated) {
          dispatch({ type: AuthActionTypes.RESTORE_TOKEN, user });
        } else {
          dispatch({ type: AuthActionTypes.RESTORE_TOKEN, user: null });
        }
      } catch (error) {
        console.error('Error restoring auth state:', error);
        dispatch({ type: AuthActionTypes.RESTORE_TOKEN, user: null });
      }
    };

    bootstrapAsync();
  }, []);

  // Auth context methods
  const authContext = {
    ...state,
    signIn: async (user) => {
      try {
        dispatch({ type: AuthActionTypes.SIGN_IN, user });
      } catch (error) {
        console.error('Sign in error:', error);
        dispatch({ type: AuthActionTypes.SET_ERROR, error: error.message });
      }
    },
    signOut: async () => {
      try {
        dispatch({ type: AuthActionTypes.SET_LOADING, isLoading: true });
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