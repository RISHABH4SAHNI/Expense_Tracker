import React, { useState, useEffect, useRef, useContext } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import authService from '../services/auth';
import { AuthContext } from '../context/AuthContext';
import aaService from '../services/aa';

const { width } = Dimensions.get('window');

// Development flag - set to true to show dev features
const __DEV_MODE__ = __DEV__;

const BankLinkScreen = ({ navigation }) => {
  // Access AuthContext for proper logout handling
  const { signOut } = useContext(AuthContext);
  const [linkingState, setLinkingState] = useState('NOT_LINKED'); // NOT_LINKED, PENDING, LINKED
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [consentData, setConsentData] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [polling, setPolling] = useState(false);
  const [authError, setAuthError] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Counter to ensure unique log IDs
  const logCounter = useRef(0);

  // Refs for cleanup
  const pollingInterval = useRef(null);

  // API base URL (should match your API service)
  const API_BASE = 'http://192.168.1.246:8000';

  useEffect(() => {
    // Add a small delay to ensure token storage is complete after login
    const initializeWithDelay = async () => {
      // Wait a bit to ensure any recent login token storage is complete
      await new Promise(resolve => setTimeout(resolve, 500));
      loadBankLinkStatus();
    };

    initializeWithDelay();

    // Cleanup polling on unmount
    return () => {
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current);
      }
    };
  }, []);

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    // Use counter + timestamp to ensure uniqueness even for rapid calls
    logCounter.current += 1;
    const logEntry = {
      id: `${Date.now()}_${logCounter.current}`,
      timestamp,
      message,
      type, // info, success, error, warning
    };
    setLogs(prev => [logEntry, ...prev.slice(0, 19)]); // Keep last 20 logs
    console.log(`[BankLink ${type.toUpperCase()}] ${message}`);
  };

  // Helper function to handle token refresh
  const handleAuthRefresh = async () => {
    // Prevent multiple refresh attempts
    if (isRefreshing) {
      return false;
    }

    setIsRefreshing(true);

    try {
      addLog('Token expired, attempting to refresh...', 'warning');

      // First, clear any potentially stale cached tokens
      addLog('Clearing potentially stale cached tokens...', 'info');

      const refreshResult = await authService.refresh();
      if (refreshResult.success) {
        addLog('Token refreshed successfully', 'success');
        setIsRefreshing(false);
        return true;
      } else {
        addLog('Token refresh failed - please login again', 'error');
        await handleCompleteLogout();
        setIsRefreshing(false);
        return false;
      }
    } catch (error) {
      addLog(`Token refresh error: ${error.message}`, 'error');

      // If no refresh token available or revoked, immediately set auth error
      if (error.message.includes('No refresh token available') || 
          error.message.includes('revoked') || 
          error.message.includes('invalid')) {
        await handleCompleteLogout();
      }
      setIsRefreshing(false);
      return false;
    }
  };

  // Helper function to handle complete logout and cleanup
  const handleCompleteLogout = async () => {
    addLog('Clearing authentication data...', 'warning');
    await authService.logout();
    setAuthError(true);
    addLog('Please return to login screen to authenticate again', 'error');
  };

  // Helper function to go back to login
  const goToLogin = () => {
    addLog('Signing out and redirecting to login...', 'warning');
    signOut();
  };

  const loadBankLinkStatus = async () => {
    // Don't make requests if we already have an auth error
    if (authError) {
      return;
    }

    try {
      addLog('Checking bank link status...');


      // Clear auth error when retrying
      setAuthError(false);

      // Check if user is authenticated
      const isAuth = await authService.isAuthenticated();
      addLog(`Authentication status: ${isAuth ? 'Authenticated' : 'Not authenticated'}`, isAuth ? 'success' : 'warning');

      // Use fresh headers to avoid caching issues
      const headers = await authService.getAuthHeadersFresh();

      // If not authenticated, immediately set auth error and return
      if (!isAuth) {
        await handleCompleteLogout();
        return;
      }

      // Log headers for debugging (without sensitive info)
      addLog(`Request headers: ${JSON.stringify(Object.keys(headers))}`, 'info');

      // Try using AA service first, fall back to direct API call if needed
      try {
        const result = await aaService.getAccounts();

        if (result.success) {
          if (result.accounts && result.accounts.length > 0) {
            setAccounts(result.accounts);
            setLinkingState('LINKED');
            addLog(`Found ${result.accounts.length} linked account(s)`, 'success');
          } else {
            setLinkingState('NOT_LINKED');
            addLog('No linked accounts found');
          }
          return;
        }
      } catch (serviceError) {
        addLog(`AA service error: ${serviceError.message}`, 'warning');
        // Fall back to direct API call below
      }

      // Fallback: Direct API call with existing error handling
      const response = await fetch(`${API_BASE}/aa/accounts`, {
        method: 'GET',
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        if (data.accounts && data.accounts.length > 0) {
          setAccounts(data.accounts);
          setLinkingState('LINKED');
          addLog(`Found ${data.accounts.length} linked account(s)`, 'success');
        } else {
          setLinkingState('NOT_LINKED');
          addLog('No linked accounts found');
        }
      } else {
        const errorText = await response.text().catch(() => 'Unknown error');
        addLog(`Failed to check account status: ${response.status}`, 'error');
        addLog(`Response: ${errorText}`, 'error');

        if (response.status === 401) {
          // Try to refresh token but don't retry automatically
          const refreshSuccess = await handleAuthRefresh();
          if (!refreshSuccess) {
            addLog('Authentication failed - please login again', 'warning');
          }
        }
      }
    } catch (error) {
      addLog(`Error checking bank status: ${error.message}`, 'error');
    }
  };

  const startConsentFlow = async () => {
    // Don't start consent flow if we have an auth error
    if (authError) {
      addLog('Please login first before starting consent flow', 'warning');
      return;
    }

    // Don't test webhook if we have an auth error
    if (authError) {
      addLog('Please login first before testing webhook', 'warning');
      return;
    }

    // Check authentication first
    const isAuth = await authService.isAuthenticated();
    if (!isAuth) {
      await handleCompleteLogout();
      return;
    }

    try {
      setLoading(true);
      addLog('Starting AA consent flow...');

      // Check authentication first
      const isAuth = await authService.isAuthenticated();
      if (!isAuth) {
        await handleCompleteLogout();
        return;
      }

      // Try using AA service first, fall back to direct API call if needed
      try {
        const result = await aaService.startConsent();

        if (result.success) {
          const data = {
            ref_id: result.ref_id,
            consent_url: result.consent_url,
            consent_id: result.consent_id,
            status: result.status
          };
          setConsentData(data);
          addLog(`Consent started: ${data.ref_id}`, 'success');
          addLog(`Opening consent URL: ${data.consent_url}`);

          // Open consent URL in browser
          if (data.consent_url) {
            const browserResult = await WebBrowser.openBrowserAsync(data.consent_url, {
              dismissButtonStyle: 'done',
              presentationStyle: WebBrowser.WebBrowserPresentationStyle.FORM_SHEET,
            });

            addLog(`WebBrowser result: ${browserResult.type}`);

            if (browserResult.type === 'dismiss' || browserResult.type === 'cancel') {
              // User closed browser, start polling for consent status
              setLinkingState('PENDING');
              startPollingConsentStatus(data.ref_id);
            }
          } else {
            addLog('No consent URL received', 'warning');
          }
          return;
        }
      } catch (serviceError) {
        addLog(`AA service error: ${serviceError.message}`, 'warning');
        // Fall back to direct API call below
      }

      // Fallback: Direct API call with existing error handling
      const headers = await authService.getAuthHeaders();
      const response = await fetch(`${API_BASE}/aa/consent/start`, {
        method: 'POST',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      setConsentData(data);
      addLog(`Consent started: ${data.ref_id}`, 'success');
      addLog(`Opening consent URL: ${data.consent_url}`);

      // Open consent URL in browser
      if (data.consent_url) {
        const result = await WebBrowser.openBrowserAsync(data.consent_url, {
          dismissButtonStyle: 'done',
          presentationStyle: WebBrowser.WebBrowserPresentationStyle.FORM_SHEET,
        });

        addLog(`WebBrowser result: ${result.type}`);

        if (result.type === 'dismiss' || result.type === 'cancel') {
          // User closed browser, start polling for consent status
          setLinkingState('PENDING');
          startPollingConsentStatus(data.ref_id);
        }
      } else {
        addLog('No consent URL received', 'warning');
      }
    } catch (error) {
      addLog(`Consent flow failed: ${error.message}`, 'error');
      Alert.alert('Error', `Failed to start consent flow: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const startPollingConsentStatus = (refId) => {
    addLog(`Starting to poll consent status for ${refId}...`);
    // Don't start polling if we have an auth error
    if (authError) {
      return;
    }

    setPolling(true);

    // Clear any existing polling
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
    }

    let pollCount = 0;
    const maxPolls = 60; // Poll for up to 3 minutes (60 * 3s = 180s)

    pollingInterval.current = setInterval(async () => {
      pollCount++;

      try {
        addLog(`Polling consent status... (${pollCount}/${maxPolls})`);

        // Try using AA service first, fall back to direct API call if needed
        try {
          const result = await aaService.pollConsent(refId);

          if (result.success) {
            addLog(`Consent status: ${result.status}`);

            if (result.status === 'LINKED') {
              // Success! Stop polling and sync transactions
              clearInterval(pollingInterval.current);
              setPolling(false);
              setLinkingState('LINKED');
              addLog('🎉 Account successfully linked!', 'success');

              // Trigger immediate sync
              await triggerSync();

              // Reload account status
              await loadBankLinkStatus();
              return;
            } else if (result.status === 'FAILED' || result.status === 'REJECTED') {
              // Failed - stop polling
              clearInterval(pollingInterval.current);
              setPolling(false);
              setLinkingState('NOT_LINKED');
              addLog(`Consent ${result.status.toLowerCase()}`, 'error');
              Alert.alert('Consent Failed', `The consent was ${result.status.toLowerCase()}. Please try again.`);
              return;
            }

            // Continue polling for PENDING status
            return;
          }
        } catch (serviceError) {
          addLog(`AA service poll error: ${serviceError.message}`, 'warning');
          // Fall back to direct API call below
        }

        // Fallback: Direct API call with existing error handling
        const headers = await authService.getAuthHeaders();
        const response = await fetch(`${API_BASE}/aa/consent/status?ref_id=${refId}`, {
          method: 'GET',
          headers,
        });

        if (response.ok) {
          const statusData = await response.json();
          addLog(`Consent status: ${statusData.status}`);

          if (statusData.status === 'LINKED') {
            // Success! Stop polling and sync transactions
            clearInterval(pollingInterval.current);
            setPolling(false);
            setLinkingState('LINKED');
            addLog('🎉 Account successfully linked!', 'success');

            // Trigger immediate sync
            await triggerSync();

            // Reload account status
            await loadBankLinkStatus();
            return;
          } else if (statusData.status === 'FAILED' || statusData.status === 'REJECTED') {
            // Failed - stop polling
            clearInterval(pollingInterval.current);
            setPolling(false);
            setLinkingState('NOT_LINKED');
            addLog(`Consent ${statusData.status.toLowerCase()}`, 'error');
            Alert.alert('Consent Failed', `The consent was ${statusData.status.toLowerCase()}. Please try again.`);
            return;
          }

          // Continue polling for PENDING status
        } else {
          addLog(`Status poll failed: ${response.status}`, 'warning');
        }
      } catch (error) {
        addLog(`Polling error: ${error.message}`, 'error');
      }

      // Stop polling after max attempts
      if (pollCount >= maxPolls) {
        clearInterval(pollingInterval.current);
        setPolling(false);
        addLog('Polling timeout - consent may still be processing', 'warning');
        Alert.alert(
          'Polling Timeout', 
          'We stopped checking the consent status. It may still be processing. Try refreshing the status manually.'
        );
      }
    }, 3000); // Poll every 3 seconds
  };

  const triggerSync = async () => {
    // Don't sync if we have an auth error
    if (authError) {
      addLog('Please login first before syncing transactions', 'warning');
      return;
    }

    // Check authentication first
    const isAuth = await authService.isAuthenticated();
    if (!isAuth) {
      await handleCompleteLogout();
      return;
    }

    try {
      addLog('Triggering transaction sync...');

      // Try using AA service first, fall back to direct API call if needed
      try {
        const result = await aaService.triggerSync();

        if (result.success) {
          addLog(`Sync completed: ${result.message}`, 'success');
          if (result.accounts_synced > 0) {
            addLog(`Synced ${result.accounts_synced} accounts`, 'success');
          }
          return;
        }
      } catch (serviceError) {
        addLog(`AA service sync error: ${serviceError.message}`, 'warning');
        // Fall back to direct API call below
      }

      // Fallback: Direct API call with existing error handling
      const headers = await authService.getAuthHeaders();
      const response = await fetch(`${API_BASE}/aa/sync`, {
        method: 'POST',
        headers,
      });

      if (response.ok) {
        const syncData = await response.json();
        addLog(`Sync completed: ${syncData.message || 'Success'}`, 'success');
      } else {
        const errorData = await response.json().catch(() => null);
        addLog(`Sync failed: ${errorData?.detail || `HTTP ${response.status}`}`, 'error');
      }
    } catch (error) {
      addLog(`Sync error: ${error.message}`, 'error');
    }
  };

  const simulateWebhook = async () => {
    try {
      addLog('Triggering mock webhook...');
      setLoading(true);

      // Try using AA service first, fall back to direct API call if needed
      try {
        const result = await aaService.simulateWebhook('hdfc_user_1', 'tx_mock_001');

        if (result.success) {
          addLog(`Mock webhook result: ${result.message}`, 'success');

          // Slight delay then reload accounts to show new transactions
          setTimeout(() => {
            loadBankLinkStatus();
          }, 2000);

          Alert.alert('Success', 'Mock webhook sent! Check the Transactions screen to see new data.');
          return;
        }
      } catch (serviceError) {
        addLog(`AA service webhook error: ${serviceError.message}`, 'warning');
        // Fall back to direct API call below
      }

      // Fallback: Direct API call with existing error handling
      const headers = await authService.getAuthHeaders();
      const response = await fetch(`${API_BASE}/aa/dev/mock-webhook?account_id=hdfc_user_1&tx_id=tx_mock_001`, {
        method: 'POST',
        headers,
      });

      if (response.ok) {
        const result = await response.json();
        addLog(`Mock webhook result: ${result.message}`, 'success');

        // Slight delay then reload accounts to show new transactions
        setTimeout(() => {
          loadBankLinkStatus();
        }, 2000);

        Alert.alert('Success', 'Mock webhook sent! Check the Transactions screen to see new data.');
      } else {
        const errorData = await response.json().catch(() => null);
        addLog(`Mock webhook failed: ${errorData?.detail || `HTTP ${response.status}`}`, 'error');
        Alert.alert('Error', errorData?.detail || 'Failed to send mock webhook');
      }
    } catch (error) {
      addLog(`Mock webhook error: ${error.message}`, 'error');
      Alert.alert('Error', `Failed to trigger mock webhook: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const stopPolling = () => {
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
      setPolling(false);
      addLog('Stopped polling consent status');
    }
  };

  const getStatusColor = () => {
    switch (linkingState) {
      case 'LINKED': return '#4CAF50';
      case 'PENDING': return '#FF9800';
      default: return '#757575';
    }
  };

  const getStatusIcon = () => {
    switch (linkingState) {
      case 'LINKED': return '✅';
      case 'PENDING': return '⏳';
      default: return '❌';
    }
  };

  const renderAccountsList = () => {
    if (accounts.length === 0) return null;

    return (
      <View style={styles.accountsContainer}>
        <Text style={styles.sectionTitle}>Linked Accounts</Text>
        {accounts.map((account, index) => (
          <View key={index} style={styles.accountItem}>
            <Text style={styles.accountName}>{account.display_name || account.aa_account_id}</Text>
            <Text style={styles.accountId}>ID: {account.aa_account_id}</Text>
            {account.last_sync_at && (
              <Text style={styles.accountSync}>
                Last sync: {new Date(account.last_sync_at).toLocaleString()}
              </Text>
            )}
          </View>
        ))}
      </View>
    );
  };

  return (
    <ScrollView style={styles.container}>
      {/* Status Section */}
      <View style={styles.statusContainer}>
        <Text style={styles.title}>Bank Account Linking</Text>
        <View style={styles.statusRow}>
          <Text style={styles.statusIcon}>{getStatusIcon()}</Text>
          <Text style={[styles.statusText, { color: getStatusColor() }]}>
            {linkingState.replace('_', ' ')}
          </Text>
        </View>

        {polling && (
          <View style={styles.pollingIndicator}>
            <ActivityIndicator size="small" color="#FF9800" />
            <Text style={styles.pollingText}>Checking consent status...</Text>
          </View>
        )}
      </View>

      {/* Authentication Error Section */}
      {authError && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorTitle}>⚠️ Authentication Required</Text>
          <Text style={styles.errorText}>
            Your session has expired. Please login again to continue.
          </Text>
          <TouchableOpacity 
            style={[styles.button, styles.warningButton]} 
            onPress={goToLogin}
          >
            <Text style={styles.buttonText}>Go to Login</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Action Buttons */}
      <View style={styles.buttonsContainer}>
        {!authError && linkingState === 'NOT_LINKED' && (
          <TouchableOpacity 
            style={[styles.button, styles.primaryButton]} 
            onPress={startConsentFlow}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="white" />
            ) : (
              <Text style={styles.buttonText}>Link Bank Account</Text>
            )}
          </TouchableOpacity>
        )}

        {!authError && linkingState === 'PENDING' && (
          <TouchableOpacity 
            style={[styles.button, styles.warningButton]} 
            onPress={stopPolling}
            disabled={!polling}
          >
            <Text style={styles.buttonText}>Stop Checking</Text>
          </TouchableOpacity>
        )}

        {!authError && linkingState === 'LINKED' && (
          <TouchableOpacity 
            style={[styles.button, styles.successButton]} 
            onPress={triggerSync}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="white" />
            ) : (
              <Text style={styles.buttonText}>Sync Transactions</Text>
            )}
          </TouchableOpacity>
        )}

        <TouchableOpacity 
          style={[styles.button, styles.secondaryButton]} 
          onPress={loadBankLinkStatus}
          disabled={loading || authError}
        >
          <Text style={styles.buttonTextSecondary}>Refresh Status</Text>
        </TouchableOpacity>

        {/* Retry button for after login */}
        <TouchableOpacity 
          style={[styles.button, styles.warningButton]} 
          onPress={async () => {
            addLog('Retrying after login - clearing cached data...', 'info');
            setAuthError(false);
            // Small delay to ensure new tokens are loaded
            await new Promise(resolve => setTimeout(resolve, 1000));
            loadBankLinkStatus();
          }}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color="white" />
          ) : (
            <Text style={styles.buttonText}>🔄 Retry After Login</Text>
          )}
        </TouchableOpacity>

        {/* Development Features */}
        {__DEV_MODE__ && linkingState === 'LINKED' && (
          <TouchableOpacity 
            style={[styles.button, styles.devButton]} 
            onPress={simulateWebhook}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="white" />
            ) : (
              <Text style={styles.buttonText}>🧪 Simulate Webhook</Text>
            )}
          </TouchableOpacity>
        )}
      </View>

      {/* Linked Accounts */}
      {renderAccountsList()}

      {/* Logs Section */}
      <View style={styles.logsContainer}>
        <Text style={styles.sectionTitle}>Activity Log</Text>
        {logs.length === 0 ? (
          <Text style={styles.noLogs}>No activity yet</Text>
        ) : (
          logs.map((log) => (
            <View key={log.id} style={styles.logItem}>
              <Text style={styles.logTimestamp}>{log.timestamp}</Text>
              <Text style={[styles.logMessage, { color: getLogColor(log.type) }]}>
                {log.message}
              </Text>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
};

const getLogColor = (type) => {
  switch (type) {
    case 'success': return '#4CAF50';
    case 'error': return '#F44336';
    case 'warning': return '#FF9800';
    default: return '#757575';
  }
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  statusContainer: {
    backgroundColor: 'white',
    margin: 16,
    padding: 20,
    borderRadius: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 16,
    textAlign: 'center',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  statusIcon: {
    fontSize: 24,
    marginRight: 8,
  },
  statusText: {
    fontSize: 18,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  pollingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
  },
  pollingText: {
    marginLeft: 8,
    fontSize: 14,
    color: '#FF9800',
  },
  buttonsContainer: {
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  button: {
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 8,
    marginBottom: 12,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
  },
  primaryButton: {
    backgroundColor: '#2196F3',
  },
  successButton: {
    backgroundColor: '#4CAF50',
  },
  warningButton: {
    backgroundColor: '#FF9800',
  },
  secondaryButton: {
    backgroundColor: 'transparent',
    borderWidth: 2,
    borderColor: '#2196F3',
  },
  devButton: {
    backgroundColor: '#9C27B0',
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonTextSecondary: {
    color: '#2196F3',
  },
  errorContainer: {
    marginBottom: 20,
    padding: 16,
    backgroundColor: '#FFF3E0',
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#FF9800',
  },
  errorTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#E65100',
    marginBottom: 8,
  },
  errorText: {
    fontSize: 14,
    color: '#BF360C',
    marginBottom: 12,
    lineHeight: 20,
    fontSize: 16,
    fontWeight: '600',
  },
  accountsContainer: {
    backgroundColor: 'white',
    margin: 16,
    marginTop: 0,
    padding: 16,
    borderRadius: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
  },
  accountItem: {
    padding: 12,
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
    marginBottom: 8,
  },
  accountName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  accountId: {
    fontSize: 14,
    color: '#666',
    marginTop: 2,
  },
  accountSync: {
    fontSize: 12,
    color: '#999',
    marginTop: 4,
  },
  logsContainer: {
    backgroundColor: 'white',
    margin: 16,
    marginTop: 0,
    padding: 16,
    borderRadius: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    marginBottom: 32,
  },
  noLogs: {
    textAlign: 'center',
    color: '#999',
    fontStyle: 'italic',
    padding: 20,
  },
  logItem: {
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  logTimestamp: {
    fontSize: 12,
    color: '#999',
    marginBottom: 2,
  },
  logMessage: {
    fontSize: 14,
    lineHeight: 20,
  },
  errorContainer: {
    marginBottom: 20,
    padding: 16,
    backgroundColor: '#FFF3E0',
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#FF9800',
  },
  errorTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#E65100',
    marginBottom: 8,
  },
  errorText: {
    fontSize: 14,
    color: '#BF360C',
    marginBottom: 12,
    lineHeight: 20,
  },
});

export default BankLinkScreen;