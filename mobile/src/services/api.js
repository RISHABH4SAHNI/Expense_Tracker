import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Smart API configuration that works across different environments
const getApiHost = () => {
  // FORCE IP ADDRESS FOR PHYSICAL DEVICE TESTING
  // Change this back to localhost when testing in simulator
  // For physical devices, use your computer's IP address
  return '192.168.1.246';
};

const API_HOST = getApiHost();
const API_PORT = '8000';
const BASE_URL = `http://${API_HOST}:${API_PORT}`;

// API configuration
const API_TIMEOUT = 10000; // 10 seconds timeout
const REQUEST_TIMEOUT = 15000; // 15 seconds for QA requests

console.log(`🔗 API Base URL: ${BASE_URL}`);

// Auth token storage keys
const AUTH_TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_ID_KEY = 'user_id';

// Auth token management
const AuthManager = {
  // Store auth token securely
  async setAuthToken(token) {
    try {
      await SecureStore.setItemAsync(AUTH_TOKEN_KEY, token);
    } catch (error) {
      console.error('Error storing auth token:', error);
      throw error;
    }
  },

  // Get auth token
  async getAuthToken() {
    try {
      return await SecureStore.getItemAsync(AUTH_TOKEN_KEY);
    } catch (error) {
      console.error('Error retrieving auth token:', error);
      return null;
    }
  },

  // Store refresh token securely
  async setRefreshToken(token) {
    try {
      await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
    } catch (error) {
      console.error('Error storing refresh token:', error);
      throw error;
    }
  },

  // Get refresh token
  async getRefreshToken() {
    try {
      return await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
    } catch (error) {
      console.error('Error retrieving refresh token:', error);
      return null;
    }
  },

  // Store user ID
  async setUserId(userId) {
    try {
      await SecureStore.setItemAsync(USER_ID_KEY, userId);
    } catch (error) {
      console.error('Error storing user ID:', error);
      throw error;
    }
  },

  // Get user ID
  async getUserId() {
    try {
      return await SecureStore.getItemAsync(USER_ID_KEY);
    } catch (error) {
      console.error('Error retrieving user ID:', error);
      return null;
    }
  },

  // Clear all auth data
  async clearAuthData() {
    try {
      await SecureStore.deleteItemAsync(AUTH_TOKEN_KEY);
      await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
      await SecureStore.deleteItemAsync(USER_ID_KEY);
    } catch (error) {
      console.error('Error clearing auth data:', error);
      throw error;
    }
  },

  // Check if user is authenticated
  async isAuthenticated() {
    const token = await this.getAuthToken();
    return !!token;
  }
};

// Helper function to get auth headers
const getAuthHeaders = async () => {
  const token = await AuthManager.getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
};

// Helper function to create fetch with timeout
const fetchWithTimeout = async (url, options = {}, timeoutMs = API_TIMEOUT) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error(`Request timeout after ${timeoutMs}ms. Please check your network connection.`);
    }
    throw error;
  }
};

// Enhanced network connectivity test function with detailed logging
const testConnection = async () => {
  console.log(`🔍 Testing connection to: ${BASE_URL}/docs`);
  try {
    // Test basic reachability first
    const basicTest = await fetch(`${BASE_URL}/docs`, { 
      method: 'GET',
      cache: 'no-cache',
      headers: {
        'Cache-Control': 'no-cache'
      }
    });

    console.log(`📡 Basic fetch result: ${basicTest.status} ${basicTest.statusText}`);

    if (basicTest.ok) {
      console.log(`✅ Connection test SUCCESS: Server is reachable at ${BASE_URL}`);
      return true;
    } else {
      console.log(`❌ Connection test FAILED: HTTP ${basicTest.status}`);
      return false;
    }
  } catch (error) {
    console.error('🔴 Connection test failed:', error.message);
    console.error('🔴 Error details:', error);

    // Check if it's a network timeout vs other error
    if (error.message.includes('timeout') || error.message.includes('Network request failed')) {
      console.error('🚨 This looks like a network/firewall issue. Check:');
      console.error('   1. Is your phone on the same WiFi network?');
      console.error('   2. Is the server running and accessible?');
      console.error('   3. Are there any firewall restrictions?');
    }

    return false;
  }
};

