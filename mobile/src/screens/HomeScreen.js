import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { getTransactions } from '../services/storage';
import { syncTransactions } from '../services/api';

const HomeScreen = () => {
  const [moneyIn, setMoneyIn] = useState(0);
  const [moneyOut, setMoneyOut] = useState(0);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    loadTransactionSummary();
  }, []);

  const loadTransactionSummary = async () => {
    try {
      setLoading(true);
      const transactions = await getTransactions();
      
      let totalIncome = 0;
      let totalExpense = 0;
      
      transactions.forEach(transaction => {
        if (transaction.type === 'income') {
          totalIncome += transaction.amount;
        } else if (transaction.type === 'expense') {
          totalExpense += transaction.amount;
        }
      });
      
      setMoneyIn(totalIncome);
      setMoneyOut(totalExpense);
    } catch (error) {
      console.error('Error loading transaction summary:', error);
      Alert.alert('Error', 'Failed to load transaction summary');
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      await syncTransactions();
      await loadTransactionSummary(); // Refresh data after sync
      Alert.alert('Success', 'Transactions synced successfully');
    } catch (error) {
      console.error('Error syncing transactions:', error);
      Alert.alert('Error', 'Failed to sync transactions');
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Expense Tracker</Text>
      
      <View style={styles.summaryContainer}>
        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Money In</Text>
          <Text style={[styles.summaryAmount, styles.incomeText]}>
            ${moneyIn.toFixed(2)}
          </Text>
        </View>
        
        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Money Out</Text>
          <Text style={[styles.summaryAmount, styles.expenseText]}>
            ${moneyOut.toFixed(2)}
          </Text>
        </View>
      </View>
      
      <View style={styles.netContainer}>
        <Text style={styles.netLabel}>Net Balance</Text>
        <Text style={[
          styles.netAmount,
          (moneyIn - moneyOut) >= 0 ? styles.incomeText : styles.expenseText
        ]}>
          ${(moneyIn - moneyOut).toFixed(2)}
        </Text>
      </View>
      
      <TouchableOpacity
        style={styles.syncButton}
        onPress={handleSync}
        disabled={syncing}
      >
        {syncing ? (
          <ActivityIndicator size="small" color="#FFFFFF" />
        ) : (
          <Text style={styles.syncButtonText}>Sync with Server</Text>
        )}
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
    padding: 20,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#666',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 30,
    color: '#333',
  },
  summaryContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 30,
  },
  summaryCard: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    padding: 20,
    borderRadius: 12,
    marginHorizontal: 5,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 3,
  },
  summaryLabel: {
    fontSize: 16,
    color: '#666',
    marginBottom: 8,
  },
  summaryAmount: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  incomeText: {
    color: '#4CAF50',
  },
  expenseText: {
    color: '#F44336',
  },
  netContainer: {
    backgroundColor: '#FFFFFF',
    padding: 20,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 30,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 3,
  },
  netLabel: {
    fontSize: 18,
    color: '#666',
    marginBottom: 8,
  },
  netAmount: {
    fontSize: 32,
    fontWeight: 'bold',
  },
  syncButton: {
    backgroundColor: '#007AFF',
    paddingVertical: 15,
    paddingHorizontal: 20,
    borderRadius: 8,
    alignItems: 'center',
  },
  syncButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default HomeScreen;
