import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import networkService from '../services/network';

const NetworkDiagnosticsScreen = ({ navigation }) => {
  const [diagnostics, setDiagnostics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastRun, setLastRun] = useState(null);

  useEffect(() => {
    // Run diagnostics on screen load
    runDiagnostics();
  }, []);

  const runDiagnostics = async () => {
    setLoading(true);
    try {
      console.log('🔍 Starting network diagnostics...');
      const results = await networkService.runDiagnostics();
      setDiagnostics(results);
      setLastRun(new Date());
      console.log('✅ Diagnostics completed');
    } catch (error) {
      console.error('❌ Diagnostics failed:', error);
      Alert.alert('Error', `Diagnostics failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const clearNetworkCache = () => {
    networkService.clearCache();
    Alert.alert('Cache Cleared', 'Network cache has been cleared. Try connecting again.');
  };

  const renderNetworkStatus = () => {
    if (!diagnostics?.networkState) return null;

    const { networkState } = diagnostics;
    const isConnected = networkState.isConnected;
    const isInternetReachable = networkState.isInternetReachable;

    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Network Status</Text>

        <View style={styles.statusRow}>
          <Ionicons 
            name={isConnected ? "wifi" : "wifi-outline"} 
            size={20} 
            color={isConnected ? "#4CAF50" : "#FF5722"} 
          />
          <Text style={[styles.statusText, { color: isConnected ? "#4CAF50" : "#FF5722" }]}>
            {isConnected ? "Connected" : "Disconnected"}
          </Text>
        </View>

        <View style={styles.statusRow}>
          <Ionicons 
            name={isInternetReachable ? "globe" : "globe-outline"} 
            size={20} 
            color={isInternetReachable ? "#4CAF50" : "#FF5722"} 
          />
          <Text style={[styles.statusText, { color: isInternetReachable ? "#4CAF50" : "#FF5722" }]}>
            Internet {isInternetReachable ? "Reachable" : "Unreachable"}
          </Text>
        </View>

        <View style={styles.statusRow}>
          <Ionicons name="phone-portrait-outline" size={20} color="#666" />
          <Text style={styles.statusText}>
            Network Type: {networkState.type || 'Unknown'}
          </Text>
        </View>
      </View>
    );
  };

  const renderHostTests = () => {
    if (!diagnostics?.hostTests) return null;

    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Server Connectivity</Text>

        {diagnostics.hostTests.map((test, index) => (
          <View key={index} style={styles.hostTestRow}>
            <Ionicons 
              name={test.reachable ? "checkmark-circle" : "close-circle"} 
              size={20} 
              color={test.reachable ? "#4CAF50" : "#FF5722"} 
            />
            <Text style={styles.hostText}>{test.host}</Text>
            <Text style={[
              styles.statusBadge, 
              { backgroundColor: test.reachable ? "#E8F5E8" : "#FFEBEE" }
            ]}>
              {test.reachable ? "Reachable" : "Unreachable"}
            </Text>
          </View>
        ))}
      </View>
    );
  };

  const renderRecommendations = () => {
    if (!diagnostics?.recommendations?.length) return null;

    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Recommendations</Text>

        {diagnostics.recommendations.map((recommendation, index) => (
          <View key={index} style={styles.recommendationRow}>
            <Ionicons name="bulb-outline" size={20} color="#FF9800" />
            <Text style={styles.recommendationText}>{recommendation}</Text>
          </View>
        ))}

        {/* Additional troubleshooting tips */}
        <View style={styles.troubleshootingSection}>
          <Text style={styles.troubleshootingTitle}>Troubleshooting Tips:</Text>

          <View style={styles.tipRow}>
            <Text style={styles.tipNumber}>1.</Text>
            <Text style={styles.tipText}>Make sure your server is running on port 8000</Text>
          </View>

          <View style={styles.tipRow}>
            <Text style={styles.tipNumber}>2.</Text>
            <Text style={styles.tipText}>Check that your phone and computer are on the same WiFi network</Text>
          </View>

          <View style={styles.tipRow}>
            <Text style={styles.tipNumber}>3.</Text>
            <Text style={styles.tipText}>Verify your computer's firewall allows connections on port 8000</Text>
          </View>

          <View style={styles.tipRow}>
            <Text style={styles.tipNumber}>4.</Text>
            <Text style={styles.tipText}>Try restarting the server: cd server && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000</Text>
          </View>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Network Diagnostics</Text>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#007AFF" />
            <Text style={styles.loadingText}>Running diagnostics...</Text>
          </View>
        ) : (
          <>
            {lastRun && (
              <Text style={styles.lastRunText}>
                Last run: {lastRun.toLocaleTimeString()}
              </Text>
            )}

            {renderNetworkStatus()}
            {renderHostTests()}
            {renderRecommendations()}
          </>
        )}
      </ScrollView>

      <View style={styles.buttonContainer}>
        <TouchableOpacity 
          style={[styles.button, styles.secondaryButton]} 
          onPress={clearNetworkCache}
          disabled={loading}
        >
          <Ionicons name="refresh" size={20} color="#666" />
          <Text style={styles.secondaryButtonText}>Clear Cache</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={[styles.button, styles.primaryButton]} 
          onPress={runDiagnostics}
          disabled={loading}
        >
          <Ionicons name="analytics" size={20} color="#FFFFFF" />
          <Text style={styles.primaryButtonText}>Run Diagnostics</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8F9FA',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 60,
    paddingBottom: 20,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  backButton: {
    marginRight: 15,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  content: {
    flex: 1,
    paddingHorizontal: 20,
  },
  lastRunText: {
    textAlign: 'center',
    color: '#666',
    marginVertical: 10,
    fontSize: 14,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 50,
  },
  loadingText: {
    marginTop: 15,
    fontSize: 16,
    color: '#666',
  },
  section: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 20,
    marginVertical: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 15,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  statusText: {
    marginLeft: 10,
    fontSize: 16,
    fontWeight: '500',
  },
  hostTestRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F0F0F0',
  },
  hostText: {
    flex: 1,
    marginLeft: 10,
    fontSize: 16,
    fontFamily: 'monospace',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    fontSize: 12,
    fontWeight: '500',
  },
  recommendationRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  recommendationText: {
    flex: 1,
    marginLeft: 10,
    fontSize: 14,
    color: '#333',
    lineHeight: 20,
  },
  troubleshootingSection: {
    marginTop: 20,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  troubleshootingTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 10,
  },
  tipRow: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  tipNumber: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#007AFF',
    width: 20,
  },
  tipText: {
    flex: 1,
    fontSize: 14,
    color: '#666',
    lineHeight: 18,
  },
  buttonContainer: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    paddingVertical: 20,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  button: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 8,
    marginHorizontal: 5,
  },
  primaryButton: {
    backgroundColor: '#007AFF',
  },
  secondaryButton: {
    backgroundColor: '#F0F0F0',
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 5,
  },
  secondaryButtonText: {
    color: '#666',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 5,
  },
});

export default NetworkDiagnosticsScreen;