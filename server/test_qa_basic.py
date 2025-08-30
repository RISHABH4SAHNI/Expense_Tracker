#!/usr/bin/env python3
"""
QA endpoint test script for localhost

This script tests:
1. Server connection on localhost
2. QA endpoint functionality
3. Different question types
4. Error handling

Run with: python test_qa_localhost.py
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from decimal import Decimal
import random

# API configuration for localhost
BASE_URL = "http://localhost:8000"

async def test_server_connection():
    """Test if the server is running"""
    print("🔗 Testing server connection...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/docs", timeout=5.0)
            if response.status_code == 200:
                print("✅ Server is running and accessible!")
                return True
            else:
                print(f"❌ Server returned status: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

async def test_qa_endpoint():
    """Test the QA endpoint with various questions"""
    print("🤔 Testing QA endpoint...")
    
    test_questions = [
        "How much did I spend on food?",
        "What's my total spending this month?", 
        "Show me my restaurant expenses",
        "What are my top merchants?",
        "How much did I spend on Zomato?",
        "What was my biggest expense?",
        "How much did I spend yesterday?",
        "Show me entertainment expenses",
    ]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, question in enumerate(test_questions, 1):
            print(f"  {i}. Testing: '{question}'")
            
            try:
                payload = {
                    "question": question,
                    "context_days": 30
                }
                
                response = await client.post(
                    f"{BASE_URL}/qa/",
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"     ✅ Answer: {data.get('answer', 'No answer')[:150]}...")
                    print(f"     📊 Method: {data.get('analysis_method', 'Unknown')}")
                    print(f"     🎯 Confidence: {data.get('confidence', 'N/A')}")
                    
                    # Show sources if available
                    sources = data.get('sources', [])
                    if sources:
                        print(f"     📄 Sources: {len(sources)} transactions found")
                    
                else:
                    print(f"     ❌ Failed with status: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"     Error: {error_data}")
                    except:
                        print(f"     Error: {response.text}")
                    
            except Exception as e:
                print(f"     💥 Exception: {e}")
            
            print()

async def test_edge_cases():
    """Test edge cases and error handling"""
    print("🧪 Testing edge cases...")
    
    edge_cases = [
        {"question": "", "context_days": 30},  # Empty question
        {"question": "test", "context_days": -1},  # Invalid context days
        {"question": "A" * 1000, "context_days": 30},  # Very long question
        {"question": "Normal question", "context_days": 0},  # Zero context days
    ]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, payload in enumerate(edge_cases, 1):
            print(f"  {i}. Testing edge case: {str(payload)[:100]}...")
            
            try:
                response = await client.post(
                    f"{BASE_URL}/qa/",
                    json=payload,
                    timeout=30.0
                )
                
                print(f"     Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"     Answer: {data.get('answer', 'No answer')[:100]}...")
                else:
                    try:
                        error_data = response.json()
                        print(f"     Expected error: {error_data.get('detail', 'Unknown error')}")
                    except:
                        print(f"     Raw error: {response.text[:100]}")
                        
            except Exception as e:
                print(f"     Exception: {e}")
            
            print()

async def main():
    """Run all tests"""
    print("🚀 Starting QA endpoint tests on localhost")
    print("=" * 60)
    
    if await test_server_connection():
        await test_qa_endpoint()
        await test_edge_cases()
    else:
        print("❌ Server is not accessible. Please start the server first.")
    
    print("🏁 Test completed!")

if __name__ == "__main__":
    asyncio.run(main())
