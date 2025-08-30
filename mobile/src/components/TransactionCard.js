import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

const TransactionCard = ({ transaction }) => {
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <View style={styles.container}>
      <View style={styles.leftSection}>
        <Text style={styles.description}>
          {transaction.description || 'No description'}
        </Text>
        <Text style={styles.category}>
          {transaction.category || 'Uncategorized'}
        </Text>
        <Text style={styles.date}>
          {formatDate(transaction.date)}
        </Text>
      </View>
      <View style={styles.rightSection}>
        <Text style={[
          styles.amount,
          transaction.type === 'income' ? styles.income : styles.expense
        ]}>
          {transaction.type === 'income' ? '+' : '-'}${Math.abs(transaction.amount).toFixed(2)}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    padding: 15,
    marginHorizontal: 15,
    marginVertical: 5,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 1,
    },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  leftSection: {
    flex: 1,
  },
  rightSection: {
    justifyContent: 'center',
  },
  description: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  category: {
    fontSize: 14,
    color: '#666',
    marginBottom: 2,
  },
  date: {
    fontSize: 12,
    color: '#999',
  },
  amount: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  income: {
    color: '#4CAF50',
  },
  expense: {
    color: '#F44336',
  },
});

export default TransactionCard;