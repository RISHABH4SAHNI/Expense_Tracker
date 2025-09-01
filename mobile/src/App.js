import React, { useEffect, useState, useContext } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createStackNavigator } from '@react-navigation/stack';
import { StatusBar, View, Text, ActivityIndicator } from 'react-native';
// Using React Native's built-in icon solution
import Icon from './components/Icon';

// Import existing screens
import HomeScreen from './screens/HomeScreen';
import TransactionsScreen from './screens/TransactionsScreen';
import ChatScreen from './screens/ChatScreen';
import BankLinkScreen from './screens/BankLinkScreen';
import InsightsNavigator from './navigators/InsightsNavigator';

// Import auth screens
import LoginScreen from './screens/LoginScreen';
import RegisterScreen from './screens/RegisterScreen';

// Import auth context
import { AuthProvider, AuthContext } from './context/AuthContext';

// Import storage service
import { initDatabase } from './services/storage';

// Import API service to set auth context
import { setAuthContext } from './services/api';
import { FirebaseAuthProvider } from './context/FirebaseAuthContext';

const Tab = createBottomTabNavigator();
const Stack = createStackNavigator();

// Auth Stack Navigator (Login/Register)
const AuthStack = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="Login" component={LoginScreen} />
      <Stack.Screen name="Register" component={RegisterScreen} />
    </Stack.Navigator>
  );
};

// App Stack Navigator (Main App)
const AppStack = () => {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused, color, size }) => {
          let iconName;

          if (route.name === 'Home') {
            iconName = focused ? 'home' : 'home-outline';
          } else if (route.name === 'Transactions') {
            iconName = focused ? 'card' : 'card-outline';
          } else if (route.name === 'BankLink') {
            iconName = focused ? 'link' : 'link-outline';
          } else if (route.name === 'Insights') {
            iconName = focused ? 'analytics' : 'analytics-outline';
          } else if (route.name === 'Chat') {
            iconName = focused ? 'chatbubble' : 'chatbubble-outline';
          }

          return <Icon name={iconName} size={size} color={color} />;
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
        headerRight: () => <LogoutButton />,
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
        name="BankLink" 
        component={BankLinkScreen}
        options={{
          tabBarLabel: 'Link Bank',
          headerTitle: 'Bank Linking',
        }}
      />
      <Tab.Screen 
        name="Insights" 
        component={InsightsNavigator}
        options={{
          tabBarLabel: 'Insights',
          headerShown: false,
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
  );
};

// Logout Button Component
const LogoutButton = () => {
  const { signOut } = useContext(AuthContext);

  return (
    <Ionicons 
      name="log-out-outline" 
      size={24} 
      color="#FFFFFF" 
      style={{ marginRight: 15 }}
      onPress={signOut}
    />
  );
};

// Main Navigation Component
const Navigation = () => {
  const { isSignedIn, isLoading } = useContext(AuthContext);

  if (isLoading) {
    return (
      <View style={{ 
        flex: 1, 
        justifyContent: 'center', 
        alignItems: 'center',
        backgroundColor: '#FFFFFF'
      }}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={{ 
          marginTop: 10, 
          fontSize: 16, 
          color: '#666' 
        }}>
          Loading...
        </Text>
      </View>
    );
  }

  return (
    <NavigationContainer>
      {isSignedIn ? <AppStack /> : <AuthStack />}
    </NavigationContainer>
  );
};

// App Component with Auth Context
const AppWithAuth = () => {
  const [isDbReady, setIsDbReady] = useState(false);
  const [dbError, setDbError] = useState(null);
  const authContext = useContext(AuthContext);

  // Set auth context reference for API service
  useEffect(() => {
    if (authContext) {
      setAuthContext(authContext);
    }
  }, [authContext]);

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
      <View style={{ 
        flex: 1, 
        justifyContent: 'center', 
        alignItems: 'center',
        backgroundColor: '#FFFFFF'
      }}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={{ marginTop: 10 }}>Setting up database...</Text>
      </View>
    );
  }

  return (
    <>
      <StatusBar style="auto" />
      <Navigation />
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

// Root App Component
const App = () => {
  const [isDbReady, setIsDbReady] = useState(false);
  const [dbError, setDbError] = useState(null);

  return (
    <AuthProvider>
      <AppWithAuth />
    </AuthProvider>
  );
};

export default App;
