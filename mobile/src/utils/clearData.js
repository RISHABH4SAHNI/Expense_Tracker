/**
 * Utility to clear all app data for fresh start
 */

import { clearAllData } from '../storage/db';
import * as SecureStore from 'expo-secure-store';
import { Alert } from 'react-native';

export const clearAllAppData = async () => {
  return new Promise((resolve, reject) => {
    Alert.alert(
      '🧹 Clear All Data',
      'This will delete all local transactions, accounts, and cached data. This action cannot be undone.',
      [
        {
          text: 'Cancel',
          style: 'cancel',
          onPress: () => resolve(false)
        },
        {
          text: 'Clear All Data',
          style: 'destructive',
          onPress: async () => {
            try {
              console.log('🧹 Starting complete data cleanup...');
              
              // Clear all local database data
              await clearAllData();
              console.log('✅ Database cleared');
              
              // Clear any cached authentication data (optional)
              try {
                await SecureStore.deleteItemAsync('auth_token');
                await SecureStore.deleteItemAsync('refresh_token');
                await SecureStore.deleteItemAsync('user_id');
                console.log('✅ Auth cache cleared');
              } catch (authError) {
                console.log('ℹ️ No auth cache to clear');
              }
              
              console.log('🎉 Complete data cleanup finished');
              
              Alert.alert(
                'Success',
                'All data cleared! You can now login fresh and add new data.',
                [{ text: 'OK' }]
              );
              
              resolve(true);
            } catch (error) {
              console.error('❌ Error during cleanup:', error);
              Alert.alert(
                'Error',
                `Failed to clear data: ${error.message}`,
                [{ text: 'OK' }]
              );
              reject(error);
            }
          }
        }
      ]
    );
  });
};
