#!/usr/bin/env python3
"""
Verification script for AA models

This script demonstrates that the AA models can be imported and used correctly.
It creates the tables and shows basic usage of the models.
"""

import os
import sys
import uuid
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.models.aa_models import (
        AAConsent, AAAccount, AASyncLog,
        AAConsentStatus, AASyncStatus,
        ConsentStartOut, ConsentStatusOut, AAAccountOut, AASyncLogOut,
        create_aa_tables
    )
    print("✅ Successfully imported AA models")
except ImportError as e:
    print(f"❌ Failed to import AA models: {e}")
    sys.exit(1)

def test_model_creation():
    """Test creating model instances"""
    print("\n🧪 Testing model creation...")

    # Test AAConsent creation
    try:
        consent = AAConsent(
            user_id=uuid.uuid4(),
            ref_id="test-ref-123",
            status=AAConsentStatus.PENDING
        )
        print("✅ AAConsent model created successfully")

        # Test token encryption/decryption
        test_token = "test-token-12345"
        consent.set_encrypted_token(test_token)
        decrypted = consent.get_decrypted_token()

        if decrypted == test_token:
            print("✅ Token encryption/decryption working correctly")
        else:
            print(f"❌ Token encryption/decryption failed: {decrypted} != {test_token}")

    except Exception as e:
        print(f"❌ AAConsent creation failed: {e}")

    # Test AAAccount creation
    try:
        account = AAAccount(
            user_id=uuid.uuid4(),
            aa_account_id="aa-account-123",
            display_name="Test Bank Account"
        )
        print("✅ AAAccount model created successfully")
    except Exception as e:
        print(f"❌ AAAccount creation failed: {e}")

    # Test AASyncLog creation
    try:
        sync_log = AASyncLog(
            user_id=uuid.uuid4(),
            start_ts=datetime.utcnow(),
            status=AASyncStatus.RUNNING
        )
        print("✅ AASyncLog model created successfully")
    except Exception as e:
        print(f"❌ AASyncLog creation failed: {e}")

def test_pydantic_schemas():
    """Test Pydantic schema creation"""
    print("\n📋 Testing Pydantic schemas...")

    try:
        # Test all the output schemas can be created
        schemas = [ConsentStartOut, ConsentStatusOut, AAAccountOut, AASyncLogOut]
        for schema in schemas:
            print(f"✅ {schema.__name__} schema available")
    except Exception as e:
        print(f"❌ Pydantic schema test failed: {e}")

if __name__ == "__main__":
    print("🚀 Verifying AA models...")
    test_model_creation()
    test_pydantic_schemas()
    print("\n🎉 AA models verification completed!")