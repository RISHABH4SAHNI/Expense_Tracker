/**
 * Debug Utilities for Development
 * Simple utility to clear local database
 */

import { clearAllData } from '../storage/db';

/**
 * Clear all transaction data from local database
 */
export const clearLocalDatabase = async () => {
  try {
    console.log('🗑️ Clearing local database...');
    await clearAllData();
    console.log('✅ Local database cleared successfully');
    return { success: true, message: 'Database cleared' };
  } catch (error) {
    console.error('❌ Error clearing database:', error);
    return { success: false, error: error.message };
  }
};

export default {
  clearLocalDatabase
};