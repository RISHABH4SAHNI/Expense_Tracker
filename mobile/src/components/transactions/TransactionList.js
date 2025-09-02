/**
 * Transaction List Component
 * 
 * Displays all transactions with filtering capabilities
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Alert
} from 'react-native';
import TransactionCard from './TransactionCard';
import Icon from '../Icon';
import { getAllTransactions } from '../../services/transactions/transactionService';
import { TRANSACTION_CATEGORIES } from '../../features/manual/manualTransactionService';

const TransactionList = ({ onAddTransaction, refreshTrigger }) => {
  const [transactions, setTransactions] = useState([]);
  const [filteredTransactions, setFilteredTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilters, setActiveFilters] = useState({
    type: 'all', // 'all', 'income', 'expense'
    category: 'all',
    source: 'all' // 'all', 'manual', 'aa'
  });
  const [showFilters, setShowFilters] = useState(false);

  // Load transactions
  const loadTransactions = async () => {
    try {
      setLoading(true);
      console.log('🔄 Loading transactions...');
      const data = await getAllTransactions();
      console.log('✅ Loaded transactions:', data.length);
      setTransactions(data);
      applyFilters(data, activeFilters);
    } catch (error) {
      console.error('Error loading transactions:', error);
      // Don't show alert on first load if no transactions exist
      if (transactions.length > 0) {
      Alert.alert('Error', 'Failed to load transactions');
      }
    } finally {
      setLoading(false);
    }
  };

  // Apply filters to transactions
  const applyFilters = (data, filters) => {
    let filtered = [...data];

    // Filter by type
    if (filters.type !== 'all') {
      filtered = filtered.filter(t => t.type === filters.type);
    }

    // Filter by category
    if (filters.category !== 'all') {
      filtered = filtered.filter(t => t.category === filters.category);
    }

    // Filter by source
    if (filters.source !== 'all') {
      filtered = filtered.filter(t => {
        if (filters.source === 'manual') {
          return t.account_id === 'manual';
        } else if (filters.source === 'aa') {
          return t.account_id !== 'manual';
        }
        return true;
      });
    }

    setFilteredTransactions(filtered);
  };

  // Handle filter change
  const handleFilterChange = (filterType, value) => {
    const newFilters = { ...activeFilters, [filterType]: value };
    setActiveFilters(newFilters);
    applyFilters(transactions, newFilters);
  };

  // Refresh handler
  const onRefresh = async () => {
    setRefreshing(true);
    await loadTransactions();
    setRefreshing(false);
  };

  // Load transactions on mount and when refreshTrigger changes
  useEffect(() => {
    loadTransactions();
  }, [refreshTrigger]);

  // Get all unique categories from transactions
  const getAllCategories = () => {
    const categories = new Set();
    transactions.forEach(t => {
      if (t.category) categories.add(t.category);
    });
    return Array.from(categories).sort();
  };

  // Render filter section
  const renderFilterSection = () => {
    if (!showFilters) return null;

    const allCategories = getAllCategories();

    return (
      <View style={styles.filtersContainer}>
        {/* Type Filter */}
        <View style={styles.filterSection}>
          <Text style={styles.filterTitle}>Type</Text>
          <View style={styles.filterOptions}>
            {['all', 'income', 'expense'].map(type => (
              <TouchableOpacity
                key={type}
                style={[
                  styles.filterButton,
                  activeFilters.type === type && styles.filterButtonActive
                ]}
                onPress={() => handleFilterChange('type', type)}
              >
                <Text style={[
                  styles.filterButtonText,
                  activeFilters.type === type && styles.filterButtonTextActive
                ]}>
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Category Filter */}
        {allCategories.length > 0 && (
          <View style={styles.filterSection}>
            <Text style={styles.filterTitle}>Category</Text>
            <View style={styles.filterOptions}>
              <TouchableOpacity
                style={[
                  styles.filterButton,
                  activeFilters.category === 'all' && styles.filterButtonActive
                ]}
                onPress={() => handleFilterChange('category', 'all')}
              >
                <Text style={[
                  styles.filterButtonText,
                  activeFilters.category === 'all' && styles.filterButtonTextActive
                ]}>
                  All
                </Text>
              </TouchableOpacity>
              {allCategories.slice(0, 5).map(category => (
                <TouchableOpacity
                  key={category}
                  style={[
                    styles.filterButton,
                    activeFilters.category === category && styles.filterButtonActive
                  ]}
                  onPress={() => handleFilterChange('category', category)}
                >
                  <Text style={[
                    styles.filterButtonText,
                    activeFilters.category === category && styles.filterButtonTextActive
                  ]}>
                    {category}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

        {/* Source Filter */}
        <View style={styles.filterSection}>
          <Text style={styles.filterTitle}>Source</Text>
          <View style={styles.filterOptions}>
            {['all', 'manual', 'aa'].map(source => (
              <TouchableOpacity
                key={source}
                style={[
                  styles.filterButton,
                  activeFilters.source === source && styles.filterButtonActive
                ]}
                onPress={() => handleFilterChange('source', source)}
              >
                <Text style={[
                  styles.filterButtonText,
                  activeFilters.source === source && styles.filterButtonTextActive
                ]}>
                  {source === 'aa' ? 'Bank' : source.charAt(0).toUpperCase() + source.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>
    );
  };

  // Render header with filter toggle and add button
  const renderHeader = () => (
    <View style={styles.header}>
      <View style={styles.headerLeft}>
        <Text style={styles.headerTitle}>
          Transactions ({filteredTransactions.length})
        </Text>
        <TouchableOpacity
          style={styles.filterToggle}
          onPress={() => setShowFilters(!showFilters)}
        >
          <Icon 
            name={showFilters ? "filter" : "filter-outline"} 
            size={20} 
            color="#007AFF" 
          />
          <Text style={styles.filterToggleText}>Filters</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity
        style={styles.addButton}
        onPress={onAddTransaction}
      >
        <Icon name="add" size={24} color="#fff" />
      </TouchableOpacity>
    </View>
  );

  // Render transaction item
  const renderTransaction = ({ item }) => (
    <TransactionCard transaction={item} />
  );

  // Loading state
  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading transactions...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {renderHeader()}
      {renderFilterSection()}

      <FlatList
        data={filteredTransactions}
        renderItem={renderTransaction}
        keyExtractor={(item) => item.id.toString()}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="receipt-outline" size={64} color="#ccc" />
            <Text style={styles.emptyText}>No transactions found</Text>
            <Text style={styles.emptySubText}>
              {activeFilters.type === 'all' ? 'Add your first transaction to get started' : `No ${activeFilters.type} transactions found`}
            </Text>
            <TouchableOpacity
              style={styles.emptyButton}
              onPress={onAddTransaction}
            >
              <Text style={styles.emptyButtonText}>Add Transaction</Text>
            </TouchableOpacity>
          </View>
        }
        contentContainerStyle={filteredTransactions.length === 0 ? styles.emptyList : null}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#666',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 15,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  headerLeft: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  filterToggle: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  filterToggleText: {
    fontSize: 14,
    color: '#007AFF',
    marginLeft: 4,
  },
  addButton: {
    backgroundColor: '#007AFF',
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  filtersContainer: {
    backgroundColor: '#fff',
    paddingHorizontal: 20,
    paddingBottom: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  filterSection: {
    marginBottom: 15,
  },
  filterTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  filterOptions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  filterButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: '#f0f0f0',
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  filterButtonActive: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  filterButtonText: {
    fontSize: 12,
    color: '#666',
  },
  filterButtonTextActive: {
    color: '#fff',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 80,
    paddingHorizontal: 40,
  },
  emptyList: {
    flex: 1,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#666',
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubText: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    marginBottom: 20,
    lineHeight: 20,
  },
  emptyButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  emptyButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
});

export default TransactionList;