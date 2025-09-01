/**
 * Account Aggregator (AA) Service Client
 * 
 * Provides functions for Account Aggregator operations:
 * - Starting consent flow
 * - Polling consent status
 * - Triggering transaction sync
 * - Simulating webhooks for development
 */

import authService from './auth';

// API configuration
const getApiHost = () => {
  return '192.168.1.246'; // Use your computer's IP address for physical device testing
};

const API_HOST = getApiHost();
const API_PORT = '8000';
const BASE_URL = `http://${API_HOST}:${API_PORT}`;

// Development flag
const __DEV_MODE__ = __DEV__;

class AAService {
  /**
   * Start AA consent flow
   * 
   * @returns {Promise<Object>} Consent data with ref_id and consent_url
   * @throws {Error} If consent start fails
   */
  async startConsent() {
    try {
      console.log('🏦 [AA Service] Starting consent flow...');

      const headers = await authService.getAuthHeaders();
      const response = await fetch(`${BASE_URL}/aa/consent/start`, {
        method: 'POST',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const error = new Error(errorData?.detail || `HTTP ${response.status}: Failed to start consent`);
        error.status = response.status;
        error.data = errorData;
        throw error;
      }

      const data = await response.json();
      console.log('✅ [AA Service] Consent started:', data.ref_id);

      return {
        success: true,
        consent_id: data.consent_id,
        ref_id: data.ref_id,
        status: data.status,
        consent_url: data.consent_url,
        created_at: data.created_at,
      };
    } catch (error) {
      console.error('❌ [AA Service] Consent start failed:', error);
      throw error;
    }
  }

  /**
   * Poll consent status
   * 
   * @param {string} refId - AA consent reference ID
   * @returns {Promise<Object>} Consent status data
   * @throws {Error} If status poll fails
   */
  async pollConsent(refId) {
    try {
      console.log(`🔄 [AA Service] Polling consent status for ${refId}...`);

      if (!refId) {
        throw new Error('Reference ID is required for polling consent status');
      }

      const headers = await authService.getAuthHeaders();
      const response = await fetch(`${BASE_URL}/aa/consent/status?ref_id=${refId}`, {
        method: 'GET',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const error = new Error(errorData?.detail || `HTTP ${response.status}: Failed to poll consent status`);
        error.status = response.status;
        error.data = errorData;
        throw error;
      }

      const data = await response.json();
      console.log(`📊 [AA Service] Consent status: ${data.status}`);

      return {
        success: true,
        consent_id: data.consent_id,
        ref_id: data.ref_id,
        status: data.status,
        created_at: data.created_at,
        updated_at: data.updated_at,
        last_polled_at: data.last_polled_at,
      };
    } catch (error) {
      console.error('❌ [AA Service] Consent poll failed:', error);
      throw error;
    }
  }

  /**
   * Trigger transaction sync
   * 
   * @returns {Promise<Object>} Sync result
   * @throws {Error} If sync fails
   */
  async triggerSync() {
    try {
      console.log('🔄 [AA Service] Triggering transaction sync...');

      const headers = await authService.getAuthHeaders();
      const response = await fetch(`${BASE_URL}/aa/sync`, {
        method: 'POST',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const error = new Error(errorData?.detail || `HTTP ${response.status}: Sync failed`);
        error.status = response.status;
        error.data = errorData;
        throw error;
      }

      const data = await response.json();
      console.log('✅ [AA Service] Sync completed:', data.message || 'Success');

      return {
        success: true,
        message: data.message || 'Sync completed successfully',
        sync_logs: data.sync_logs || [],
        accounts_synced: data.accounts_synced || 0,
      };
    } catch (error) {
      console.error('❌ [AA Service] Sync failed:', error);
      throw error;
    }
  }

  /**
   * Get linked AA accounts
   * 
   * @returns {Promise<Object>} List of linked accounts
   * @throws {Error} If accounts fetch fails
   */
  async getAccounts() {
    try {
      console.log('📋 [AA Service] Fetching linked accounts...');

      const headers = await authService.getAuthHeaders();
      const response = await fetch(`${BASE_URL}/aa/accounts`, {
        method: 'GET',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const error = new Error(errorData?.detail || `HTTP ${response.status}: Failed to fetch accounts`);
        error.status = response.status;
        error.data = errorData;
        throw error;
      }

      const data = await response.json();
      console.log(`📋 [AA Service] Found ${data.accounts?.length || 0} linked accounts`);

      return {
        success: true,
        accounts: data.accounts || [],
        total_count: data.accounts?.length || 0,
      };
    } catch (error) {
      console.error('❌ [AA Service] Accounts fetch failed:', error);
      throw error;
    }
  }

  /**
   * Simulate webhook for development testing
   * 
   * @param {string} accountId - Account ID for mock webhook (default: hdfc_user_1)
   * @param {string} txId - Transaction ID from mock data (default: tx_mock_001)
   * @returns {Promise<Object>} Webhook simulation result
   * @throws {Error} If webhook simulation fails
   */
  async simulateWebhook(accountId = 'hdfc_user_1', txId = 'tx_mock_001') {
    try {
      if (!__DEV_MODE__) {
        throw new Error('Webhook simulation is only available in development mode');
      }

      console.log(`🧪 [AA Service] Simulating webhook for ${accountId}/${txId}...`);

      const headers = await authService.getAuthHeaders();
      const response = await fetch(`${BASE_URL}/aa/dev/mock-webhook?account_id=${accountId}&tx_id=${txId}`, {
        method: 'POST',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const error = new Error(errorData?.detail || `HTTP ${response.status}: Webhook simulation failed`);
        error.status = response.status;
        error.data = errorData;
        throw error;
      }

      const data = await response.json();
      console.log('🎯 [AA Service] Webhook simulation result:', data.message);

      return {
        success: data.success || true,
        message: data.message || 'Mock webhook sent successfully',
        account_id: accountId,
        transaction_id: txId,
      };
    } catch (error) {
      console.error('❌ [AA Service] Webhook simulation failed:', error);
      throw error;
    }
  }

  /**
   * Check authentication status
   * 
   * @returns {Promise<boolean>} Authentication status
   */
  async isAuthenticated() {
    return await authService.isAuthenticated();
  }
}

// Export singleton instance
const aaService = new AAService();
export default aaService;