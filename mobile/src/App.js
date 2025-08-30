import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { StatusBar } from 'expo-status-bar';
import { Alert, View, Text, ActivityIndicator } from 'react-native';

// Import screens
import HomeScreen from './src/screens/HomeScreen';
import TransactionsScreen from './src/screens/TransactionsScreen';
import ChatScreen from './src/screens/ChatScreen';

// Import storage service
import { initDatabase } from './src/services/storage';

// Simple icons using text
const TabIcon = ({ name, focused }) => {
  const getIcon = () => {
    switch (name) {
      case 'Home':
        return focused ? '🏠' : '🏡';
      case 'Transactions':
        return focused ? '💰' : '💸';
      case 'Chat':
        return focused ? '💬' : '💭';
      default:
        return '📱';
    }
  };
  
  return getIcon();
};

const Tab = createBottomTabNavigator();

const App = () => {
  const [isDbReady, setIsDbReady] = useState(false);
  const [dbError, setDbError] = useState(null);

  useEffect(() => {
    const setupDatabase = async () => {
      try {
        await initDatabase();
        console.log('Database initialized successfully');
        setIsDbReady(true);
      } catch (error) {
        console.error('Error initializing database:', error);
        setDbError(error.message);
        // Don't block the app, just show error
        setIsDbReady(true);
      }
    };

    setupDatabase();
  }, []);

  if (!isDbReady) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={{ marginTop: 10 }}>Setting up database...</Text>
      </View>
    );
  }

  return (
    <>
      <StatusBar style="auto" />
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={({ route }) => ({
            tabBarIcon: ({ focused }) => (
              <TabIcon name={route.name} focused={focused} />
            ),
            tabBarActiveTintColor: '#007AFF',
            tabBarInactiveTintColor: 'gray',
            headerStyle: {
              backgroundColor: '#007AFF',
            },
            headerTintColor: '#FFFFFF',
            headerTitleStyle: {
              fontWeight: 'bold',
            },
          })}
        >
          <Tab.Screen name="Home" component={HomeScreen} />
          <Tab.Screen name="Transactions" component={TransactionsScreen} />
          <Tab.Screen name="Chat" component={ChatScreen} />
        </Tab.Navigator>
      </NavigationContainer>
      {dbError && (
        <View style={{ position: 'absolute', top: 100, left: 20, right: 20, backgroundColor: '#ffebee', padding: 10, borderRadius: 5 }}>
          <Text style={{ color: '#c62828', fontSize: 12 }}>Database Warning: {dbError}</Text>
        </View>
      )}
    </>
  );
};

export default App;
