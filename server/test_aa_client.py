"""
Test script for Setu Account Aggregator client
Tests consent flow, transaction fetching, and integration with API endpoints
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from app.services.aa_client import aa_client
from app.services.transaction_service import transaction_service

BASE_URL = "http://127.0.0.1:8000"

async def test_aa_client_directly():
    """Test the AA client methods directly"""
    print("🧪 Testing AA Client directly...\n")

    # Test consent flow
    print("1. Testing consent flow...")
    user_id = "test_user_123"
    consent = await aa_client.simulate_consent_flow(user_id)

    print(f"✅ Consent created:")
    print(f"   - Consent Handle: {consent.consent_handle}")
    print(f"   - Status: {consent.status}")
    print(f"   - Account IDs: {consent.account_ids}")
    print(f"   - Expires: {consent.expires_at}")
    print("")

    # Test account info
    print("2. Testing account info...")
    for account_id in consent.account_ids[:2]:  # Test first 2 accounts
        account_info = await aa_client.get_account_info(account_id)
        print(f"✅ Account Info for {account_id}:")
        print(f"   - Bank: {account_info.bank_name}")
        print(f"   - Account Number: {account_info.account_number}")
        print(f"   - IFSC: {account_info.ifsc}")
        print(f"   - Balance: ₹{account_info.balance}")
        print("")

    # Test transaction fetching
    print("3. Testing transaction fetching...")
    from_date = datetime.utcnow() - timedelta(days=30)

    for account_id in consent.account_ids[:1]:  # Test first account
        transactions = await aa_client.fetch_transactions_for_account(
            account_id=account_id,
            since=from_date
        )

        print(f"✅ Fetched {len(transactions)} transactions for {account_id}:")
        for i, tx in enumerate(transactions[:3]):  # Show first 3
            print(f"   {i+1}. {tx.raw_desc} - ₹{tx.amount} ({tx.type.value})")
        if len(transactions) > 3:
            print(f"   ... and {len(transactions) - 3} more")
        print("")

    return consent

async def test_transaction_service():
    """Test the transaction service integration"""
    print("🧪 Testing Transaction Service...\n")

    # Test account linking
    user_id = "service_test_user"
    print("1. Testing account linking...")
    consent = await transaction_service.initiate_account_linking(user_id)
    print(f"✅ Linked {len(consent.account_ids)} accounts for user {user_id}")
    print("")

    # Test transaction sync
    print("2. Testing transaction sync...")
    from_date = datetime.utcnow() - timedelta(days=7)

    for account_id in consent.account_ids[:1]:
        sync_result = await transaction_service.sync_account_transactions(
            account_id=account_id,
            from_date=from_date,
            db=None  # Mock mode
        )

        print(f"✅ Sync result for {account_id}:")
        print(f"   - Status: {sync_result.status}")
        print(f"   - Inserted: {sync_result.inserted_count}")
        print(f"   - Updated: {sync_result.updated_count}")
        print("")

async def test_api_endpoints():
    """Test the AA-related API endpoints"""
    print("🧪 Testing API Endpoints...\n")

    async with httpx.AsyncClient() as client:
        # Test account linking endpoint
        print("1. Testing account linking endpoint...")
        response = await client.post(
            f"{BASE_URL}/transactions/link-account",
            params={"user_id": "api_test_user"}
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        print("")

        # Test AA sync endpoint
        if response.status_code == 200 and result.get("account_ids"):
            print("2. Testing AA sync endpoint...")
            account_id = result["account_ids"][0]
            from_date = (datetime.utcnow() - timedelta(days=7)).isoformat()

            response = await client.post(
                f"{BASE_URL}/transactions/sync-from-aa",
                params={
                    "account_id": account_id,
                    "from_date": from_date
                }
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            print("")

async def main():
    """Run all AA client tests"""
    print("🚀 Starting Setu AA Client Tests...\n")

    # Test direct client usage
    await test_aa_client_directly()

    # Test service layer
    await test_transaction_service()

    # Test API endpoints
    try:
        await test_api_endpoints()
    except Exception as e:
        print(f"⚠️ API endpoint tests failed (server not running?): {e}")

    print("✅ All AA client tests completed!")

if __name__ == "__main__":
    asyncio.run(main())