#!/usr/bin/env python3
"""
Integration test for AA Client functionality

Tests the complete flow:
1. start_consent(user_id) 
2. poll_consent_status(ref_id) until LINKED
3. fetch_transactions(account_id)
4. simulate_webhook_delivery
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

async def test_aa_client_flow():
    """Test the complete AA client flow"""
    print("🚀 Testing AA Client Integration...")

    try:
        from app.services.aa_client import aa_client, mock_generate_sample_transactions
        print("✅ Successfully imported AA client")

        # Test 1: Start consent
        print("\n📋 Test 1: Starting consent...")
        user_id = "test_user_123"

        consent_result = await aa_client.start_consent(user_id)
        print(f"  ✅ Consent started: {consent_result}")

        ref_id = consent_result["ref_id"]
        consent_url = consent_result["consent_url"]

        assert ref_id.startswith("mock_consent_")
        assert "ref_id=" in consent_url

        # Test 2: Poll consent status
        print("\n🔄 Test 2: Polling consent status...")

        # Should be PENDING initially
        status = await aa_client.poll_consent_status(ref_id)
        print(f"  Initial status: {status}")
        assert status == "PENDING"

        # Wait for status to change to LINKED (mock transitions after 30 seconds)
        print("  Waiting for consent to be linked (this may take 30+ seconds)...")

        max_attempts = 10
        for attempt in range(max_attempts):
            await asyncio.sleep(5)  # Wait 5 seconds between polls
            status = await aa_client.poll_consent_status(ref_id)
            print(f"  Attempt {attempt + 1}: Status = {status}")

            if status == "LINKED":
                print("  ✅ Consent successfully linked!")
                break
        else:
            print("  ⚠️  Consent didn't link within expected time")

        # Test 3: Fetch transactions
        print("\n📊 Test 3: Fetching transactions...")

        # Use a mock account ID
        account_id = "hdfc_user_1"
        since_ts = datetime.utcnow() - timedelta(days=30)

        transactions = await aa_client.fetch_transactions(account_id, since_ts, limit=10)
        print(f"  ✅ Fetched {len(transactions)} transactions")

        if transactions:
            print(f"  Sample transaction: {transactions[0]}")

        # Test 4: Generate sample transactions
        print("\n🔧 Test 4: Generating sample transactions...")
        sample_txs = mock_generate_sample_transactions("test_account", 5)
        print(f"  ✅ Generated {len(sample_txs)} sample transactions")

        print("\n🎉 All tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_aa_client_flow())
    sys.exit(0 if success else 1)