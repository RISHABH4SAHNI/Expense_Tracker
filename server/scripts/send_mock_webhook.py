
#!/usr/bin/env python3
"""
Mock webhook sender for AA transaction webhooks.

This script picks a transaction from mock data and POSTs it to /aa/webhook 
with X-AA-SIGNATURE header using AA_MOCK_WEBHOOK_SECRET for easy local webhook testing.

Usage:
    python send_mock_webhook.py --account hdfc_user_1 --tx-id tx_mock_001
    python send_mock_webhook.py --account hdfc_user_1 --tx-id tx_mock_005
    python send_mock_webhook.py --list  # Show available transactions
"""

import argparse
import json
import hmac
import hashlib
import requests
import os
import sys
from pathlib import Path


def load_mock_data():
    """Load mock transaction data from JSON file."""
    # Find the mock data file relative to this script
    script_dir = Path(__file__).parent
    mock_data_path = script_dir.parent / "mock_data" / "aa_transactions.json"

    if not mock_data_path.exists():
        print(f"❌ Mock data file not found: {mock_data_path}")
        sys.exit(1)

    try:
        with open(mock_data_path, 'r') as f:
            data = json.load(f)
        return data.get("sample_transactions", [])
    except Exception as e:
        print(f"❌ Failed to load mock data: {e}")
        sys.exit(1)


def find_transaction(transactions, account_id, tx_id):
    """Find a transaction by account_id and tx_id."""
    for tx in transactions:
        if tx.get("account_id") == account_id and tx.get("id") == tx_id:
            return tx
    return None


def list_transactions(transactions):
    """List all available transactions."""
    print("📋 Available transactions:")
    print(f"{'Account ID':<15} {'Transaction ID':<15} {'Amount':<10} {'Type':<8} {'Description'}")
    print("-" * 90)

    for tx in transactions:
        desc = tx.get("raw_desc", "")[:40] + "..." if len(tx.get("raw_desc", "")) > 40 else tx.get("raw_desc", "")
        print(f"{tx['account_id']:<15} {tx['id']:<15} {tx['amount']:<10} {tx['type']:<8} {desc}")


def generate_webhook_signature(payload_bytes, secret):
    """Generate HMAC-SHA256 signature for webhook payload."""
    if not secret:
        print("⚠️  No webhook secret configured, signature will be empty")
        return ""

    mac = hmac.new(
        secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    )
    return f"sha256={mac.hexdigest()}"


def send_webhook(account_id, transaction, webhook_url, secret):
    """Send webhook payload to the server."""
    # Create webhook payload
    payload = {
        "account_id": account_id,
        "transaction": {
            "id": transaction["id"],
            "ts": transaction["ts"],
            "amount": transaction["amount"],
            "type": transaction["type"],
            "raw_desc": transaction["raw_desc"]
        }
    }

    # Convert to JSON bytes
    payload_json = json.dumps(payload, indent=2)
    payload_bytes = payload_json.encode('utf-8')

    # Generate signature
    signature = generate_webhook_signature(payload_bytes, secret)

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-AA-Signature": signature
    }

    print(f"🚀 Sending webhook for transaction {transaction['id']}")
    print(f"   Account: {account_id}")
    print(f"   Amount: {transaction['amount']} ({transaction['type']})")
    print(f"   Description: {transaction['raw_desc']}")
    print(f"   URL: {webhook_url}")
    print(f"   Signature: {signature[:25]}...")
    print(f"   Payload preview: {payload_json[:100]}...")

    try:
        response = requests.post(webhook_url, data=payload_bytes, headers=headers, timeout=10)
        print(f"✅ Response: {response.status_code}")
        if response.text:
            try:
                resp_json = response.json()
                print(f"   Response body: {json.dumps(resp_json, indent=2)}")
            except:
                print(f"   Response body: {response.text}")
        return True
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send mock AA webhook")
    parser.add_argument("--account", help="Account ID (e.g., hdfc_user_1)")
    parser.add_argument("--tx-id", help="Transaction ID (e.g., tx_mock_001)")
    parser.add_argument("--url", default="http://localhost:8000/aa/webhook", help="Webhook URL")
    parser.add_argument("--list", action="store_true", help="List all available transactions")

    args = parser.parse_args()

    # Load mock data
    transactions = load_mock_data()

    # Handle list command
    if args.list:
        list_transactions(transactions)
        return

    # Validate required arguments
    if not args.account or not args.tx_id:
        print("❌ Both --account and --tx-id are required (or use --list to see available transactions)")
        sys.exit(1)

    # Get webhook secret from environment
    secret = os.getenv("AA_MOCK_WEBHOOK_SECRET", "mock_webhook_secret_key")

    # Find transaction
    transaction = find_transaction(transactions, args.account, args.tx_id)

    if not transaction:
        print(f"❌ Transaction not found: account={args.account}, tx_id={args.tx_id}")
        print("\nAvailable transactions for this account:")
        account_txs = [tx for tx in transactions if tx.get("account_id") == args.account]
        if account_txs:
            for tx in account_txs:
                print(f"   {tx['id']} - {tx['amount']} ({tx['type']}) - {tx['raw_desc'][:50]}...")
        else:
            print(f"   No transactions found for account: {args.account}")
            print("\nAll available accounts:")
            accounts = set(tx.get("account_id") for tx in transactions)
            for acc in sorted(accounts):
                print(f"   {acc}")
        sys.exit(1)

    # Send webhook
    success = send_webhook(args.account, transaction, args.url, secret)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
