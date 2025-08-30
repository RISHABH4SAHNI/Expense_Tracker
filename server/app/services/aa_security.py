"""
Account Aggregator Security Service

Provides secure token encryption/decryption utilities using Fernet (AES 128) encryption.
Designed specifically for protecting sensitive Account Aggregator tokens and credentials.

Security Features:
- Uses Fernet symmetric encryption (AES 128 in CBC mode with HMAC SHA256)
- Auto-generates development keys if not provided
- Secure key derivation from environment variables
- Safe error handling without leaking sensitive information
"""

import os
import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

class AASecurityError(Exception):
    """Base exception for Account Aggregator security operations"""
    pass

class AATokenEncryptionError(AASecurityError):
    """Exception raised when token encryption/decryption fails"""
    pass


class AATokenEncryption:
    """
    Account Aggregator Token Encryption Service

    Handles secure encryption and decryption of AA tokens using Fernet encryption.

    Production Security Notes:
    - The AA_TOKEN_FERNET_KEY should be stored in a Key Management Service (KMS) like:
      * AWS KMS, Azure Key Vault, Google Cloud KMS
      * HashiCorp Vault
      * Kubernetes Secrets with encryption at rest
    - Never commit encryption keys to version control
    - Rotate keys periodically (Fernet supports key rotation)
    - Use different keys for different environments (dev/staging/prod)
    """

    def __init__(self):
        self._fernet = self._initialize_encryption()

    def _initialize_encryption(self) -> Fernet:
        """
        Initialize Fernet encryption with key from environment

        Returns:
            Fernet: Configured Fernet instance for encryption/decryption

        Raises:
            AATokenEncryptionError: If encryption setup fails
        """
        try:
            # Get encryption key from environment
            fernet_key = os.getenv("AA_TOKEN_FERNET_KEY")

            if fernet_key:
                # Use provided key (production scenario)
                key_bytes = fernet_key.encode('utf-8')
                logger.info("🔐 Using AA token encryption key from environment")
            else:
                # Generate development key (development scenario)
                logger.warning("⚠️  AA_TOKEN_FERNET_KEY not set, generating development key")
                logger.warning("⚠️  This should NOT be used in production!")

                # Generate a deterministic key for development consistency
                password = b"aa-dev-encryption-key-change-in-production"
                salt = b"aa-dev-salt-12345"

                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key_bytes = base64.urlsafe_b64encode(kdf.derive(password))

            return Fernet(key_bytes)

        except Exception as e:
            logger.error(f"Failed to initialize AA token encryption: {e}")
            raise AATokenEncryptionError(f"Encryption setup failed: {e}")

    def encrypt_token(self, plaintext: str) -> str:
        """
        Encrypt an Account Aggregator token

        Args:
            plaintext: The plain text token to encrypt

        Returns:
            str: Base64 encoded encrypted token

        Raises:
            AATokenEncryptionError: If encryption fails
        """
        if not plaintext:
            raise AATokenEncryptionError("Cannot encrypt empty token")

        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            logger.error("Failed to encrypt AA token")  # Don't log the actual token
            raise AATokenEncryptionError("Token encryption failed")

    def decrypt_token(self, ciphertext: str) -> str:
        """
        Decrypt an Account Aggregator token

        Args:
            ciphertext: The base64 encoded encrypted token

        Returns:
            str: The decrypted plain text token

        Raises:
            AATokenEncryptionError: If decryption fails
        """
        if not ciphertext:
            raise AATokenEncryptionError("Cannot decrypt empty ciphertext")

        try:
            encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error("Failed to decrypt AA token")  # Don't log the actual ciphertext
            raise AATokenEncryptionError("Token decryption failed")


# Global instance for the application
_aa_encryption = None

def get_aa_encryption() -> AATokenEncryption:
    """
    Get the global AA token encryption instance

    Returns:
        AATokenEncryption: The global encryption instance
    """
    global _aa_encryption
    if _aa_encryption is None:
        _aa_encryption = AATokenEncryption()
    return _aa_encryption


# Convenience functions for direct use
def encrypt_token(plaintext: str) -> str:
    """
    Encrypt an Account Aggregator token

    Args:
        plaintext: The plain text token to encrypt

    Returns:
        str: Base64 encoded encrypted token
    """
    return get_aa_encryption().encrypt_token(plaintext)


def decrypt_token(ciphertext: str) -> str:
    """
    Decrypt an Account Aggregator token

    Args:
        ciphertext: The base64 encoded encrypted token

    Returns:
        str: The decrypted plain text token
    """
    return get_aa_encryption().decrypt_token(ciphertext)