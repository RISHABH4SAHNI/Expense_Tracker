import * as SecureStore from 'expo-secure-store';

// API configuration
const getApiHost = () => {
  return '192.168.1.246'; // Use your computer's IP address for physical device testing
};

const API_HOST = getApiHost();
const API_PORT = '8000';
const BASE_URL = `http://${API_HOST}:${API_PORT}`;

// Storage keys
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_DATA_KEY = 'user_data';

class AuthService {
  // Utility function to decode JWT token (without verification)
  _decodeJWT(token) {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
      }).join(''));
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('JWT decode error:', error);
      return null;
    }
  }

  // Log token details for debugging
  _logTokenDebug(token, label) {
    if (token) {
      const payload = this._decodeJWT(token);
      console.log(`[AuthService] ${label}:`); 
      console.log(`  - Token prefix: ${token.substring(0, 30)}...`);
      console.log(`  - Token ID (jti): ${payload?.jti || 'MISSING'}`);
      console.log(`  - User ID (sub): ${payload?.sub || 'MISSING'}`);
      console.log(`  - Expires: ${payload?.exp ? new Date(payload.exp * 1000).toISOString() : 'MISSING'}`);
    }
  }

  // Register new user
  async register(email, password) {
    try {
      const response = await fetch(`${BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || `Registration failed: ${response.status}`);
      }

      const data = await response.json();

      // Store tokens and user data securely
      console.log('[AuthService] Login successful, storing new tokens...');
      this._logTokenDebug(data.access_token, 'NEW ACCESS TOKEN');

      // Clear old tokens first to prevent caching issues
      await this._clearAuthData();
      console.log('[AuthService] Old tokens cleared, storing new ones...');

      await this._storeAuthData(data.access_token, data.refresh_token, data.user);
      console.log('[AuthService] New tokens stored successfully');
      this._logTokenDebug(data.refresh_token, 'NEW REFRESH TOKEN');

      return {
        success: true,
        user: data.user,
        message: 'Registration successful',
      };
    } catch (error) {
      console.error('Registration error:', error);
      throw new Error(error.message || 'Registration failed');
    }
  }

  // Login user
  async login(email, password) {
    try {
      const response = await fetch(`${BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || `Login failed: ${response.status}`);
      }

      const data = await response.json();

      // Store tokens and user data securely
      console.log('[AuthService] Login successful, storing new tokens...');
      this._logTokenDebug(data.access_token, 'NEW ACCESS TOKEN');

      // Clear old tokens first to prevent caching issues
      await this._clearAuthData();
      console.log('[AuthService] Old tokens cleared, storing new ones...');

      await this._storeAuthData(data.access_token, data.refresh_token, data.user);
      console.log('[AuthService] New tokens stored successfully');
      this._logTokenDebug(data.refresh_token, 'NEW REFRESH TOKEN');

      return {
        success: true,
        user: data.user,
        message: 'Login successful',
      };
    } catch (error) {
      console.error('Login error:', error);
      throw new Error(error.message || 'Login failed');
    }
  }

  // Refresh access token
  async refresh() {
    try {
      const refreshToken = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);

      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      const response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          refresh_token: refreshToken,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        // If refresh fails, clear all auth data
        await this._clearAuthData();
        throw new Error(errorData?.detail || 'Token refresh failed');
      }

      const data = await response.json();

      // Store new tokens
      await this._storeAuthData(data.access_token, data.refresh_token, data.user);

      return {
        success: true,
        accessToken: data.access_token,
      };
    } catch (error) {
      console.error('Token refresh error:', error);
      await this._clearAuthData();
      throw error;
    }
  }

  // Logout user
  async logout() {
    try {
      const accessToken = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);

      if (accessToken) {
        // Try to logout from server
        try {
          await fetch(`${BASE_URL}/auth/logout`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${accessToken}`,
            },
          });
        } catch (error) {
          console.warn('Server logout failed:', error);
          // Continue with local logout even if server logout fails
        }
      }

      // Clear local auth data
      await this._clearAuthData();

      return { success: true, message: 'Logged out successfully' };
    } catch (error) {
      console.error('Logout error:', error);
      // Still clear local data even if there's an error
      await this._clearAuthData();
      return { success: true, message: 'Logged out locally' };
    }
  }

  // Get current user data
  async getCurrentUser() {
    try {
      const userData = await SecureStore.getItemAsync(USER_DATA_KEY);
      return userData ? JSON.parse(userData) : null;
    } catch (error) {
      console.error('Error getting current user:', error);
      return null;
    }
  }

  // Check if user is authenticated
  async isAuthenticated() {
    try {
      const accessToken = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
      return !!accessToken;
    } catch (error) {
      console.error('Error checking authentication:', error);
      return false;
    }
  }

  // Force refresh auth headers (clears any potential caching)
  async getAuthHeadersFresh() {
    try {
      // Force a fresh read from SecureStore
      const accessToken = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
      this._logTokenDebug(accessToken, 'FRESH TOKEN FROM STORAGE');

      const headers = { 'Content-Type': 'application/json' };
      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
      }
      return headers;
    } catch (error) {
      console.error('Error getting fresh auth headers:', error);
      return { 'Content-Type': 'application/json' };
    }
  }

  // Get auth headers for API requests
  async getAuthHeaders() {
    try {
      const accessToken = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
      const headers = {
        'Content-Type': 'application/json',
      };

      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
      }

      return headers;
    } catch (error) {
      console.error('Error getting auth headers:', error);
      return {
        'Content-Type': 'application/json',
      };
    }
  }

  // Get access token
  async getAccessToken() {
    try {
      return await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
    } catch (error) {
      console.error('Error getting access token:', error);
      return null;
    }
  }

  // Private method to store auth data
  async _storeAuthData(accessToken, refreshToken, userData) {
    try {
      this._logTokenDebug(accessToken, 'STORING ACCESS TOKEN');
      await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, accessToken);
      await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refreshToken);
      await SecureStore.setItemAsync(USER_DATA_KEY, JSON.stringify(userData));

      // Verify storage by immediately reading back
      const storedToken = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
      this._logTokenDebug(storedToken, 'VERIFIED STORED TOKEN');

      if (storedToken !== accessToken) {
        throw new Error('Token storage verification failed');
      }
    } catch (error) {
      console.error('Error storing auth data:', error);
      throw new Error('Failed to store authentication data');
    }
  }

  // Private method to clear auth data
  async _clearAuthData() {
    try {
      await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
      await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
      await SecureStore.deleteItemAsync(USER_DATA_KEY);
      console.log('[AuthService] Auth data cleared');
    } catch (error) {
      console.error('Error clearing auth data:', error);
    }
  }
}

// Export singleton instance
const authService = new AuthService();
export default authService;