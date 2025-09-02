/**
 * Debug Panel Component
 * Development-only component for debugging and testing
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
  ActivityIndicator,
  Modal
} from 'react-native';
import {
  getDatabaseStats,
  clearLocalDatabase,
  resetLocalDatabase,
  clearAsyncStorage,
  signOutFirebase
} from '../utils/debugUtils';

const DebugPanel = ({ visible, onClose, onRefresh }) => {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);

  const handleAction = async (actionFn, actionName, showStats = false) => {
    try {
      setLoading(true);
      const result = await actionFn();

      if (result.success) {
        Alert.alert('Success', result.message || `${actionName} completed successfully`);
        if (onRefresh) onRefresh(); // Refresh parent component
        if (showStats && result.data) {
          setStats(result.data);
        }
      } else {
        Alert.alert('Error', result.error || `${actionName} failed`);
      }
    } catch (error) {
      Alert.alert('Error', `${actionName} failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const showDatabaseStats = async () => {
    await handleAction(getDatabaseStats, 'Get Database Stats', true);
  };

  const confirmAction = (actionFn, actionName, message) => {
    Alert.alert(
      'Confirm Action',
      message,
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Confirm', 
          style: 'destructive',
          onPress: () => handleAction(actionFn, actionName)
        }
      ]
    );
  };

  const renderStats = () => {
    if (!stats) return null;

    return (
      <View style={styles.statsContainer}>
        <Text style={styles.statsTitle}>📊 Database Statistics</Text>
        <Text style={styles.statItem}>Total Transactions: {stats.totalTransactions}</Text>
        <Text style={styles.statItem}>Total Income: ₹{stats.totalIncome.toFixed(2)}</Text>
        <Text style={styles.statItem}>Total Expense: ₹{stats.totalExpense.toFixed(2)}</Text>
        <Text style={styles.statItem}>Balance: ₹{(stats.totalIncome - stats.totalExpense).toFixed(2)}</Text>
        <Text style={styles.statItem}>Categories: {stats.categories.length}</Text>
        <Text style={styles.statItem}>Merchants: {stats.merchants.length}</Text>
        {stats.dateRange.earliest && (
          <Text style={styles.statItem}>
            Date Range: {new Date(stats.dateRange.earliest).toLocaleDateString()} - {new Date(stats.dateRange.latest).toLocaleDateString()}
          </Text>
        )}
      </View>
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>🛠️ Debug Panel</Text>
          <TouchableOpacity onPress={onClose} style={styles.closeButton}>
            <Text style={styles.closeButtonText}>✕</Text>
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.content}>
          {loading && (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#007AFF" />
              <Text style={styles.loadingText}>Processing...</Text>
            </View>
          )}

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>📊 Database Info</Text>
            <TouchableOpacity
              style={styles.button}
              onPress={showDatabaseStats}
              disabled={loading}
            >
              <Text style={styles.buttonText}>Get Database Stats</Text>
            </TouchableOpacity>
          </View>

          {renderStats()}

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>🗑️ Database Actions</Text>
            <TouchableOpacity
              style={[styles.button, styles.warningButton]}
              onPress={() => confirmAction(
                clearLocalDatabase,
                'Clear Database',
                'This will delete all transactions from local database. Continue?'
              )}
              disabled={loading}
            >
              <Text style={styles.buttonText}>Clear Local Database</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.button, styles.dangerButton]}
              onPress={() => confirmAction(
                resetLocalDatabase,
                'Reset Database',
                'This will completely reset the database (drop and recreate tables). Continue?'
              )}
              disabled={loading}
            >
              <Text style={styles.buttonText}>Reset Database</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>🔄 Other Actions</Text>
            <TouchableOpacity
              style={[styles.button, styles.warningButton]}
              onPress={() => confirmAction(
                clearAsyncStorage,
                'Clear Cache',
                'This will clear all app cache and stored preferences. Continue?'
              )}
              disabled={loading}
            >
              <Text style={styles.buttonText}>Clear AsyncStorage</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.button, styles.warningButton]}
              onPress={() => confirmAction(
                signOutFirebase,
                'Sign Out Firebase',
                'This will sign you out from Firebase. Continue?'
              )}
              disabled={loading}
            >
              <Text style={styles.buttonText}>Sign Out Firebase</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  closeButton: {
    padding: 5,
  },
  closeButtonText: {
    fontSize: 18,
    color: '#666',
  },
  content: {
    flex: 1,
    padding: 20,
  },
  loadingContainer: {
    alignItems: 'center',
    padding: 20,
  },
  loadingText: {
    marginTop: 10,
    color: '#666',
  },
  section: {
    marginBottom: 30,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 15,
    color: '#333',
  },
  button: {
    backgroundColor: '#007AFF',
    padding: 15,
    borderRadius: 8,
    marginBottom: 10,
  },
  warningButton: {
    backgroundColor: '#FF9500',
  },
  dangerButton: {
    backgroundColor: '#FF3B30',
  },
  buttonText: {
    color: 'white',
    textAlign: 'center',
    fontWeight: '600',
  },
  statsContainer: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 8,
    marginBottom: 20,
  },
  statsTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  statItem: {
    fontSize: 14,
    marginBottom: 5,
    color: '#333',
  },
});

export default DebugPanel;