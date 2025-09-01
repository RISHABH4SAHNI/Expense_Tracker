"""
Test script for the Financial Insights Engine

This script demonstrates the capabilities of the insights engine
with various natural language queries.
"""

import asyncio
import json
import httpx
from datetime import datetime

# Test queries to demonstrate different capabilities
TEST_QUERIES = [
    {
        "question": "How much did I spend on food in July?",
        "description": "Category-specific spending with time filter"
    },
    {
        "question": "What are my top 5 spending categories this month?",
        "description": "Category analysis and ranking"
    },
    {
        "question": "Show me transactions over ₹1000 in the last week",
        "time_range_days": 7,
        "description": "Amount-based filtering with recent time range"
    },
    {
        "question": "Compare my spending this month vs last month",
        "description": "Time-based comparison analysis"
    },
    {
        "question": "What's my average daily spending on transport?",
        "description": "Category-specific daily average calculation"
    },
    {
        "question": "Which merchants do I spend the most money at?",
        "description": "Merchant analysis and ranking"
    },
    {
        "question": "How much did I earn from salary this month?",
        "description": "Income analysis by category"
    },
    {
        "question": "Show me my Netflix and streaming expenses",
        "description": "Merchant-specific filtering"
    },
    {
        "question": "What's my net cash flow for the last 30 days?",
        "description": "Income vs expense analysis"
    },
    {
        "question": "Give me a breakdown of my shopping expenses",
        "description": "Category-specific detailed analysis"
    }
]

async def test_insights_engine():
    """Test the insights engine with various queries"""

    base_url = "http://localhost:8001"

    print("🧪 Testing Financial Insights Engine")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test health check first
        try:
            health_response = await client.get(f"{base_url}/health")
            if health_response.status_code == 200:
                print("✅ Health check passed")
            else:
                print("❌ Health check failed")
                return
        except Exception as e:
            print(f"❌ Cannot connect to insights engine: {e}")
            print("   Make sure to run: python insights_engine.py")
            return

        print("\n🔍 Testing Query Patterns")
        print("-" * 30)

        # Test each query
        for i, test_case in enumerate(TEST_QUERIES, 1):
            print(f"\n{i}. {test_case['description']}")
            print(f"   Q: {test_case['question']}")

            # Prepare request
            request_data = {
                "question": test_case["question"],
                "user_id": "test-user-123",  # Mock user ID
                "time_range_days": test_case.get("time_range_days", 30),
                "include_supporting_data": True,
                "max_transactions": 5
            }

            try:
                response = await client.post(f"{base_url}/insights", json=request_data)

                if response.status_code == 200:
                    result = response.json()
                    print(f"   A: {result['answer']}")
                    print(f"   Confidence: {result['confidence']:.2f}")
                    print(f"   Execution: {result['execution_time_ms']:.1f}ms")

                    if result.get('sql_query'):
                        print(f"   SQL: {result['sql_query'][:100]}...")
                else:
                    print(f"   ❌ Error: {response.status_code} - {response.text}")

            except Exception as e:
                print(f"   ❌ Request failed: {e}")

        print("\n📊 Testing Pattern Information")
        print("-" * 30)

        # Test patterns endpoint
        try:
            patterns_response = await client.get(f"{base_url}/insights/patterns")
            if patterns_response.status_code == 200:
                patterns = patterns_response.json()
                print("Available patterns:", ", ".join(patterns["patterns"]))
                print("\nExample queries by category:")
                for category, examples in patterns["examples"].items():
                    print(f"  {category.title()}:")
                    for example in examples[:2]:  # Show first 2 examples
                        print(f"    • {example}")
            else:
                print("❌ Failed to get patterns")
        except Exception as e:
            print(f"❌ Failed to get patterns: {e}")

    print("\n✅ Testing completed!")

    # Test anomaly detection if available
    print("\n🔍 Testing Anomaly Detection")
    print("-" * 30)

    try:
        anomaly_request = {
            "user_id": "test-user-123",
            "time_range_days": 30,
            "training_period_days": 180,
            "sensitivity": 0.1,
            "min_amount_threshold": 100.0
        }

        anomaly_response = await client.post(f"{base_url}/anomalies", json=anomaly_request)
        if anomaly_response.status_code == 200:
            result = anomaly_response.json()
            print(f"✅ Anomaly detection working")
            print(f"   Analyzed: {result['total_transactions_analyzed']} transactions")
            print(f"   Anomalies: {result['anomalies_detected']} ({result['anomaly_rate']:.1f}%)")
            print(f"   Models: {result['model_metadata'].get('models_used', ['Unknown'])}")

            if result['anomalies']:
                print(f"   Sample anomaly: ₹{result['anomalies'][0]['transaction_details']['amount']:,.2f}")
                print(f"   Reason: {result['anomalies'][0]['anomaly_reasons'][0]}")
        else:
            print(f"⚠️  Anomaly detection: {anomaly_response.status_code}")
    except Exception as e:
        print(f"⚠️  Anomaly detection not available: {e}")

    print("\nNext steps:")
    print("1. Connect to your actual database")
    print("2. Add user authentication")
    print("3. Deploy as a microservice")
    print("4. Integrate with your main application")

if __name__ == "__main__":
    asyncio.run(test_insights_engine())
