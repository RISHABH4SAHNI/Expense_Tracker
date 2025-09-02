import React from 'react';
import { Text } from 'react-native';

// Simple icon replacement using Unicode characters
const iconMap = {
  'home': '🏠',
  'home-outline': '🏠',
  'card': '💳',
  'card-outline': '💳',
  'link': '🔗',
  'link-outline': '🔗',
  'list': '📋',
  'list-outline': '📋',
  'chatbubble': '💬',
  'chatbubble-outline': '💬',
  'analytics': '📊',
  'analytics-outline': '📊',
  'add': '➕',
  'add-outline': '➕',
  'eye': '👁',
  'eye-outline': '👁',
  'eye-off': '🙈',
  'eye-off-outline': '🙈',
  'person': '👤',
  'person-outline': '👤',
  'mail': '📧',
  'mail-outline': '📧',
  'lock-closed': '🔒',
  'lock-closed-outline': '🔒',
  'refresh': '🔄',
  'refresh-outline': '🔄',
  'log-out-outline': '🚀',
  'log-out-outline': '🔓',
  'restaurant-outline': '🍽️',
  'car-outline': '🚗',
  'pie-chart-outline': '📊',
  'storefront-outline': '🏪',
  'bag-outline': '🛍️',
  'musical-notes-outline': '🎵',
  'receipt-outline': '🧾',
  'medical-outline': '⚕️',
  'school-outline': '🎓',
  'trending-up-outline': '📈',
  'ellipsis-horizontal-outline': '⋯',
  'filter': '🔽',
  'filter-outline': '🔽'
};

const Icon = ({ name, size = 24, color = '#000', style }) => {
  const iconText = iconMap[name] || '❓';
  return <Text style={[{ fontSize: size, color }, style]}>{iconText}</Text>;
};

export default Icon;
