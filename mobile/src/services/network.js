import { Platform } from 'react-native';
import * as Network from 'expo-network';

/**
 * Network utility service for handling connectivity and server discovery
 */
class NetworkService {
  constructor() {
    this.currentHost = null;
    this.lastSuccessfulHost = null;
    this.hostCandidates = [
      '192.168.1.246',  // Current configured IP
      '192.168.1.100',  // Common router IP range
      '192.168.0.100',  // Alternative router IP range
      'localhost',       // For simulator
      '127.0.0.1',      // Localhost IP
      '10.0.2.2',       // Android emulator host
    ];
  }

  /**
   * Get the best available API host
   */
  async getApiHost() {
    // Return cached successful host if available
    if (this.lastSuccessfulHost) {
      console.log(`🔄 Using cached host: ${this.lastSuccessfulHost}`);
      return this.lastSuccessfulHost;
    }

    // Try to discover working host
    const discoveredHost = await this.discoverHost();
    if (discoveredHost) {
      this.lastSuccessfulHost = discoveredHost;
      return discoveredHost;
    }

    // Fallback to default
    console.warn('⚠️ No working host found, using default');
    return '192.168.1.246';
  }

  /**
   * Discover working server host by testing connectivity
   */
  async discoverHost() {
    console.log('🔍 Discovering server host...');

    // Check network connectivity first
    const networkState = await this.getNetworkState();
    if (!networkState.isConnected) {
      console.error('❌ No network connectivity');
      return null;
    }

    // Test each host candidate
    for (const host of this.hostCandidates) {
      console.log(`🧪 Testing host: ${host}`);

      if (await this.testHost(host)) {
        console.log(`✅ Found working host: ${host}`);
        return host;
      }
    }

    console.error('❌ No working host found');
    return null;
  }

  /**
   * Test if a specific host is reachable
   */
  async testHost(host, port = 8000, timeout = 5000) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const url = `http://${host}:${port}/health`;
      console.log(`📡 Testing: ${url}`);

      const response = await fetch(url, {
        method: 'GET',
        signal: controller.signal,
        headers: {
          'Cache-Control': 'no-cache',
        },
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        console.log(`✅ ${host} is reachable (${response.status})`);
        return true;
      } else {
        console.log(`❌ ${host} returned ${response.status}`);
        return false;
      }
    } catch (error) {
      console.log(`❌ ${host} failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Get network state information
   */
  async getNetworkState() {
    try {
      const networkState = await Network.getNetworkStateAsync();
      console.log('🌐 Network state:', {
        type: networkState.type,
        isConnected: networkState.isConnected,
        isInternetReachable: networkState.isInternetReachable,
      });
      return networkState;
    } catch (error) {
      console.error('Failed to get network state:', error);
      return { isConnected: false, isInternetReachable: false };
    }
  }

  /**
   * Enhanced fetch with improved timeout and retry logic
   */
  async fetchWithRetry(url, options = {}, maxRetries = 3) {
    let lastError = null;
    const baseTimeout = options.timeout || 15000; // 15 seconds default

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.log(`🔄 Attempt ${attempt}/${maxRetries}: ${url}`);

        // Increase timeout with each retry
        const timeout = baseTimeout * attempt;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
          controller.abort();
        }, timeout);

        const response = await fetch(url, {
          ...options,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.ok) {
          console.log(`✅ Request successful on attempt ${attempt}`);
          return response;
        } else {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
      } catch (error) {
        console.log(`❌ Attempt ${attempt} failed: ${error.message}`);
        lastError = error;

        if (error.name === 'AbortError') {
          lastError = new Error(`Request timeout after ${baseTimeout * attempt}ms`);
        }

        // Don't retry on authentication errors
        if (error.message.includes('401') || error.message.includes('403')) {
          break;
        }

        // Wait before retrying (exponential backoff)
        if (attempt < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
          console.log(`⏳ Waiting ${delay}ms before retry...`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    throw lastError || new Error('All retry attempts failed');
  }

  /**
   * Comprehensive network diagnostics
   */
  async runDiagnostics() {
    console.log('🔍 Running network diagnostics...');

    const results = {
      timestamp: new Date().toISOString(),
      platform: Platform.OS,
      networkState: await this.getNetworkState(),
      hostTests: [],
      recommendations: [],
    };

    // Test all host candidates
    for (const host of this.hostCandidates) {
      const isReachable = await this.testHost(host);
      results.hostTests.push({ host, reachable: isReachable });
    }

    // Generate recommendations
    const reachableHosts = results.hostTests.filter(t => t.reachable);
    if (reachableHosts.length === 0) {
      results.recommendations.push('No servers are reachable. Check if the server is running.');
    } else {
      results.recommendations.push(`Found ${reachableHosts.length} reachable server(s)`);
    }

    console.log('📊 Diagnostics complete:', results);
    return results;
  }

  /**
   * Clear cached host information
   */
  clearCache() {
    this.lastSuccessfulHost = null;
    console.log('🗑️ Network cache cleared');
  }
}

// Export singleton instance
export const networkService = new NetworkService();
export default networkService;