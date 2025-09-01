import React from 'react';
import { createMaterialTopTabNavigator } from '@react-navigation/material-top-tabs';
import { View, Text, StyleSheet } from 'react-native';
import InsightsScreen from '../screens/InsightsScreen';
import AnalyticsScreen from '../screens/AnalyticsScreen';

const Tab = createMaterialTopTabNavigator();

const InsightsNavigator = () => {
  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Insights & Analytics</Text>
        <Text style={styles.headerSubtitle}>AI-powered financial intelligence</Text>
      </View>

      {/* Tab Navigator */}
      <Tab.Navigator
        screenOptions={{
          tabBarActiveTintColor: '#007AFF',
          tabBarInactiveTintColor: '#8E8E93',
          tabBarIndicatorStyle: {
            backgroundColor: '#007AFF',
            height: 3,
          },
          tabBarLabelStyle: {
            fontSize: 14,
            fontWeight: '600',
            textTransform: 'none',
          },
          tabBarStyle: {
            backgroundColor: '#fff',
            elevation: 0,
            shadowOpacity: 0,
            borderBottomWidth: 1,
            borderBottomColor: '#E5E5EA',
          },
        }}
      >
        <Tab.Screen 
          name="AIInsights" 
          component={InsightsScreen}
          options={{
            tabBarLabel: 'AI Insights',
          }}
        />
        <Tab.Screen 
          name="Analytics" 
          component={AnalyticsScreen}
          options={{
            tabBarLabel: 'Analytics',
          }}
        />
      </Tab.Navigator>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  header: {
    padding: 20,
    backgroundColor: '#007AFF',
    paddingTop: 60,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  headerSubtitle: {
    fontSize: 16,
    color: 'rgba(255, 255, 255, 0.8)',
    marginTop: 4,
  },
});

export default InsightsNavigator;