// Advanced network diagnostic function
const diagnosticNetworkTest = async () => {
  console.log('🔍 Starting network diagnostics...');
  console.log(`📍 Target server: ${BASE_URL}`);
  console.log(`📱 Platform: ${Platform.OS}`);
  console.log(`🔧 Development mode: ${__DEV__}`);

  const results = [];

  // Test 1: Basic docs endpoint
  try {
    const docsResponse = await fetch(`${BASE_URL}/docs`, { 
      method: 'GET',
      timeout: 5000
    });
    results.push({
      test: 'Docs Endpoint',
      success: docsResponse.ok,
      status: docsResponse.status,
      details: `HTTP ${docsResponse.status}`
    });
  } catch (error) {
    results.push({
      test: 'Docs Endpoint',
      success: false,
      status: 'ERROR',
      details: error.message
    });
  }

  // Test 2: QA endpoint with simple request
  try {
    const qaResponse = await fetch(`${BASE_URL}/qa/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'test', context_days: 30 }),
      timeout: 10000
    });
    results.push({
      test: 'QA Endpoint',
      success: qaResponse.ok,
      status: qaResponse.status,
      details: `HTTP ${qaResponse.status}`
    });
  } catch (error) {
    results.push({
      test: 'QA Endpoint',
      success: false,
      status: 'ERROR',
      details: error.message
    });
  }

  console.log('📊 Network Diagnostic Results:');
  results.forEach(result => {
    const icon = result.success ? '✅' : '❌';
    console.log(`${icon} ${result.test}: ${result.details}`);
  });

  return results;
};

// Helper function to get network status information
const getNetworkInfo = () => {
  return {
    baseUrl: BASE_URL,
    platform: Platform.OS,
    isDev: __DEV__,
    timestamp: new Date().toISOString()
  };
};

// Helper function to handle API errors
const handleApiError = (error, operation) => {
  console.error(`Error ${operation}:`, error);

  if (error.status === 401) {
    // Token expired or invalid - could trigger logout/refresh logic here
    throw new Error('Authentication required. Please log in again.');
  } else if (error.status === 403) {
    throw new Error('Access denied. Insufficient permissions.');
  } else if (error.status === 404) {
    throw new Error('Resource not found.');
  } else if (error.status >= 500) {
    throw new Error('Server error. Please try again later.');
  } else {
    throw new Error(error.message || `Failed to ${operation}`);
  }
};

// Sync transactions with the server - Enhanced version
const syncTransactions = async (localTransactions) => {
  // Handle backward compatibility - if no parameter is provided, return a helpful error
  if (localTransactions === undefined) {
    throw new Error('syncTransactions now requires localTransactions parameter. Please provide an array of transactions to sync.');
  }

  // Validate input
  if (!Array.isArray(localTransactions)) {
    throw new Error('localTransactions must be an array');
  }

  if (localTransactions.length === 0) {
    throw new Error('localTransactions array is empty. No transactions to sync.');
  }

  // Validate transaction structure
  const validTransactions = localTransactions.filter(tx => 
    tx && typeof tx === 'object' && tx.id && tx.amount !== undefined
  );

  try {
    const headers = await getAuthHeaders();

    const response = await fetchWithTimeout(`${BASE_URL}/transactions/sync`, {
      method: 'POST',
      headers,
      body: JSON.stringify(validTransactions),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    return data;
  } catch (error) {
    handleApiError(error, 'syncing transactions');
  }
};

// Fetch transactions from server with optional filters
const fetchTransactionsFromServer = async (options = {}) => {
  const {
    accountId,
    category,
    transactionType,
    limit = 50,
    offset = 0
  } = options;

  try {
    const headers = await getAuthHeaders();

    // Build query parameters
    const queryParams = new URLSearchParams();
    if (accountId) queryParams.append('account_id', accountId);
    if (category) queryParams.append('category', category);
    if (transactionType) queryParams.append('transaction_type', transactionType);
    queryParams.append('limit', limit.toString());
    queryParams.append('offset', offset.toString());

    const url = `${BASE_URL}/transactions?${queryParams.toString()}`;

    const response = await fetchWithTimeout(url, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    return data;
  } catch (error) {
    handleApiError(error, 'fetching transactions');
  }
};

// Ask a question to the QA endpoint
const askQuestion = async (question, contextDays = 30) => {
  console.log(`🤔 Asking question: "${question}" (context_days: ${contextDays})`);
  console.log(`🔗 Using API endpoint: ${BASE_URL}/qa/`);

  if (!question || typeof question !== 'string' || question.trim().length === 0) {
    throw new Error('Question must be a non-empty string');
  }

  try {
    const headers = await getAuthHeaders();
    console.log('📡 Making request with headers:', headers);

    const requestBody = {
      question: question.trim(),
      context_days: contextDays
    };

    console.log('📤 Request body:', requestBody);

    const response = await fetchWithTimeout(`${BASE_URL}/qa/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody),
    }, REQUEST_TIMEOUT); // Use longer timeout for QA requests

    console.log(`📥 Response status: ${response.status}`);

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      console.error('❌ API Error:', errorData);
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    console.log('✅ QA Response received:', data);

    return {
      answer: data.answer,
      confidence: data.confidence,
      sources: data.sources || [],
      analysis_method: data.analysis_method,
      context_summary: data.context_summary
    };
  } catch (error) {
    console.error('💥 Ask question failed:', error);
    if (error.message.includes('Network request failed') || error.message.includes('timeout')) {
      throw new Error(`Cannot connect to server at ${BASE_URL}. Make sure the server is running and accessible.`);
    }
    handleApiError(error, 'asking question');
  }
};

// Export API functions and AuthManager
export { 
  syncTransactions, 
  fetchTransactionsFromServer, 
  askQuestion, 
  AuthManager,
  testConnection,
  diagnosticNetworkTest,
  getNetworkInfo
};
