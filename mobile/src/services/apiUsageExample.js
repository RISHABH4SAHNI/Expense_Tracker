/**
 * API Usage Examples
 * 
 * This file demonstrates how to use the API client functions
 * with proper auth token management and error handling.
 */

import { syncTransactions, fetchTransactionsFromServer, askQuestion, AuthManager } from './api';

// Example: Complete authentication flow
export const exampleAuthFlow = async () => {
  try {
    // Mock login - in real app, this would call your auth endpoint
    const mockAuthResponse = {
      accessToken: 'eyJhbGciOiJIUzI1NiIs...',
      refreshToken: 'refresh_token_here',
      userId: 'user_12345'
    };

    // Store auth data securely
    await AuthManager.setAuthToken(mockAuthResponse.accessToken);
    await AuthManager.setRefreshToken(mockAuthResponse.refreshToken);
    await AuthManager.setUserId(mockAuthResponse.userId);

    console.log('✅ Authentication successful');

    // Check if authenticated
    const isAuth = await AuthManager.isAuthenticated();
    console.log('Is authenticated:', isAuth);

  } catch (error) {
    console.error('Authentication failed:', error);
  }
};

// Example: Sync local transactions to server
export const exampleSyncTransactions = async () => {
  try {
    // Sample local transactions data
    const localTransactions = [
      {
        id: 'local_txn_001',
        ts: new Date().toISOString(),
        amount: 250.00,
        type: 'DEBIT',
        raw_desc: 'SWIGGY*ORDER #12345',
        account_id: 'acc_12345'
      },
      {
        id: 'local_txn_002',
        ts: new Date(Date.now() - 86400000).toISOString(), // Yesterday
        amount: 1200.00,
        type: 'DEBIT',
        raw_desc: 'BIG BAZAAR MUMBAI',
        account_id: 'acc_12345'
      }
    ];

    const syncResult = await syncTransactions(localTransactions);

    console.log('✅ Sync successful:', {
      status: syncResult.status,
      inserted: syncResult.inserted_count,
      updated: syncResult.updated_count,
      errors: syncResult.error_count
    });

    return syncResult;

  } catch (error) {
    console.error('❌ Sync failed:', error.message);
    throw error;
  }
};

// Example: Fetch transactions from server
export const exampleFetchTransactions = async () => {
  try {
    // Fetch all transactions (default pagination)
    const allTransactions = await fetchTransactionsFromServer();
    console.log('📄 All transactions:', allTransactions);

    // Fetch with filters
    const filteredTransactions = await fetchTransactionsFromServer({
      accountId: 'acc_12345',
      category: 'FOOD',
      limit: 10,
      offset: 0
    });
    console.log('🔍 Filtered transactions:', filteredTransactions);

    return filteredTransactions;

  } catch (error) {
    console.error('❌ Fetch failed:', error.message);
    throw error;
  }
};

// Example: Ask financial questions
export const exampleAskQuestion = async () => {
  try {
    // Ask a spending-related question
    const response1 = await askQuestion(
      "How much did I spend on food last week?",
      7 // context days
    );
    console.log('💬 Question 1 Response:', response1);

    // Ask a budget-related question
    const response2 = await askQuestion(
      "What are my top 3 spending categories this month?"
    );
    console.log('💬 Question 2 Response:', response2);

    return response2;

  } catch (error) {
    console.error('❌ Question failed:', error.message);
    throw error;
  }
};

// Example: Complete workflow
export const exampleCompleteWorkflow = async () => {
  try {
    console.log('🚀 Starting complete API workflow...');

    // 1. Authenticate
    await exampleAuthFlow();

    // 2. Sync local transactions
    await exampleSyncTransactions();

    // 3. Fetch updated transactions
    await exampleFetchTransactions();

    // 4. Ask questions about spending
    await exampleAskQuestion();

    console.log('✅ Complete workflow finished successfully');

  } catch (error) {
    console.error('❌ Workflow failed:', error.message);

    // Handle auth errors specifically
    if (error.message.includes('Authentication required')) {
      console.log('🔄 Clearing auth data and requiring re-login...');
      await AuthManager.clearAuthData();
    }
  }
};

// Example: Logout
export const exampleLogout = async () => {
  try {
    await AuthManager.clearAuthData();
    console.log('👋 Logged out successfully');
  } catch (error) {
    console.error('❌ Logout failed:', error);
  }
};