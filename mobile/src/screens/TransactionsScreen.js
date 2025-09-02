import React, { useState, useEffect } from 'react';
import {
  View,
  TouchableOpacity,
  StyleSheet,
  Alert,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import Icon from '../components/Icon';
import { TransactionList, TransactionForm } from '../components/transactions';
import { addTransaction } from '../services/transactions/transactionService';

const TransactionsScreen = () => {
  const [showForm, setShowForm] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleAddTransaction = () => {
    setShowForm(true);
  };

  const handleSubmitTransaction = async (transactionData) => {
    try {
      await addTransaction(transactionData, 'manual');
      setRefreshTrigger(prev => prev + 1); // Trigger refresh
    } catch (error) {
      console.error('Error adding transaction:', error);
      throw error; // Let TransactionForm handle the error display
    }
  };

  return (
    <View style={styles.container}>
      <TransactionList
        onAddTransaction={handleAddTransaction}
        refreshTrigger={refreshTrigger}
      />

      <TransactionForm
        visible={showForm}
        onClose={() => setShowForm(false)}
        onSubmit={handleSubmitTransaction}
      />

      {/* Floating Action Button */}
      <TouchableOpacity
        style={styles.fab}
        onPress={handleAddTransaction}
      >
        <Icon name="add" size={28} color="#fff" />
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  fab: {
    position: 'absolute',
    bottom: 20,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#007AFF',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
});

export default TransactionsScreen;