import React from 'react';
import { Text } from 'react-native';

// Simple icon replacement using Unicode characters
const iconMap = {
  'home': '🏠',
  'home-outline': '🏠',
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
  'refresh-outline': '🔄'
};

const Icon = ({ name, size = 24, color = '#000', style }) => {
  const iconText = iconMap[name] || '❓';
  return <Text style={[{ fontSize: size, color }, style]}>{iconText}</Text>;
};

export default Icon;