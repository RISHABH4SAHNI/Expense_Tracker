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
import { TransactionForm } from '../components/transactions';
import { addTransaction } from '../services/transactions/transactionService';
import { syncTransactions } from '../services/api';

const HomeScreen = () => {
  const [moneyIn, setMoneyIn] = useState(0);
  const [moneyOut, setMoneyOut] = useState(0);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

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

  const handleQuickAdd = () => {
    setShowAddForm(true);
  };

  const handleAddTransaction = async (transactionData) => {
    try {
      console.log('🔄 Adding transaction from HomeScreen:', transactionData);
      await addTransaction(transactionData, 'manual');
      setRefreshTrigger(prev => prev + 1);
      await loadTransactionSummary(); // Refresh home screen data
      console.log('✅ Transaction added successfully');
    } catch (error) {
      console.error('❌ Error in HomeScreen handleAddTransaction:', error);
      throw error; // Re-throw to let TransactionForm handle it
    }
  };

  // Transform local transactions to backend format
  const transformTransactionsForSync = (localTransactions) => {
    console.log('🔄 Transforming transactions:', localTransactions.slice(0, 2)); // Log first 2 for debugging
    return localTransactions.map(transaction => {
      // Generate a unique ID if not present
      const transactionId = transaction.transaction_id || 
                           transaction.id?.toString() || 
                           `local_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      // Convert local format to backend format
      return {
        id: transactionId,
        ts: transaction.date ? new Date(transaction.date).toISOString() : new Date().toISOString(),
        amount: Math.abs(parseFloat(transaction.amount) || 0),
        type: transaction.type === 'income' ? 'credit' : 'debit',
        raw_desc: transaction.description || transaction.merchant || 'Local transaction',
        account_id: transaction.account_id || 'local_account_001'
      };
    }).filter(transaction => {
      const isValid = transaction.amount > 0 && transaction.raw_desc && transaction.id;
      if (!isValid) {
        console.warn('⚠️ Filtering out invalid transaction:', transaction);
      }
      return isValid;
    });
  };

  const handleSync = async () => {
    try {
      setSyncing(true);

      console.log('📱 Starting sync process...');

      // Get local transactions from storage
      const localTransactions = await getTransactions();
      console.log(`📊 Found ${localTransactions.length} local transactions`);

      if (localTransactions.length === 0) {
        Alert.alert(
          'No Data to Sync', 
          'There are no local transactions to sync with the server.',
          [{ text: 'OK' }]
        );
        return;
      }

      // Transform transactions to backend format
      const transformedTransactions = transformTransactionsForSync(localTransactions);
      console.log(`🔄 Transformed ${transformedTransactions.length} transactions for sync`);

      if (transformedTransactions.length === 0) {
        Alert.alert(
          'No Valid Data', 
          'No valid transactions found to sync. Please check your transaction data.',
          [{ text: 'OK' }]
        );
        return;
      }

      // Sync with server
      console.log('📤 Sending transactions to server:', {
        count: transformedTransactions.length,
        sample: transformedTransactions[0] // Log first transaction structure
      });

      const syncResult = await syncTransactions(transformedTransactions);
      console.log('✅ Sync completed:', syncResult);

      // Show success message with details
      Alert.alert(
        'Sync Successful', 
        `Synced ${syncResult.inserted_count || 0} new transactions and updated ${syncResult.updated_count || 0} existing transactions.`
      );
      // Refresh local data
      await loadTransactionSummary();
    } catch (error) {
      console.error('Error syncing transactions:', error);

      // Show more helpful error messages
      let errorMessage = 'Failed to sync transactions';
      if (error.message.includes('localTransactions')) {
        errorMessage = 'No valid transaction data found to sync';
      } else if (error.message.includes('Authentication required')) {
        errorMessage = 'Authentication required. Please log in again.';
      } else if (error.message.includes('Network')) {
        errorMessage = 'Network error. Please check your connection and try again.';
      } else if (error.message) {
        errorMessage = error.message;
      }

      Alert.alert('Sync Failed', errorMessage);
    } finally {
      setSyncing(false);
    }
  };

  // Refresh data when refreshTrigger changes
  useEffect(() => {
    loadTransactionSummary();
  }, [refreshTrigger]);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  return (
    <>
      <View style={styles.container}>
      <Text style={styles.title}>Expense Tracker</Text>
      
      <View style={styles.summaryContainer}>
        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Money In</Text>
          <Text style={[styles.summaryAmount, styles.incomeText]}>
            ₹{moneyIn.toFixed(2)}
          </Text>
        </View>
        
        <View style={styles.summaryCard}>
          <Text style={styles.summaryLabel}>Money Out</Text>
          <Text style={[styles.summaryAmount, styles.expenseText]}>
            ₹{moneyOut.toFixed(2)}
          </Text>
        </View>
      </View>
      
      <View style={styles.netContainer}>
        <Text style={styles.netLabel}>Net Balance</Text>
        <Text style={[
          styles.netAmount,
          (moneyIn - moneyOut) >= 0 ? styles.incomeText : styles.expenseText
        ]}>
          ₹{(moneyIn - moneyOut).toFixed(2)}
        </Text>
      </View>

      <View style={styles.actionsContainer}>
        <TouchableOpacity
          style={styles.quickAddButton}
          onPress={handleQuickAdd}
        >
          <Text style={styles.quickAddButtonText}>+ Quick Add</Text>
        </TouchableOpacity>

        <View style={styles.spacer} />
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

      <TransactionForm
        visible={showAddForm}
        onClose={() => setShowAddForm(false)}
        onSubmit={handleAddTransaction}
      />
    </>
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
  actionsContainer: {
    flexDirection: 'row',
    marginBottom: 20,
  },
  quickAddButton: {
    backgroundColor: '#4CAF50',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    alignItems: 'center',
    flex: 1,
  },
  quickAddButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  spacer: {
    width: 10,
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
