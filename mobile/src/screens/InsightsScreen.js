import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { askAdvancedInsights, detectAnomalies } from '../services/api';

const InsightsScreen = () => {
  const [insights, setInsights] = useState([]);
  const [anomalies, setAnomalies] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Predefined insight queries for quick access
  const quickInsights = [
    {
      id: 1,
      title: 'Monthly Spending',
      question: 'How much did I spend this month?',
      icon: 'card-outline',
      color: '#007AFF'
    },
    {
      id: 2,
      title: 'Food Expenses',
      question: 'How much did I spend on food?',
      icon: 'restaurant-outline',
      color: '#FF9500'
    },
    {
      id: 3,
      title: 'Transport Costs',
      question: 'What are my transport expenses?',
      icon: 'car-outline',
      color: '#32D74B'
    },
    {
      id: 4,
      title: 'Top Categories',
      question: 'What are my top spending categories?',
      icon: 'pie-chart-outline',
      color: '#AF52DE'
    },
    {
      id: 5,
      title: 'Recent Large Expenses',
      question: 'Show me transactions over ₹1000 in the last week',
      icon: 'trending-up-outline',
      color: '#FF3B30'
    },
    {
      id: 6,
      title: 'Merchant Analysis',
      question: 'Which merchants do I spend the most at?',
      icon: 'storefront-outline',
      color: '#00C7BE'
    }
  ];

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    await Promise.all([
      loadQuickInsight('How much did I spend this month?'),
      loadAnomalies()
    ]);
  };

  const loadQuickInsight = async (question) => {
    try {
      setLoading(true);
      const response = await askAdvancedInsights(question);

      const newInsight = {
        id: Date.now(),
        question,
        answer: response.answer,
        confidence: response.confidence,
        timestamp: new Date(),
        supporting_transactions: response.supporting_transactions?.slice(0, 3) || [],
        execution_time: response.execution_time_ms
      };

      setInsights(prev => [newInsight, ...prev.slice(0, 4)]); // Keep last 5 insights
    } catch (error) {
      console.error('Error loading insight:', error);
      Alert.alert('Error', `Failed to load insight: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadAnomalies = async () => {
    try {
      const response = await detectAnomalies({
        timeRangeDays: 30,
        sensitivity: 0.1,
        minAmountThreshold: 500
      });
      setAnomalies(response);
    } catch (error) {
      console.error('Error loading anomalies:', error);
      // Don't show alert for anomalies as it's not critical
    }
  };

  const handleQuickInsight = async (question) => {
    await loadQuickInsight(question);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadInitialData();
    setRefreshing(false);
  };

  const formatCurrency = (amount) => {
    return `₹${amount?.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}`;
  };

  const formatTime = (date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return '#32D74B';
    if (confidence >= 0.6) return '#FF9500';
    return '#FF3B30';
  };

  const renderInsightCard = (insight) => (
    <View key={insight.id} style={styles.insightCard}>
      <View style={styles.insightHeader}>
        <Text style={styles.insightQuestion}>{insight.question}</Text>
        <View style={styles.confidenceContainer}>
          <View style={[
            styles.confidenceDot, 
            { backgroundColor: getConfidenceColor(insight.confidence) }
          ]} />
          <Text style={styles.confidenceText}>
            {Math.round(insight.confidence * 100)}%
          </Text>
        </View>
      </View>

      <Text style={styles.insightAnswer}>{insight.answer}</Text>

      {insight.supporting_transactions?.length > 0 && (
        <View style={styles.supportingTransactions}>
          <Text style={styles.supportingTitle}>Recent Transactions:</Text>
          {insight.supporting_transactions.map((tx, index) => (
            <View key={index} style={styles.transactionItem}>
              <Text style={styles.transactionMerchant}>
                {tx.merchant || 'Unknown Merchant'}
              </Text>
              <Text style={styles.transactionAmount}>
                {formatCurrency(tx.amount)}
              </Text>
            </View>
          ))}
        </View>
      )}

      <Text style={styles.insightTime}>
        {formatTime(insight.timestamp)} • {insight.execution_time?.toFixed(0)}ms
      </Text>
    </View>
  );

  const renderAnomalyCard = () => {
    if (!anomalies || anomalies.anomalies_detected === 0) return null;

    return (
      <View style={styles.anomalyCard}>
        <View style={styles.anomalyHeader}>
          <Ionicons name="warning-outline" size={24} color="#FF3B30" />
          <Text style={styles.anomalyTitle}>Spending Anomalies Detected</Text>
        </View>

        <Text style={styles.anomalyStats}>
          {anomalies.anomalies_detected} unusual transaction{anomalies.anomalies_detected !== 1 ? 's' : ''} 
          out of {anomalies.total_transactions_analyzed} analyzed 
          ({anomalies.anomaly_rate?.toFixed(1)}%)
        </Text>

        {anomalies.anomalies?.slice(0, 2).map((anomaly, index) => (
          <View key={index} style={styles.anomalyItem}>
            <View style={styles.anomalyDetails}>
              <Text style={styles.anomalyAmount}>
                {formatCurrency(anomaly.transaction_details.amount)}
              </Text>
              <Text style={styles.anomalyMerchant}>
                {anomaly.transaction_details.merchant || 'Unknown Merchant'}
              </Text>
            </View>
            <Text style={styles.anomalyReason}>
              {anomaly.anomaly_reasons[0]}
            </Text>
          </View>
        ))}

        <TouchableOpacity 
          style={styles.viewAllButton}
          onPress={() => Alert.alert('Anomalies', 'Full anomaly details coming soon!')}
        >
          <Text style={styles.viewAllText}>View All Anomalies</Text>
        </TouchableOpacity>
      </View>
    );
  };

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Financial Insights</Text>
        <Text style={styles.headerSubtitle}>AI-powered spending analysis</Text>
      </View>

      {/* Anomalies Section */}
      {renderAnomalyCard()}

      {/* Quick Insights */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Quick Insights</Text>
        <View style={styles.quickInsightsGrid}>
          {quickInsights.map((item) => (
            <TouchableOpacity
              key={item.id}
              style={[styles.quickInsightCard, { borderLeftColor: item.color }]}
              onPress={() => handleQuickInsight(item.question)}
              disabled={loading}
            >
              <Ionicons name={item.icon} size={20} color={item.color} />
              <Text style={styles.quickInsightTitle}>{item.title}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Recent Insights */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Recent Analysis</Text>
        {loading && insights.length === 0 ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#007AFF" />
            <Text style={styles.loadingText}>Analyzing your spending...</Text>
          </View>
        ) : insights.length > 0 ? (
          insights.map(renderInsightCard)
        ) : (
          <View style={styles.emptyState}>
            <Ionicons name="analytics-outline" size={48} color="#999" />
            <Text style={styles.emptyStateText}>
              Tap on quick insights above to get started
            </Text>
          </View>
        )}
      </View>
    </ScrollView>
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
  section: {
    padding: 20,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#333',
    marginBottom: 15,
  },
  quickInsightsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  quickInsightCard: {
    width: '48%',
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 12,
    marginBottom: 10,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  quickInsightTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginTop: 8,
  },
  insightCard: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 12,
    marginBottom: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  insightHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  insightQuestion: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    flex: 1,
    marginRight: 10,
  },
  confidenceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  confidenceDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 4,
  },
  confidenceText: {
    fontSize: 12,
    color: '#666',
  },
  insightAnswer: {
    fontSize: 15,
    color: '#444',
    lineHeight: 22,
    marginBottom: 10,
  },
  supportingTransactions: {
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#f0f0f0',
  },
  supportingTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#666',
    marginBottom: 8,
  },
  transactionItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  transactionMerchant: {
    fontSize: 13,
    color: '#666',
    flex: 1,
  },
  transactionAmount: {
    fontSize: 13,
    fontWeight: '600',
    color: '#333',
  },
  insightTime: {
    fontSize: 12,
    color: '#999',
    marginTop: 8,
  },
  anomalyCard: {
    backgroundColor: '#fff',
    margin: 20,
    padding: 16,
    borderRadius: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#FF3B30',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  anomalyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  anomalyTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FF3B30',
    marginLeft: 8,
  },
  anomalyStats: {
    fontSize: 14,
    color: '#666',
    marginBottom: 15,
  },
  anomalyItem: {
    backgroundColor: '#f8f8f8',
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
  },
  anomalyDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  anomalyAmount: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FF3B30',
  },
  anomalyMerchant: {
    fontSize: 14,
    color: '#333',
  },
  anomalyReason: {
    fontSize: 12,
    color: '#666',
    fontStyle: 'italic',
  },
  viewAllButton: {
    alignSelf: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#FF3B30',
    borderRadius: 16,
    marginTop: 10,
  },
  viewAllText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  loadingContainer: {
    alignItems: 'center',
    padding: 40,
  },
  loadingText: {
    marginTop: 10,
    color: '#666',
    fontStyle: 'italic',
  },
  emptyState: {
    alignItems: 'center',
    padding: 40,
  },
  emptyStateText: {
    marginTop: 10,
    color: '#999',
    textAlign: 'center',
  },
});

export default InsightsScreen;