import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import authService from './auth';

// Smart API configuration that works across different environments
const getApiHost = () => {
  // FORCE IP ADDRESS FOR PHYSICAL DEVICE TESTING
  // Change this back to localhost when testing in simulator
  // For physical devices, use your computer's IP address
  return '192.168.1.251';
  return '192.168.1.251';
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

// Helper function to get auth headers - Updated to use authService
const getAuthHeaders = async () => {
  try {
    return await authService.getAuthHeaders();
  } catch (error) {
    console.error('Error getting auth headers:', error);
    return {
      'Content-Type': 'application/json',
    };
  }
};

// Global reference to auth context (will be set from App.js)
let authContextRef = null;

export const setAuthContext = (authContext) => {
  authContextRef = authContext;
};

// Helper function to handle 401 errors
const handle401Error = async () => {
  console.log('🔄 Handling 401 error - attempting token refresh');

  if (authContextRef && authContextRef.refreshToken) {
    const refreshSuccess = await authContextRef.refreshToken();
    if (!refreshSuccess) {
      console.log('🚪 Token refresh failed - signing out');
      await authContextRef.signOut();
    }
    return refreshSuccess;
  }

  return false;
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

// Enhanced fetch with auth and retry logic
const fetchWithAuth = async (url, options = {}, timeoutMs = API_TIMEOUT) => {
  try {
    // Get auth headers
    const headers = await getAuthHeaders();

    // Make request
    const response = await fetchWithTimeout(url, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    }, timeoutMs);

    // Handle 401 errors
    if (response.status === 401) {
      console.log('🔑 Received 401 - attempting token refresh');
      const refreshSuccess = await handle401Error();

      if (refreshSuccess) {
        // Retry the request with new token
        const newHeaders = await getAuthHeaders();
        return await fetchWithTimeout(url, {
          ...options,
          headers: {
            ...newHeaders,
            ...options.headers,
          },
        }, timeoutMs);
      }
    }

    return response;
  } catch (error) {
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
    const response = await fetchWithAuth(`${BASE_URL}/transactions/sync`, {
      method: 'POST',
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
    // Build query parameters
    const queryParams = new URLSearchParams();
    if (accountId) queryParams.append('account_id', accountId);
    if (category) queryParams.append('category', category);
    if (transactionType) queryParams.append('transaction_type', transactionType);
    queryParams.append('limit', limit.toString());
    queryParams.append('offset', offset.toString());

    const url = `${BASE_URL}/transactions?${queryParams.toString()}`;

    const response = await fetchWithAuth(url, {
      method: 'GET',
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
    const requestBody = {
      question: question.trim(),
      context_days: contextDays
    };

    console.log('📡 Making authenticated request');
    console.log('📤 Request body:', requestBody);

    const response = await fetchWithAuth(`${BASE_URL}/qa/`, {
      method: 'POST',
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

// Advanced Insights Engine Functions
const askAdvancedInsights = async (question, options = {}) => {
  console.log(`🧠 Asking advanced insights: "${question}"`);
  console.log(`🔗 Using API endpoint: ${BASE_URL}/api/insights`);

  if (!question || typeof question !== 'string' || question.trim().length === 0) {
    throw new Error('Question must be a non-empty string');
  }

  // Get current user from authService instead of AuthManager
  const currentUser = await authService.getCurrentUser();
  if (!currentUser || !currentUser.id) {
    throw new Error('User not authenticated');
  }

  if (!currentUser.id) {
    throw new Error('User not authenticated');
  }

  try {
    const requestBody = {
      question: question.trim(),
      user_id: currentUser.id,
      time_range_days: options.timeRangeDays || 30,
      include_supporting_data: options.includeSupportingData !== false,
      max_transactions: options.maxTransactions || 10
    };

    console.log('📤 Request body:', requestBody);

    const response = await fetchWithAuth(`${BASE_URL}/api/insights`, {
      method: 'POST',
      body: JSON.stringify(requestBody),
    }, REQUEST_TIMEOUT);

    console.log(`📥 Response status: ${response.status}`);

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      console.error('❌ API Error:', errorData);
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    console.log('✅ Advanced Insights Response received:', data);

    return {
      answer: data.answer,
      confidence: data.confidence,
      supporting_transactions: data.supporting_transactions || [],
      analysis_metadata: data.analysis_metadata || {},
      sql_query: data.sql_query,
      execution_time_ms: data.execution_time_ms
    };
  } catch (error) {
    console.error('💥 Advanced insights failed:', error);
    if (error.message.includes('Network request failed') || error.message.includes('timeout')) {
      throw new Error(`Cannot connect to insights engine at ${BASE_URL}. Make sure the server is running and accessible.`);
    }
    handleApiError(error, 'getting advanced insights');
  }
};

// Anomaly Detection Functions
const detectAnomalies = async (options = {}) => {
  console.log('🚨 Detecting spending anomalies');

  // Get current user from authService instead of AuthManager
  const currentUser = await authService.getCurrentUser();
  if (!currentUser || !currentUser.id) {
    throw new Error('User not authenticated');
  }

  if (!currentUser.id) {
    throw new Error('User not authenticated');
  }

  try {
    const requestBody = {
      user_id: currentUser.id,
      time_range_days: options.timeRangeDays || 30,
      training_period_days: options.trainingPeriodDays || 180,
      sensitivity: options.sensitivity || 0.1,
      min_amount_threshold: options.minAmountThreshold || 100.0
    };

    const response = await fetchWithAuth(`${BASE_URL}/api/anomalies`, {
      method: 'POST',
      body: JSON.stringify(requestBody),
    }, REQUEST_TIMEOUT);

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    console.log('✅ Anomaly detection response:', data);

    return {
      total_transactions_analyzed: data.total_transactions_analyzed,
      anomalies_detected: data.anomalies_detected,
      anomaly_rate: data.anomaly_rate,
      anomalies: data.anomalies || [],
      model_metadata: data.model_metadata || {},
      execution_time_ms: data.execution_time_ms
    };
  } catch (error) {
    console.error('💥 Anomaly detection failed:', error);
    if (error.message.includes('Network request failed') || error.message.includes('timeout')) {
      throw new Error(`Cannot connect to anomaly detection service. Make sure the insights engine is running.`);
    }
    handleApiError(error, 'detecting anomalies');
  }
};

// Analytics Functions
const getAnalyticsSummary = async (options = {}) => {
  console.log('📊 Fetching analytics summary');

  try {
    // Build query parameters
    const params = new URLSearchParams();
    if (options.accountId) params.append('account_id', options.accountId);
    if (options.fromDate) params.append('from_date', options.fromDate);
    if (options.toDate) params.append('to_date', options.toDate);

    const queryString = params.toString();
    const url = `${BASE_URL}/api/analytics/summary${queryString ? `?${queryString}` : ''}`;

    console.log(`🔗 Analytics URL: ${url}`);

    const response = await fetchWithAuth(url, {
      method: 'GET',
    }, REQUEST_TIMEOUT);

    console.log(`📥 Analytics response status: ${response.status}`);

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    console.log('✅ Analytics summary received:', data);

    return {
      totalInflow: parseFloat(data.total_inflow || 0),
      totalOutflow: parseFloat(data.total_outflow || 0),
      balance: parseFloat(data.balance || 0),
      expenseCategories: data.expense_categories || [],
      incomeCategories: data.income_categories || [],
      periodStart: data.period_start,
      periodEnd: data.period_end,
      totalTransactions: data.total_transactions || 0
    };
  } catch (error) {
    console.error('💥 Analytics summary failed:', error);
    if (error.message.includes('Network request failed') || error.message.includes('timeout')) {
      throw new Error(`Cannot connect to analytics service at ${BASE_URL}. Make sure the server is running and accessible.`);
    }
    handleApiError(error, 'getting analytics summary');
  }
};

const getCategoryAnalytics = async (options = {}) => {
  console.log('📈 Fetching category analytics');

  try {
    const params = new URLSearchParams();
    if (options.transactionType) params.append('transaction_type', options.transactionType);
    if (options.accountId) params.append('account_id', options.accountId);
    if (options.fromDate) params.append('from_date', options.fromDate);
    if (options.toDate) params.append('to_date', options.toDate);

    const queryString = params.toString();
    const url = `${BASE_URL}/api/analytics/categories${queryString ? `?${queryString}` : ''}`;

    const response = await fetchWithAuth(url, {
      method: 'GET',
    }, REQUEST_TIMEOUT);

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    console.log('✅ Category analytics received:', data);
    return data;
  } catch (error) {
    console.error('💥 Category analytics failed:', error);
    if (error.message.includes('Network request failed') || error.message.includes('timeout')) {
      throw new Error(`Cannot connect to analytics service. Make sure the server is running and accessible.`);
    }
    handleApiError(error, 'getting category analytics');
  }
};

const getTimeSeriesAnalytics = async (options = {}) => {
  console.log('📈 Fetching time-series analytics');

  try {
    const params = new URLSearchParams();
    if (options.accountId) params.append('account_id', options.accountId);
    if (options.months) params.append('months', options.months.toString());

    const queryString = params.toString();
    const url = `${BASE_URL}/api/analytics/timeseries${queryString ? `?${queryString}` : ''}`;

    console.log(`🔗 Time-series URL: ${url}`);

    const response = await fetchWithAuth(url, {
      method: 'GET',
    }, REQUEST_TIMEOUT);

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    console.log('✅ Time-series analytics received:', data);
    return data;
  } catch (error) {
    console.error('💥 Time-series analytics failed:', error);
    if (error.message.includes('Network request failed') || error.message.includes('timeout')) {
      throw new Error(`Cannot connect to analytics service. Make sure the server is running and accessible.`);
    }
    handleApiError(error, 'getting time-series analytics');
  }
};

// Export transactions as CSV
const exportTransactionsCSV = async (options = {}) => {
  console.log('📊 Exporting transactions to CSV');

  try {
    const params = new URLSearchParams();
    if (options.accountId) params.append('account_id', options.accountId);
    if (options.fromDate) params.append('from_date', options.fromDate);
    if (options.toDate) params.append('to_date', options.toDate);
    if (options.format) params.append('format', options.format);

    const queryString = params.toString();
    const url = `${BASE_URL}/api/analytics/export${queryString ? `?${queryString}` : ''}`;

    console.log(`🔗 Export URL: ${url}`);

    const response = await fetchWithAuth(url, {
      method: 'GET',
    }, REQUEST_TIMEOUT);

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const error = new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    // For CSV export, we need to handle the response as text/blob
    const csvContent = await response.text();
    console.log('✅ CSV export received');

    // In React Native, we can return the CSV content
    // The calling component can handle saving or sharing
    return {
      content: csvContent,
      filename: `transactions_export_${new Date().toISOString().split('T')[0]}.csv`,
      mimeType: 'text/csv'
    };
  } catch (error) {
    console.error('💥 CSV export failed:', error);
    if (error.message.includes('Network request failed') || error.message.includes('timeout')) {
      throw new Error(`Cannot connect to export service. Make sure the server is running and accessible.`);
    }
    handleApiError(error, 'exporting transactions');
  }
};

// Export API functions and AuthManager
export { 
  syncTransactions, 
  fetchTransactionsFromServer, 
  askQuestion, 
  askAdvancedInsights,
  detectAnomalies,
  getAnalyticsSummary,
  getCategoryAnalytics,
  getTimeSeriesAnalytics,
  exportTransactionsCSV,
  AuthManager,
  testConnection,
  diagnosticNetworkTest,
  getNetworkInfo
};
