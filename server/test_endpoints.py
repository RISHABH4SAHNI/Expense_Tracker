"""
Test script for transaction endpoints
Tests bulk sync, webhook, and job processing
"""
import asyncio
import httpx
import json
from datetime import datetime, timezone
from decimal import Decimal

BASE_URL = "http://127.0.0.1:8000"

# Sample transaction data
sample_transactions = [
    {
        "id": "txn_test_001",
        "ts": "2024-01-15T10:30:00+05:30",
        "amount": 250.50,
        "type": "debit", 
        "raw_desc": "SWIGGY*DELIVERY ORDER #12345",
        "account_id": "acc_12345"
    },
    {
        "id": "txn_test_002", 
        "ts": "2024-01-14T15:45:00+05:30",
        "amount": 1200.00,
        "type": "debit",
        "raw_desc": "BIG BAZAAR MUMBAI PURCHASE",
        "account_id": "acc_12345"
    },
    {
        "id": "txn_test_003",
        "ts": "2024-01-13T09:15:00+05:30", 
        "amount": 50000.00,
        "type": "credit",
        "raw_desc": "SALARY CREDIT - COMPANY XYZ",
        "account_id": "acc_67890"
    }
]

async def test_bulk_sync():
    """Test bulk transaction sync endpoint"""
    print("🧪 Testing bulk sync endpoint...")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/transactions/sync",
            json=sample_transactions,
            timeout=30.0
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print("")

async def test_webhook():
    """Test webhook endpoint"""
    print("🧪 Testing webhook endpoint...")

    webhook_transaction = {
        "id": "txn_webhook_001",
        "ts": "2024-01-16T12:00:00+05:30",
        "amount": 75.00,
        "type": "debit",
        "raw_desc": "UBER RIDE #ABC123",
        "account_id": "acc_12345"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/transactions/webhook",
            json=webhook_transaction,
            timeout=30.0
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print("")

async def test_job_stats():
    """Test job monitoring endpoints"""
    print("🧪 Testing job stats endpoint...")

    async with httpx.AsyncClient() as client:
        # Get job statistics
        response = await client.get(f"{BASE_URL}/jobs/stats")
        print(f"Job Stats - Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print("")

        # Get recent jobs
        response = await client.get(f"{BASE_URL}/jobs/recent?limit=5")
        print(f"Recent Jobs - Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print("")

async def test_get_transactions():
    """Test get transactions with filters"""
    print("🧪 Testing get transactions endpoint...")

    async with httpx.AsyncClient() as client:
        # Get all transactions
        response = await client.get(f"{BASE_URL}/transactions/")
        print(f"All Transactions - Status: {response.status_code}")
        result = response.json()
        print(f"Found {result.get('total_count', 0)} transactions")
        print("")

        # Get filtered transactions
        response = await client.get(f"{BASE_URL}/transactions/?account_id=acc_12345&limit=10")
        print(f"Filtered Transactions - Status: {response.status_code}")
        result = response.json()
        print(f"Found {len(result.get('transactions', []))} filtered transactions")
        print("")

async def main():
    """Run all tests"""
    print("🚀 Starting transaction endpoint tests...\n")

    # Test health check first
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("❌ Health check failed - server not running?")
            return
        print("✅ Server is healthy\n")

    # Run tests
    await test_bulk_sync()
    await test_webhook()
    await asyncio.sleep(2)  # Give time for background jobs
    await test_job_stats()
    await test_get_transactions()

    print("✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())