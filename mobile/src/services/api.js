// Configuration - Change this to your computer's IP address when testing on device
// For development: use 'localhost' when testing in simulator/web
// For device testing: use your computer's IP address (e.g., '192.168.1.246')
const API_HOST = 'localhost'; // Change to your IP address for device testing
const API_PORT = '8000';
const BASE_URL = `http://${API_HOST}:${API_PORT}`;

// Sync transactions with the server
const syncTransactions = async () => {
  try {
    const response = await fetch(`${BASE_URL}/transactions/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        // Add any sync parameters here
        last_sync: new Date().toISOString(),
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error syncing transactions:', error);
    throw error;
  }
};

// Get transactions from server
const getTransactions = async () => {
  try {
    const response = await fetch(`${BASE_URL}/transactions`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching transactions:', error);
    throw error;
  }
};

// Ask a question to the QA endpoint
const askQuestion = async (question) => {
  try {
    const response = await fetch(`${BASE_URL}/qa`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question: question,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error asking question:', error);
    throw error;
  }
};

export { syncTransactions, getTransactions, askQuestion };
