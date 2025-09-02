import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
  Dimensions,
  Alert,
  Platform,
  Share,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  LineChart,
  PieChart,
  BarChart,
  ContributionGraph,
  StackedBarChart
} from 'react-native-chart-kit';
import { getAnalyticsSummary, getTimeSeriesAnalytics, exportTransactionsCSV } from '../services/api';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { clearAllAppData } from '../utils/clearData';

const { width: screenWidth } = Dimensions.get('window');

// Chart configuration
const chartConfig = {
  backgroundColor: '#ffffff',
  backgroundGradientFrom: '#ffffff',
  backgroundGradientTo: '#ffffff',
  decimalPlaces: 0,
  color: (opacity = 1) => `rgba(0, 122, 255, ${opacity})`,
  labelColor: (opacity = 1) => `rgba(0, 0, 0, ${opacity})`,
  style: {
    borderRadius: 16,
  },
  propsForDots: {
    r: '6',
    strokeWidth: '2',
    stroke: '#007AFF',
  },
};

const AnalyticsScreen = () => {
  const [analytics, setAnalytics] = useState(null);
  const [timeSeriesData, setTimeSeriesData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState('30'); // 30 days default

  const periods = [
    { key: '7', label: '7 Days', days: 7 },
    { key: '30', label: '30 Days', days: 30 },
    { key: '90', label: '3 Months', days: 90 },
    { key: '365', label: '1 Year', days: 365 },
  ];

  useEffect(() => {
    loadAnalytics();
    loadTimeSeriesData();
  }, [selectedPeriod]);

  const loadAnalytics = async () => {
    try {
      setLoading(true);

      // Calculate date range
      const toDate = new Date();
      const fromDate = new Date();
      fromDate.setDate(toDate.getDate() - parseInt(selectedPeriod));

      const options = {
        fromDate: fromDate.toISOString().split('T')[0],
        toDate: toDate.toISOString().split('T')[0]
      };

      console.log('📊 Loading analytics with options:', options);
      const data = await getAnalyticsSummary(options);
      setAnalytics(data);
    } catch (error) {
      console.error('Error loading analytics:', error);
      // Don't show alert, just log the error
    } finally {
      setLoading(false);
    }
  };

  const loadTimeSeriesData = async () => {
    try {
      // Load last 6 months for line chart
      const data = await getTimeSeriesAnalytics({ months: 6 });
      setTimeSeriesData(data);
      console.log('📈 Time series data loaded:', data);
    } catch (error) {
      console.error('Error loading time series data:', error);
      // Don't show alert, just log the error
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadAnalytics();
    await loadTimeSeriesData();
    setRefreshing(false);
  };

  const handleExportCSV = async () => {
    try {
      // Calculate date range based on selected period
      const toDate = new Date();
      const fromDate = new Date();
      fromDate.setDate(toDate.getDate() - parseInt(selectedPeriod));

      const options = {
        fromDate: fromDate.toISOString().split('T')[0],
        toDate: toDate.toISOString().split('T')[0],
        format: 'csv'
      };

      console.log('📊 Exporting CSV with options:', options);

      // Show loading state
      Alert.alert(
        'Exporting Data',
        'Preparing your transaction report...',
        [],
        { cancelable: false }
      );

      const exportData = await exportTransactionsCSV(options);

      if (Platform.OS === 'ios') {
        // On iOS, we can use the Share API
        await Share.share({
          message: exportData.content,
          title: 'Transaction Report',
        });
      } else {
        // On Android, save to downloads and share
        const downloadDir = FileSystem.documentDirectory;
        const filePath = `${downloadDir}${exportData.filename}`;

        await FileSystem.writeAsStringAsync(filePath, exportData.content, {
          encoding: FileSystem.EncodingType.UTF8,
        });

        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(filePath, {
            mimeType: exportData.mimeType,
            dialogTitle: 'Share Transaction Report',
          });
        } else {
          Alert.alert(
            'Export Complete',
            `Your transaction report has been saved to ${filePath}`,
            [{ text: 'OK' }]
          );
        }
      }

      Alert.alert(
        'Export Successful',
        'Your transaction report has been exported successfully!',
        [{ text: 'OK' }]
      );

    } catch (error) {
      console.error('Export failed:', error);
      Alert.alert(
        'Export Failed',
        'Failed to export transactions. Please try again.',
        [{ text: 'OK' }]
      );
    }
  };

  const formatCurrency = (amount) => {
    return `₹${amount?.toLocaleString('en-IN', { 
      minimumFractionDigits: 2, 
      maximumFractionDigits: 2 
    }) || '0.00'}`;
  };

  const getCategoryIcon = (category) => {
    const icons = {
      'food': 'restaurant-outline',
      'transport': 'car-outline',
      'shopping': 'bag-outline',
      'entertainment': 'musical-notes-outline',
      'bills': 'receipt-outline',
      'healthcare': 'medical-outline',
      'education': 'school-outline',
      'salary': 'card-outline',
      'investment': 'trending-up-outline',
      'other': 'ellipsis-horizontal-outline'
    };
    return icons[category] || 'ellipsis-horizontal-outline';
  };

  const getCategoryColor = (category) => {
    const colors = {
      'food': '#FF9500',
      'transport': '#32D74B',
      'shopping': '#AF52DE',
      'entertainment': '#FF3B30',
      'bills': '#007AFF',
      'healthcare': '#FF2D92',
      'education': '#5856D6',
      'salary': '#34C759',
      'investment': '#30B0C7',
      'other': '#8E8E93'
    };
    return colors[category] || '#8E8E93';
  };

  const renderSummaryCard = () => {
    if (!analytics) return null;

    const { totalInflow, totalOutflow, balance } = analytics;
    const balanceColor = balance >= 0 ? '#34C759' : '#FF3B30';

    return (
      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Financial Overview</Text>

        <View style={styles.summaryRow}>
          <View style={styles.summaryItem}>
            <View style={[styles.summaryIconContainer, { backgroundColor: '#34C759' }]}>
              <Ionicons name="arrow-down-outline" size={20} color="#fff" />
            </View>
            <Text style={styles.summaryLabel}>Income</Text>
            <Text style={[styles.summaryAmount, { color: '#34C759' }]}>
              {formatCurrency(totalInflow)}
            </Text>
          </View>

          <View style={styles.summaryItem}>
            <View style={[styles.summaryIconContainer, { backgroundColor: '#FF3B30' }]}>
              <Ionicons name="arrow-up-outline" size={20} color="#fff" />
            </View>
            <Text style={styles.summaryLabel}>Expenses</Text>
            <Text style={[styles.summaryAmount, { color: '#FF3B30' }]}>
              {formatCurrency(totalOutflow)}
            </Text>
          </View>
        </View>

        <View style={styles.balanceContainer}>
          <View style={[styles.summaryIconContainer, { backgroundColor: balanceColor }]}>
            <Ionicons name="wallet-outline" size={20} color="#fff" />
          </View>
          <View style={styles.balanceInfo}>
            <Text style={styles.balanceLabel}>Net Balance</Text>
            <Text style={[styles.balanceAmount, { color: balanceColor }]}>
              {formatCurrency(balance)}
            </Text>
          </View>
        </View>

        <Text style={styles.transactionCount}>
          Based on {analytics.totalTransactions} transactions
        </Text>
      </View>
    );
  };

  const renderCategoryCard = (categories, title, type) => {
    if (!categories || categories.length === 0) {
      return (
        <View style={styles.categoryCard}>
          <Text style={styles.categoryTitle}>{title}</Text>
          <View style={styles.emptyState}>
            <Ionicons name="pie-chart-outline" size={48} color="#999" />
            <Text style={styles.emptyStateText}>No {type} data available</Text>
          </View>
        </View>
      );
    }

    // Calculate total for percentages
    const total = categories.reduce((sum, cat) => sum + parseFloat(cat.total_amount), 0);

    return (
      <View style={styles.categoryCard}>
        <Text style={styles.categoryTitle}>{title}</Text>

        {categories.map((category, index) => {
          const amount = parseFloat(category.total_amount);
          const percentage = total > 0 ? (amount / total * 100) : 0;
          const color = getCategoryColor(category.category);

          return (
            <View key={index} style={styles.categoryItem}>
              <View style={styles.categoryHeader}>
                <View style={styles.categoryInfo}>
                  <View style={[styles.categoryIcon, { backgroundColor: color }]}>
                    <Ionicons 
                      name={getCategoryIcon(category.category)} 
                      size={16} 
                      color="#fff" 
                    />
                  </View>
                  <View style={styles.categoryDetails}>
                    <Text style={styles.categoryName}>
                      {category.category.charAt(0).toUpperCase() + category.category.slice(1)}
                    </Text>
                    <Text style={styles.categoryCount}>
                      {category.transaction_count} transactions
                    </Text>
                  </View>
                </View>

                <View style={styles.categoryAmounts}>
                  <Text style={styles.categoryAmount}>
                    {formatCurrency(amount)}
                  </Text>
                  <Text style={styles.categoryPercentage}>
                    {percentage.toFixed(1)}%
                  </Text>
                </View>
              </View>

              {/* Progress bar */}
              <View style={styles.progressContainer}>
                <View 
                  style={[
                    styles.progressBar, 
                    { width: `${percentage}%`, backgroundColor: color }
                  ]} 
                />
              </View>

              <Text style={styles.averageAmount}>
                Avg: {formatCurrency(parseFloat(category.average_amount))}
              </Text>
            </View>
          );
        })}
      </View>
    );
  };

  const renderPieChart = () => {
    if (!analytics || !analytics.expenseCategories || analytics.expenseCategories.length === 0) {
      return (
        <View style={styles.chartCard}>
          <Text style={styles.chartTitle}>Expense Distribution</Text>
          <View style={styles.emptyState}>
            <Ionicons name="pie-chart-outline" size={48} color="#999" />
            <Text style={styles.emptyStateText}>No expense data available</Text>
          </View>
        </View>
      );
    }

    // Prepare data for pie chart - show top 5 categories and group others
    const sortedCategories = [...analytics.expenseCategories]
      .sort((a, b) => parseFloat(b.total_amount) - parseFloat(a.total_amount))
      .slice(0, 5);

    const pieData = sortedCategories.map((category, index) => {
      const colors = ['#FF9500', '#32D74B', '#AF52DE', '#FF3B30', '#007AFF', '#FF2D92'];
      return {
        name: category.category.charAt(0).toUpperCase() + category.category.slice(1),
        population: parseFloat(category.total_amount),
        color: colors[index % colors.length],
        legendFontColor: '#333',
        legendFontSize: 12,
      };
    });

    return (
      <View style={styles.chartCard}>
        <Text style={styles.chartTitle}>Expense Distribution</Text>
        <View style={styles.chartContainer}>
          <PieChart
            data={pieData}
            width={screenWidth - 60}
            height={220}
            chartConfig={chartConfig}
            accessor="population"
            backgroundColor="transparent"
            paddingLeft="15"
            center={[10, 10]}
            absolute
          />
        </View>
      </View>
    );
  };

  const renderLineChart = () => {
    if (!timeSeriesData || !timeSeriesData.monthly_data || timeSeriesData.monthly_data.length === 0) {
      return (
        <View style={styles.chartCard}>
          <Text style={styles.chartTitle}>Monthly Expense Trends</Text>
          <View style={styles.emptyState}>
            <Ionicons name="trending-up-outline" size={48} color="#999" />
            <Text style={styles.emptyStateText}>No trend data available</Text>
          </View>
        </View>
      );
    }

    // Prepare data for line chart - reverse to show chronological order
    const monthlyData = [...timeSeriesData.monthly_data].reverse();

    const labels = monthlyData.map(item => {
      const date = new Date(item.month + '-01');
      return date.toLocaleDateString('en-US', { month: 'short' });
    });

    const expenseData = monthlyData.map(item => parseFloat(item.total_outflow) / 1000); // Convert to thousands
    const incomeData = monthlyData.map(item => parseFloat(item.total_inflow) / 1000); // Convert to thousands

    const data = {
      labels: labels,
      datasets: [
        {
          data: expenseData,
          color: (opacity = 1) => `rgba(255, 59, 48, ${opacity})`, // Red for expenses
          strokeWidth: 3,
        },
        {
          data: incomeData,
          color: (opacity = 1) => `rgba(52, 199, 89, ${opacity})`, // Green for income
          strokeWidth: 3,
        },
      ],
    };

    return (
      <View style={styles.chartCard}>
        <Text style={styles.chartTitle}>Monthly Trends (₹'000)</Text>
        <View style={styles.legendContainer}>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: '#FF3B30' }]} />
            <Text style={styles.legendText}>Expenses</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: '#34C759' }]} />
            <Text style={styles.legendText}>Income</Text>
          </View>
        </View>
        <View style={styles.chartContainer}>
          <LineChart
            data={data}
            width={screenWidth - 60}
            height={220}
            chartConfig={{
              ...chartConfig,
              color: (opacity = 1) => `rgba(0, 122, 255, ${opacity})`,
            }}
            bezier
            style={{
              marginVertical: 8,
              borderRadius: 16,
            }}
            withHorizontalLabels={true}
            withVerticalLabels={true}
            withDots={true}
            withShadow={false}
            withScrollableDot={false}
          />
        </View>
      </View>
    );
  };

  const renderPeriodSelector = () => (
    <View style={styles.periodSelector}>
      <View style={styles.periodHeader}>
        <Text style={styles.periodTitle}>Time Period</Text>
        <TouchableOpacity
          style={styles.exportButton}
          onPress={handleExportCSV}
        >
          <Ionicons name="download-outline" size={16} color="#007AFF" />
          <Text style={styles.exportButtonText}>Export</Text>
        </TouchableOpacity>
      </View>
      <View style={styles.periodButtons}>
        {periods.map((period) => (
          <TouchableOpacity
            key={period.key}
            style={[
              styles.periodButton,
              selectedPeriod === period.key && styles.periodButtonActive
            ]}
            onPress={() => setSelectedPeriod(period.key)}
          >
            <Text style={[
              styles.periodButtonText,
              selectedPeriod === period.key && styles.periodButtonTextActive
            ]}>
              {period.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading analytics...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Period Selector */}
      {renderPeriodSelector()}

      {/* Summary Card */}
      {renderSummaryCard()}

      {/* Charts */}
      {renderPieChart()}
      {renderLineChart()}

      {/* Expense Categories */}
      {analytics && renderCategoryCard(
        analytics.expenseCategories, 
        'Expense Breakdown', 
        'expense'
      )}

      {/* Income Categories */}
      {analytics && renderCategoryCard(
        analytics.incomeCategories, 
        'Income Sources', 
        'income'
      )}        {/* Debug Clear Button (Dev Only) */}
        {renderClearDataButton()}


    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
  },
  loadingText: {
    marginTop: 10,
    color: '#666',
    fontSize: 16,
  },
  periodSelector: {
    backgroundColor: '#fff',
    margin: 20,
    marginTop: 10,
    padding: 16,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  periodTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
  },
  periodButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  periodButton: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginHorizontal: 2,
    borderRadius: 8,
    backgroundColor: '#f0f0f0',
  },
  periodButtonActive: {
    backgroundColor: '#007AFF',
  },
  periodButtonText: {
    fontSize: 12,
    fontWeight: '500',
    color: '#666',
    textAlign: 'center',
  },
  periodButtonTextActive: {
    color: '#fff',
  },
  summaryCard: {
    backgroundColor: '#fff',
    margin: 20,
    marginTop: 0,
    padding: 20,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  summaryTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  summaryItem: {
    flex: 1,
    alignItems: 'center',
  },
  summaryIconContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  summaryLabel: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  summaryAmount: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  balanceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#f0f0f0',
  },
  balanceInfo: {
    marginLeft: 12,
    flex: 1,
  },
  balanceLabel: {
    fontSize: 16,
    color: '#666',
    marginBottom: 4,
  },
  balanceAmount: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  transactionCount: {
    fontSize: 12,
    color: '#999',
    textAlign: 'center',
    marginTop: 12,
  },
  categoryCard: {
    backgroundColor: '#fff',
    margin: 20,
    marginTop: 0,
    padding: 20,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  categoryTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 16,
  },
  categoryItem: {
    marginBottom: 16,
  },
  categoryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  categoryInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  categoryIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  categoryDetails: {
    flex: 1,
  },
  categoryName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  categoryCount: {
    fontSize: 12,
    color: '#666',
  },
  categoryAmounts: {
    alignItems: 'flex-end',
  },
  categoryAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  categoryPercentage: {
    fontSize: 12,
    color: '#666',
  },
  progressContainer: {
    height: 4,
    backgroundColor: '#f0f0f0',
    borderRadius: 2,
    marginBottom: 4,
  },
  progressBar: {
    height: 4,
    borderRadius: 2,
  },
  averageAmount: {
    fontSize: 12,
    color: '#666',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyStateText: {
    marginTop: 10,
    color: '#999',
    fontSize: 14,
  },
  chartCard: {
    backgroundColor: '#fff',
    margin: 20,
    marginTop: 0,
    padding: 20,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  chartTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 16,
    textAlign: 'center',
  },
  chartContainer: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  legendContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: 10,
    paddingHorizontal: 20,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 15,
  },
  legendDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 6,
  },
  legendText: {
    fontSize: 12,
    color: '#666',
    fontWeight: '500',
  },
  periodHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  exportButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#007AFF',
    backgroundColor: 'transparent',
  },
  exportButtonText: {
    fontSize: 12,
    color: '#007AFF',
    fontWeight: '500',
    marginLeft: 4,
  },
});  // Debug: Clear all data button (only show in development)
  const renderClearDataButton = () => {
    if (!__DEV__) return null;
    
    return (
      <View style={styles.chartCard}>
        <Text style={styles.cardTitle}>🛠️ Debug Tools</Text>
        <TouchableOpacity
          style={[styles.clearButton, { backgroundColor: '#FF3B30' }]}
          onPress={clearAllAppData}
        >
          <Text style={styles.clearButtonText}>🧹 Clear All App Data</Text>
        </TouchableOpacity>
        <Text style={styles.debugText}>
          Use this to clear all local data and start fresh with clean analytics.
        </Text>
      </View>
    );
  };



export default AnalyticsScreen;