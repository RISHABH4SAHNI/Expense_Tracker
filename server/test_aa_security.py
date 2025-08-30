#!/usr/bin/env python3
"""
Test script for AA Security Service

Verifies that token encryption and decryption works correctly with roundtrip tests.
"""

import os
import sys
import traceback

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def test_aa_token_encryption():
    """Test Account Aggregator token encryption roundtrip"""
    print("🚀 Testing AA Token Encryption Service...")

    try:
        from app.services.aa_security import encrypt_token, decrypt_token, AATokenEncryptionError
        print("✅ Successfully imported AA security functions")

        # Test cases
        test_cases = [
            "simple-token-123",
            "complex-token-with-special-chars!@#$%^&*()",
            "very-long-token-" + "x" * 100,
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token",
            "aa_token_12345_with_underscores_and_numbers_987654321"
        ]

        print(f"\n🧪 Testing {len(test_cases)} token encryption scenarios...")

        for i, original_token in enumerate(test_cases, 1):
            print(f"\n  Test {i}: Token length {len(original_token)} chars")

            # Encrypt the token
            encrypted_token = encrypt_token(original_token)
            print(f"    ✅ Encryption successful (length: {len(encrypted_token)} chars)")

            # Verify encrypted token is different from original
            if encrypted_token == original_token:
                print(f"    ❌ Encrypted token same as original!")
                return False

            # Decrypt the token
            decrypted_token = decrypt_token(encrypted_token)
            print(f"    ✅ Decryption successful")

            # Verify roundtrip integrity
            if decrypted_token == original_token:
                print(f"    ✅ Roundtrip successful - token integrity maintained")
            else:
                print(f"    ❌ Roundtrip failed!")
                print(f"      Original:  {original_token}")
                print(f"      Decrypted: {decrypted_token}")
                return False

        # Test error handling
        print(f"\n🔍 Testing error handling...")
        try:
            encrypt_token("")
            print("    ❌ Should have failed on empty token")
            return False
        except AATokenEncryptionError:
            print("    ✅ Correctly rejected empty token")

        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_aa_token_encryption()
    if success:
        print("\n🎉 All AA token encryption tests passed!")
        print("\n💡 To use in Python REPL:")
        print("    from app.services.aa_security import encrypt_token, decrypt_token")
        print("    encrypted = encrypt_token('my-secret-token')")
        print("    decrypted = decrypt_token(encrypted)")
        print("    assert decrypted == 'my-secret-token'")
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)