/**
 * Transaction Form Component
 * 
 * Allows users to manually add income/expense transactions
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
  Modal,
  KeyboardAvoidingView,
  Platform
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { TRANSACTION_CATEGORIES } from '../../features/manual/manualTransactionService';

const TransactionForm = ({ visible, onClose, onSubmit }) => {
  const [formData, setFormData] = useState({
    type: 'expense',
    amount: '',
    category: '',
    description: '',
    merchant: '',
    date: new Date().toISOString().split('T')[0], // Today's date
    notes: ''
  });

  const [showCategoryPicker, setShowCategoryPicker] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    try {
      // Validate form
      if (!formData.amount || parseFloat(formData.amount) <= 0) {
        Alert.alert('Error', 'Please enter a valid amount');
        return;
      }

      if (!formData.category) {
        Alert.alert('Error', 'Please select a category');
        return;
      }

      if (!formData.date) {
        Alert.alert('Error', 'Please select a date');
        return;
      }

      setLoading(true);

      // Prepare transaction data
      const transactionData = {
        ...formData,
        amount: parseFloat(formData.amount)
      };

      await onSubmit(transactionData);

      // Reset form
      setFormData({
        type: 'expense',
        amount: '',
        category: '',
        description: '',
        merchant: '',
        date: new Date().toISOString().split('T')[0],
        notes: ''
      });

      Alert.alert('Success', 'Transaction added successfully!');
      onClose();
    } catch (error) {
      console.error('Error submitting transaction:', error);
      Alert.alert('Error', 'Failed to add transaction. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const renderCategoryPicker = () => {
    const categories = formData.type === 'income' 
      ? TRANSACTION_CATEGORIES.INCOME 
      : TRANSACTION_CATEGORIES.EXPENSE;

    return (
      <Modal
        visible={showCategoryPicker}
        transparent
        animationType="slide"
        onRequestClose={() => setShowCategoryPicker(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.categoryModal}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Category</Text>
              <TouchableOpacity
                onPress={() => setShowCategoryPicker(false)}
                style={styles.closeButton}
              >
                <Ionicons name="close" size={24} color="#666" />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.categoryList}>
              {categories.map((category, index) => (
                <TouchableOpacity
                  key={index}
                  style={styles.categoryItem}
                  onPress={() => {
                    setFormData(prev => ({ ...prev, category }));
                    setShowCategoryPicker(false);
                  }}
                >
                  <Text style={styles.categoryText}>{category}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        </View>
      </Modal>
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView 
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={styles.header}>
          <TouchableOpacity onPress={onClose} style={styles.cancelButton}>
            <Text style={styles.cancelText}>Cancel</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Add Transaction</Text>
          <TouchableOpacity 
            onPress={handleSubmit} 
            style={[styles.saveButton, loading && styles.saveButtonDisabled]}
            disabled={loading}
          >
            <Text style={styles.saveText}>
              {loading ? 'Saving...' : 'Save'}
            </Text>
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.form}>
          {/* Transaction Type */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Type</Text>
            <View style={styles.typeContainer}>
              <TouchableOpacity
                style={[
                  styles.typeButton,
                  formData.type === 'expense' && styles.typeButtonActive
                ]}
                onPress={() => setFormData(prev => ({ ...prev, type: 'expense', category: '' }))}
              >
                <Ionicons 
                  name="arrow-up-outline" 
                  size={20} 
                  color={formData.type === 'expense' ? '#fff' : '#F44336'} 
                />
                <Text style={[
                  styles.typeButtonText,
                  formData.type === 'expense' && styles.typeButtonTextActive
                ]}>
                  Expense
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[
                  styles.typeButton,
                  formData.type === 'income' && styles.typeButtonActive
                ]}
                onPress={() => setFormData(prev => ({ ...prev, type: 'income', category: '' }))}
              >
                <Ionicons 
                  name="arrow-down-outline" 
                  size={20} 
                  color={formData.type === 'income' ? '#fff' : '#4CAF50'} 
                />
                <Text style={[
                  styles.typeButtonText,
                  formData.type === 'income' && styles.typeButtonTextActive
                ]}>
                  Income
                </Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Amount */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Amount</Text>
            <TextInput
              style={styles.amountInput}
              value={formData.amount}
              onChangeText={(text) => setFormData(prev => ({ ...prev, amount: text }))}
              placeholder="0.00"
              keyboardType="numeric"
              returnKeyType="done"
            />
          </View>

          {/* Category */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Category</Text>
            <TouchableOpacity
              style={styles.categorySelector}
              onPress={() => setShowCategoryPicker(true)}
            >
              <Text style={[
                styles.categorySelectorText,
                !formData.category && styles.placeholderText
              ]}>
                {formData.category || 'Select category'}
              </Text>
              <Ionicons name="chevron-down" size={20} color="#666" />
            </TouchableOpacity>
          </View>

          {/* Description */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Description</Text>
            <TextInput
              style={styles.textInput}
              value={formData.description}
              onChangeText={(text) => setFormData(prev => ({ ...prev, description: text }))}
              placeholder="Transaction description"
              returnKeyType="done"
            />
          </View>

          {/* Merchant */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Merchant (Optional)</Text>
            <TextInput
              style={styles.textInput}
              value={formData.merchant}
              onChangeText={(text) => setFormData(prev => ({ ...prev, merchant: text }))}
              placeholder="Store or merchant name"
              returnKeyType="done"
            />
          </View>

          {/* Date */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Date</Text>
            <TextInput
              style={styles.textInput}
              value={formData.date}
              onChangeText={(text) => setFormData(prev => ({ ...prev, date: text }))}
              placeholder="YYYY-MM-DD"
              returnKeyType="done"
            />
          </View>

          {/* Notes */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Notes (Optional)</Text>
            <TextInput
              style={[styles.textInput, styles.notesInput]}
              value={formData.notes}
              onChangeText={(text) => setFormData(prev => ({ ...prev, notes: text }))}
              placeholder="Additional notes"
              multiline
              numberOfLines={3}
              returnKeyType="done"
            />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>

      {renderCategoryPicker()}
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
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 15,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  cancelButton: {
    padding: 5,
  },
  cancelText: {
    fontSize: 16,
    color: '#007AFF',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
  },
  saveButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 8,
  },
  saveButtonDisabled: {
    backgroundColor: '#ccc',
  },
  saveText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  form: {
    flex: 1,
    padding: 20,
  },
  section: {
    marginBottom: 25,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 10,
  },
  typeContainer: {
    flexDirection: 'row',
    gap: 10,
  },
  typeButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 15,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#e0e0e0',
    backgroundColor: '#fff',
  },
  typeButtonActive: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  typeButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#666',
    marginLeft: 8,
  },
  typeButtonTextActive: {
    color: '#fff',
  },
  amountInput: {
    fontSize: 24,
    fontWeight: 'bold',
    textAlign: 'center',
    paddingVertical: 20,
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  textInput: {
    fontSize: 16,
    paddingVertical: 15,
    paddingHorizontal: 15,
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  categorySelector: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 15,
    paddingHorizontal: 15,
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  categorySelectorText: {
    fontSize: 16,
    color: '#333',
  },
  placeholderText: {
    color: '#999',
  },
  notesInput: {
    height: 80,
    textAlignVertical: 'top',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  categoryModal: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '70%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
  },
  closeButton: {
    padding: 5,
  },
  categoryList: {
    flex: 1,
  },
  categoryItem: {
    paddingVertical: 15,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  categoryText: {
    fontSize: 16,
    color: '#333',
  },
});

export default TransactionForm;