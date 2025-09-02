"""
Firebase Admin Service

Handles Firebase Admin SDK operations for generating custom tokens
that allow users to authenticate with Firebase Auth after logging in
through our custom JWT system.
"""

import json
import logging
import os
from typing import Optional

try:
    import firebase_admin
    from firebase_admin import auth, credentials
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logging.warning("Firebase Admin SDK not installed. Custom token generation will be disabled.")

from app.config import FIREBASE_SERVICE_ACCOUNT_PATH, is_dev_mode

logger = logging.getLogger(__name__)

# Global Firebase app instance
_firebase_app = None


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    global _firebase_app

    if not FIREBASE_AVAILABLE:
        logger.warning("🔥 Firebase Admin SDK not available")
        return False

    if _firebase_app is not None:
        logger.info("🔥 Firebase Admin SDK already initialized")
        return True

    try:
        if FIREBASE_SERVICE_ACCOUNT_PATH and os.path.exists(FIREBASE_SERVICE_ACCOUNT_PATH):
            # Use service account file
            logger.info(f"🔥 Using Firebase service account: {FIREBASE_SERVICE_ACCOUNT_PATH}")
            cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
        elif is_dev_mode() and not FIREBASE_SERVICE_ACCOUNT_PATH:
            # Development mode without service account - use dummy credentials
            logger.info("🔥 Development mode: Using dummy Firebase credentials")
            service_account_info = {
                "type": "service_account",
                "project_id": "expense-tracker-45860",
                "private_key_id": "dummy_key_id",
                "private_key": "-----BEGIN PRIVATE KEY-----\nDUMMY_PRIVATE_KEY_FOR_DEV\n-----END PRIVATE KEY-----\n",
                "client_email": "firebase-adminsdk-dummy@expense-tracker-45860.iam.gserviceaccount.com",
                "client_id": "dummy_client_id",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-dummy%40expense-tracker-45860.iam.gserviceaccount.com"
            }
            cred = credentials.Certificate(service_account_info)
        else:
            logger.warning("🔥 No Firebase service account configured")
            return False

        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("✅ Firebase Admin SDK initialized successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to initialize Firebase Admin SDK: {e}")
        return False


def create_custom_token(user_id: str, additional_claims: Optional[dict] = None) -> Optional[str]:
    """
    Create a Firebase custom token for the given user

    Args:
        user_id: Unique user identifier
        additional_claims: Optional additional claims to include in the token

    Returns:
        Custom token string or None if creation fails
    """
    if not FIREBASE_AVAILABLE or _firebase_app is None:
        logger.warning("🔥 Firebase not available for custom token generation")
        return None

    try:
        # For development without real service account, return a mock token
        if is_dev_mode() and not (FIREBASE_SERVICE_ACCOUNT_PATH and os.path.exists(FIREBASE_SERVICE_ACCOUNT_PATH)):
            logger.info(f"🔥 DEV: Mock custom token for user {user_id}")
            return f"dev_custom_token_{user_id}"

        # Create custom token
        custom_token = auth.create_custom_token(user_id, additional_claims)
        logger.info(f"✅ Real custom token created for user: {user_id}")
        return custom_token.decode('utf-8')

    except Exception as e:
        logger.error(f"❌ Failed to create custom token for user {user_id}: {e}")
        return None


# Initialize on import
if initialize_firebase():
    logger.info("🎉 Firebase Admin SDK initialized successfully!")
else:
    logger.warning("⚠️ Firebase Admin SDK not initialized")
    initialize_firebase()