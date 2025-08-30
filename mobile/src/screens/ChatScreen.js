import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { askQuestion, testConnection, diagnosticNetworkTest } from '../services/api';

// Helper function to format time
const formatTime = () => {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const MessageBubble = ({ message, isUser }) => {
  return (
    <View style={[
      styles.messageBubble,
      isUser ? styles.userMessage : styles.botMessage
    ]}>
      <Text style={[
        styles.messageText,
        isUser ? styles.userMessageText : styles.botMessageText
      ]}>
        {message.text}
      </Text>
      <Text style={[
        styles.messageTime,
        isUser ? styles.userMessageTime : styles.botMessageTime
      ]}>
        {message.timestamp}
      </Text>
    </View>
  );
};

const ChatScreen = () => {
  const [messages, setMessages] = useState([
    {
      id: '1',
      text: 'Hi! I can help you analyze your spending patterns. Try asking "How much did I spend on food?" or "What\'s my total spending?"',
      isUser: false,
      timestamp: formatTime(),
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);

  // Enhanced send message function with better error handling
  const sendMessage = async () => {
    if (!inputText.trim() || loading) return;

    const userMessage = {
      id: Date.now().toString(),
      text: inputText.trim(),
      isUser: true,
      timestamp: formatTime(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setLoading(true);

    try {
      console.log('🚀 Sending question to API...');
      const response = await askQuestion(inputText.trim());
      console.log('✅ Got response:', response);

      const botMessage = {
        id: (Date.now() + 1).toString(),
        text: response.answer || response.message || 'I received your question but couldn\'t generate a response.',
        isUser: false,
        timestamp: formatTime(),
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error('❌ Error sending message:', error);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        text: `Sorry, I encountered an error: ${error.message}. Please check your connection and try again.`,
        isUser: false,
        timestamp: formatTime(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  // Enhanced test connection function with diagnostics
  const handleTestConnection = async () => {
    const testMessage = {
      id: Date.now().toString(),
      text: '🔍 Running network diagnostics...',
      isUser: false,
      timestamp: formatTime(),
    };
    setMessages(prev => [...prev, testMessage]);

    try {
      const results = await diagnosticNetworkTest();

      let resultText = '📊 Network Diagnostic Results:\n';
      results.forEach(result => {
        const icon = result.success ? '✅' : '❌';
        resultText += `${icon} ${result.test}: ${result.details}\n`;
      });

      const resultMessage = {
        id: (Date.now() + 1).toString(),
        text: resultText.trim(),
        isUser: false,
        timestamp: formatTime(),
      };
      setMessages(prev => [...prev, resultMessage]);

    } catch (error) {
      const errorMessage = {
        id: (Date.now() + 2).toString(),
        text: `❌ Connection test error: ${error.message}`,
        isUser: false,
        timestamp: formatTime(),
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  // Simple connection test function (for quick testing)
  const handleQuickTest = async () => {
    try {
      const isConnected = await testConnection();
      const resultMessage = {
        id: Date.now().toString(),
        text: isConnected ? '✅ Quick test: Server is reachable!' : '❌ Quick test: Server not reachable.',
        isUser: false,
        timestamp: formatTime(),
      };
      setMessages(prev => [...prev, resultMessage]);
    } catch (error) {
      console.error('Quick test failed:', error);
    }
  };

  const renderMessage = ({ item }) => (
    <MessageBubble message={item} isUser={item.isUser} />
  );

  return (
    <KeyboardAvoidingView 
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Financial Assistant</Text>
        <TouchableOpacity 
          style={styles.testButton}
          onPress={handleTestConnection}
        >
          <Text style={styles.testButtonText}>Diagnostics</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.testButton, { marginLeft: 8 }]}
          onPress={handleQuickTest}
        >
          <Text style={styles.testButtonText}>Quick Test</Text>
        </TouchableOpacity>
      </View>
      <FlatList
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id}
        style={styles.messagesList}
        contentContainerStyle={styles.messagesContainer}
      />

      {loading && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color="#007AFF" />
          <Text style={styles.loadingText}>Analyzing your finances...</Text>
        </View>
      )}

      <View style={styles.inputContainer}>
        <TextInput
          style={styles.textInput}
          value={inputText}
          onChangeText={setInputText}
          placeholder="Ask me about your expenses..."
          multiline
          maxLength={500}
          editable={!loading}
        />
        <TouchableOpacity
          style={[styles.sendButton, (!inputText.trim() || loading) && styles.sendButtonDisabled]}
          onPress={sendMessage}
          disabled={!inputText.trim() || loading}
        >
          <Text style={[
            styles.sendButtonText,
            (!inputText.trim() || loading) && styles.sendButtonTextDisabled
          ]}>
            Send
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#007AFF',
    paddingTop: Platform.OS === 'ios' ? 50 : 30,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
  },
  testButton: {
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  testButtonText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  messagesList: {
    flex: 1,
  },
  messagesContainer: {
    padding: 15,
  },
  messageBubble: {
    maxWidth: '80%',
    marginVertical: 5,
    padding: 12,
    borderRadius: 18,
  },
  userMessage: {
    alignSelf: 'flex-end',
    backgroundColor: '#007AFF',
  },
  botMessage: {
    alignSelf: 'flex-start',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E0E0E0',
  },
  messageText: {
    fontSize: 16,
    lineHeight: 20,
  },
  userMessageText: {
    color: '#FFFFFF',
  },
  botMessageText: {
    color: '#333',
  },
  messageTime: {
    fontSize: 12,
    marginTop: 4,
  },
  userMessageTime: {
    color: 'rgba(255, 255, 255, 0.7)',
    textAlign: 'right',
  },
  botMessageTime: {
    color: '#999',
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
  },
  loadingText: {
    marginLeft: 8,
    color: '#666',
    fontStyle: 'italic',
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 15,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
    alignItems: 'flex-end',
  },
  textInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#E0E0E0',
    borderRadius: 20,
    paddingHorizontal: 15,
    paddingVertical: 10,
    marginRight: 10,
    maxHeight: 100,
    fontSize: 16,
  },
  sendButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
  },
  sendButtonDisabled: {
    backgroundColor: '#CCCCCC',
  },
  sendButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 16,
  },
  sendButtonTextDisabled: {
    color: '#999999',
  },
});

export default ChatScreen;