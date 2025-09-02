#!/usr/bin/env python3
"""
Test Firebase Admin SDK Setup

This script tests if Firebase Admin SDK is properly configured.
"""

import sys
import os

# Add the server directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.firebase_admin import initialize_firebase, create_custom_token

def test_firebase_setup():
    """Test Firebase Admin SDK setup"""
    print("🧪 Testing Firebase Admin SDK Setup...\n")

    # Test 1: Initialize Firebase
    print("1️⃣ Testing Firebase initialization...")
    if initialize_firebase():
        print("   ✅ Firebase Admin SDK initialized successfully!")
    else:
        print("   ❌ Firebase Admin SDK initialization failed!")
        return False

    # Test 2: Create custom token
    print("\n2️⃣ Testing custom token creation...")
    test_user_id = "test_user_123"
    test_claims = {"email": "test@example.com", "role": "user"}

    token = create_custom_token(test_user_id, test_claims)
    if token:
        print(f"   ✅ Custom token created successfully!")
        print(f"   📄 Token preview: {token[:50]}...")
    else:
        print("   ❌ Custom token creation failed!")
        return False

    print("\n🎉 All Firebase tests passed!")
    return True

if __name__ == "__main__":
    try:
        success = test_firebase_setup()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)
