import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { StatusBar } from 'expo-status-bar';
import { View, Text, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

// Import screens
import HomeScreen from './screens/HomeScreen';
import TransactionsScreen from './screens/TransactionsScreen';
import ChatScreen from './screens/ChatScreen';

// Import storage service
import { initDatabase } from './services/storage';

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
            tabBarIcon: ({ focused, color, size }) => {
              let iconName;

              if (route.name === 'Home') {
                iconName = focused ? 'home' : 'home-outline';
              } else if (route.name === 'Transactions') {
                iconName = focused ? 'card' : 'card-outline';
              } else if (route.name === 'Chat') {
                iconName = focused ? 'chatbubble' : 'chatbubble-outline';
              }

              return <Ionicons name={iconName} size={size} color={color} />;
            },
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
          <Tab.Screen 
            name="Home" 
            component={HomeScreen}
            options={{
              tabBarLabel: 'Home',
            }}
          />
          <Tab.Screen 
            name="Transactions" 
            component={TransactionsScreen}
            options={{
              tabBarLabel: 'Transactions',
            }}
          />
          <Tab.Screen 
            name="Chat" 
            component={ChatScreen}
            options={{
              tabBarLabel: 'Chat',
            }}
          />
        </Tab.Navigator>
      </NavigationContainer>
      {dbError && (
        <View style={{ 
          position: 'absolute', 
          top: 100, 
          left: 20, 
          right: 20, 
          backgroundColor: '#ffebee', 
          padding: 10, 
          borderRadius: 5 
        }}>
          <Text style={{ color: '#c62828', fontSize: 12 }}>
            Database Warning: {dbError}
          </Text>
        </View>
      )}
    </>
  );
};

export default App;
