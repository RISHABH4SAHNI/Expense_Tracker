"""
Account Aggregator (AA) Client Wrapper

This module provides a comprehensive AA client wrapper with environment toggle
support for both mock and real Account Aggregator implementations.

PRODUCTION REPLACEMENT GUIDE:
============================
To replace mock with real Setu/Finvu client:

1. Install AA SDK: 
   pip install setu-aa-python-sdk
   # OR
   pip install finvu-aa-python-sdk

3. Update environment variables:
   - USE_REAL_AA=true
   - AA_BASE_URL=https://api.setu.co
   - AA_API_KEY=your_api_key
   - AA_SECRET=your_secret_key

4. Implement RealAAClient class with these methods:
   - start_consent(user_id) -> real consent creation
   - poll_consent_status(ref_id) -> real status polling
   - fetch_transactions(account_id, since_ts, limit) -> real data fetch

5. Handle real FIP (Financial Information Provider) responses
6. Add proper error handling and retries
7. Implement webhook signature verification

Real implementation would look like:
```python
from setu import SetuAAClient
# OR from finvu import FinvuAAClient

client = SetuAAClient(
    api_key=os.getenv("AA_API_KEY"),
    secret=os.getenv("AA_SECRET"),
    base_url=os.getenv("AA_BASE_URL")
)

class RealAAClient:
    def __init__(self):
        self.client = client

    async def start_consent(self, user_id: str):
        # Real consent creation with actual banks
        consent = await self.client.create_consent(
            user_id=user_id,
            fip_ids=["HDFC", "ICICI", "SBI", "AXIS"],
            data_range={"from": "2023-01-01", "to": "2024-12-31"}
        )
        return {"consent_url": consent.redirect_url, "ref_id": consent.id}

    async def poll_consent_status(self, ref_id: str):
        # Real status polling
        status = await self.client.get_consent_status(ref_id)
        return status.status  # "PENDING", "ACTIVE", "EXPIRED", etc.

    async def fetch_transactions(self, account_id: str, since_ts=None, limit=500):
        # Real transaction fetching with FI data decryption
        data = await self.client.fetch_financial_information(
            account_id=account_id,
            from_date=since_ts,
            limit=limit
        )
        return data.transactions
```
"""

import os
import json
import uuid
import random
import asyncio
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

import httpx
import asyncpg

from app.config import is_real_aa
from app.database import get_db
from app.services.aa_security import encrypt_token
from app.models.aa_models import AAConsentStatus

logger = logging.getLogger(__name__)


class ConsentResponse:
    """
    Response object for AA consent operations

    Provides a structured response for consent start operations with
    consistent data access patterns.
    """

    def __init__(self, consent_url: str, ref_id: str):
        self.consent_url = consent_url
        self.ref_id = ref_id

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary representation"""
        return {
            "consent_url": self.consent_url,
            "ref_id": self.ref_id
        }

    def __str__(self) -> str:
        return f"ConsentResponse(ref_id={self.ref_id})"

    def __repr__(self) -> str:
        return self.__str__()

class AAClientError(Exception):
    """Base exception for AA client operations"""
    pass

class MockAAClient:
    """
    Mock Account Aggregator client for development and testing.

    Simulates the full AA consent flow and transaction fetching with
    realistic data and database persistence.
    """

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.mock_data_file = os.path.join(self.base_dir, "mock_data", "aa_transactions.json")

        # Simulated consent states (in real implementation, this would be external)
        self._consent_states = {}
        self._linked_accounts = {}

        # Mock webhook secret for signature verification
        self.webhook_secret = os.getenv("AA_MOCK_WEBHOOK_SECRET", "mock_webhook_secret_key")

        logger.info("🏦 Initialized Mock AA Client")

    async def start_consent(self, user_id: str) -> Dict[str, str]:
        """
        Create a mock consent and persist AAConsent row with status "PENDING"

        Args:
            user_id: User identifier

        Returns:
            Dict containing consent_url and ref_id
        """
        try:
            # Generate mock reference ID
            ref_id = f"mock_consent_{uuid.uuid4().hex[:12]}"

            # Create consent URL (mock)
            consent_url = f"https://mock-aa.example.com/consent?ref_id={ref_id}&user_id={user_id}"

            # Get database connection
            async with asyncpg.create_pool(
                os.getenv("DATABASE_URL", "postgresql://expenseuser:expensepass@localhost:5433/expensedb"),
                min_size=1, max_size=2
            ) as pool:
                async with pool.acquire() as conn:
                    # Insert AAConsent record
                    await conn.execute(
                        """
                        INSERT INTO aa_consents (user_id, ref_id, status, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        user_id, ref_id, AAConsentStatus.PENDING.value, 
                        datetime.utcnow(), datetime.utcnow()
                    )

            # Store in mock state
            self._consent_states[ref_id] = {
                "user_id": user_id,
                "status": "PENDING",
                "created_at": datetime.utcnow(),
                "accounts": []
            }

            logger.info(f"🔄 Started consent for user {user_id}, ref_id: {ref_id}")

            return {
                "consent_url": consent_url,
                "ref_id": ref_id
            }

        except Exception as e:
            logger.error(f"Failed to start consent: {e}")
            raise AAClientError(f"Failed to start consent: {e}")

    async def poll_consent_status(self, ref_id: str) -> str:
        """
        Poll consent status. Simulates "PENDING" -> "LINKED" after short delay.
        When "LINKED", creates AAAccount and stores encrypted token.

        Args:
            ref_id: Consent reference ID

        Returns:
            str: Status - "PENDING" or "LINKED"
        """
        try:
            # Simulate timing-based status transition
            if ref_id not in self._consent_states:
                return "EXPIRED"

            consent = self._consent_states[ref_id]
            created_at = consent["created_at"]
            elapsed = datetime.utcnow() - created_at

            # Simulate consent approval after 30 seconds
            if elapsed.total_seconds() > 30 and consent["status"] == "PENDING":
                await self._simulate_consent_linking(ref_id, consent)
                return "LINKED"

            return consent["status"]

        except Exception as e:
            logger.error(f"Failed to poll consent status: {e}")
            raise AAClientError(f"Failed to poll consent status: {e}")

    async def _simulate_consent_linking(self, ref_id: str, consent: Dict):
        """Simulate consent linking - create accounts and update database"""
        try:
            user_id = consent["user_id"]

            # Mock token for this consent
            mock_token = f"mock_aa_token_{uuid.uuid4().hex[:16]}"
            encrypted_token = encrypt_token(mock_token)

            # Generate 2-3 mock accounts
            banks = ["HDFC", "ICICI", "SBI", "AXIS"]
            num_accounts = random.randint(2, 3)
            account_ids = []

            async with asyncpg.create_pool(
                os.getenv("DATABASE_URL", "postgresql://expenseuser:expensepass@localhost:5433/expensedb"),
                min_size=1, max_size=2
            ) as pool:
                async with pool.acquire() as conn:
                    # Update consent status and store encrypted token
                    await conn.execute(
                        """
                        UPDATE aa_consents 
                        SET status = $1, encrypted_token = $2, updated_at = $3, last_polled_at = $4
                        WHERE ref_id = $5
                        """,
                        AAConsentStatus.ACTIVE.value, encrypted_token, 
                        datetime.utcnow(), datetime.utcnow(), ref_id
                    )

                    # Create mock AA accounts
                    for i in range(num_accounts):
                        bank = random.choice(banks)
                        aa_account_id = f"{bank.lower()}_{user_id}_{i+1}"
                        display_name = f"{bank} Bank Account ****{random.randint(1000, 9999)}"

                        await conn.execute(
                            """
                            INSERT INTO aa_accounts (user_id, aa_account_id, display_name, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            user_id, aa_account_id, display_name, 
                            datetime.utcnow(), datetime.utcnow()
                        )

                        account_ids.append(aa_account_id)

            # Update mock state
            consent["status"] = "LINKED"
            consent["accounts"] = account_ids
            consent["token"] = mock_token

            logger.info(f"✅ Consent {ref_id} linked with {len(account_ids)} accounts")

        except Exception as e:
            logger.error(f"Failed to simulate consent linking: {e}")
            raise AAClientError(f"Failed to simulate consent linking: {e}")

    async def fetch_transactions(
        self, 
        account_id: str, 
        since_ts: Optional[datetime] = None, 
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Fetch transactions from mock data file

        Args:
            account_id: AA account identifier
            since_ts: Fetch transactions since this timestamp
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dictionaries
        """
        try:
            # Load mock transactions from file
            transactions = self._load_mock_transactions()

            # Filter by account_id if specified in mock data
            if account_id:
                transactions = [tx for tx in transactions if tx.get("account_id") == account_id]

            # Filter by timestamp if provided
            if since_ts:
                filtered_transactions = []
                for tx in transactions:
                    tx_time = datetime.fromisoformat(tx["ts"].replace("Z", "+00:00"))
                    if tx_time >= since_ts:
                        filtered_transactions.append(tx)
                transactions = filtered_transactions

            # Apply limit
            transactions = transactions[:limit]

            # Simulate API delay
            await asyncio.sleep(0.5)

            logger.info(f"📊 Fetched {len(transactions)} transactions for account {account_id}")

            return transactions

        except Exception as e:
            logger.error(f"Failed to fetch transactions: {e}")
            raise AAClientError(f"Failed to fetch transactions: {e}")

    def _load_mock_transactions(self) -> List[Dict[str, Any]]:
        """Load transactions from mock data file"""
        try:
            if not os.path.exists(self.mock_data_file):
                logger.warning(f"Mock data file not found: {self.mock_data_file}")
                return []

            with open(self.mock_data_file, 'r') as f:
                data = json.load(f)
                return data.get("sample_transactions", [])

        except Exception as e:
            logger.error(f"Failed to load mock transactions: {e}")
            return []

    async def simulate_webhook_delivery(
        self, 
        account_id: str, 
        transaction: Dict[str, Any]
    ) -> bool:
        """
        Simulate webhook delivery by posting to local /aa/webhook endpoint

        Args:
            account_id: Account identifier
            transaction: Transaction data

        Returns:
            bool: Success status
        """
        try:
            # Prepare webhook payload
            payload = {
                "event": "transaction.created",
                "account_id": account_id,
                "transaction": transaction,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Generate signature
            signature = self._generate_webhook_signature(payload)

            # Local webhook URL (adjust based on your setup)
            webhook_url = "http://localhost:8000/aa/webhook"

            headers = {
                "Content-Type": "application/json",
                "X-AA-Signature": signature,
                "User-Agent": "Mock-AA-Client/1.0"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=10.0
                )

                if response.status_code == 200:
                    logger.info(f"📡 Webhook delivered successfully for account {account_id}")
                    return True
                else:
                    logger.warning(f"Webhook delivery failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Failed to deliver webhook: {e}")
            return False

    def _generate_webhook_signature(self, payload: Dict[str, Any]) -> str:
        """Generate HMAC signature for webhook payload"""
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"


class RealAAClient:
    """
    Real Account Aggregator client placeholder.

    This would implement actual AA provider integration (Setu/Finvu).
    Currently raises NotImplementedError as requested.
    """

    def __init__(self):
        self.base_url = os.getenv("AA_BASE_URL", "")
        self.api_key = os.getenv("AA_API_KEY", "")
        self.secret = os.getenv("AA_SECRET", "")

        if not all([self.base_url, self.api_key, self.secret]):
            logger.warning("Real AA configuration incomplete")

    async def start_consent(self, user_id: str) -> Dict[str, str]:
        """Start real AA consent flow"""
        raise NotImplementedError("Real AA client not configured")

    async def poll_consent_status(self, ref_id: str) -> str:
        """Poll real AA consent status"""
        raise NotImplementedError("Real AA client not configured")

    async def fetch_transactions(
        self, 
        account_id: str, 
        since_ts: Optional[datetime] = None, 
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Fetch real AA transactions"""
        raise NotImplementedError("Real AA client not configured")

    async def simulate_webhook_delivery(
        self, 
        account_id: str, 
        transaction: Dict[str, Any]
    ) -> bool:
        """Real AA doesn't simulate webhooks"""
        raise NotImplementedError("Real AA client not configured")


class AAClient:
    """
    Main AA Client wrapper with environment toggle.

    Automatically switches between mock and real implementation based on
    the is_real_aa() configuration function.
    """

    def __init__(self):
        if is_real_aa():
            self._client = RealAAClient()
            logger.info("🏦 Using Real AA Client")
        else:
            self._client = MockAAClient()
            logger.info("🎭 Using Mock AA Client")

    async def start_consent(self, user_id: str) -> Dict[str, str]:
        """
        Start AA consent flow

        Args:
            user_id: User identifier

        Returns:
            Dict containing consent_url and ref_id
        """
        return await self._client.start_consent(user_id)

    async def poll_consent_status(self, ref_id: str) -> str:
        """
        Poll consent status

        Args:
            ref_id: Consent reference ID

        Returns:
            str: Status - "PENDING", "LINKED", "EXPIRED", etc.
        """
        return await self._client.poll_consent_status(ref_id)

    async def fetch_transactions(
        self, 
        account_id: str, 
        since_ts: Optional[datetime] = None, 
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Fetch transactions for account

        Args:
            account_id: AA account identifier
            since_ts: Fetch transactions since this timestamp
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dictionaries
        """
        return await self._client.fetch_transactions(account_id, since_ts, limit)

    async def simulate_webhook_delivery(
        self, 
        account_id: str, 
        transaction: Dict[str, Any]
    ) -> bool:
        """
        Simulate webhook delivery (mock only)

        Args:
            account_id: Account identifier
            transaction: Transaction data

        Returns:
            bool: Success status
        """
        return await self._client.simulate_webhook_delivery(account_id, transaction)


# Helper functions

def mock_generate_sample_transactions(account_id: str, n: int) -> List[Dict[str, Any]]:
    """
    Generate sample transactions for testing

    Args:
        account_id: Account identifier
        n: Number of transactions to generate

    Returns:
        List of transaction dictionaries
    """
    transactions = []

    merchants = [
        ("SWIGGY*ORDER", "debit", (150, 500)),
        ("AMAZON PAY", "debit", (200, 2000)),
        ("UBER TRIP", "debit", (80, 300)),
        ("NETFLIX", "debit", (199, 799)),
        ("SALARY CREDIT", "credit", (30000, 80000)),
        ("ATM WITHDRAWAL", "debit", (500, 5000)),
        ("FLIPKART", "debit", (300, 1500)),
        ("ELECTRICITY BILL", "debit", (800, 3000)),
        ("DIVIDEND CREDIT", "credit", (1000, 5000))
    ]

    for i in range(n):
        merchant, tx_type, amount_range = random.choice(merchants)
        amount = round(random.uniform(amount_range[0], amount_range[1]), 2)

        # Generate timestamp within last 30 days
        days_ago = random.randint(0, 30)  
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)

        timestamp = datetime.utcnow() - timedelta(
            days=days_ago, 
            hours=hours_ago, 
            minutes=minutes_ago
        )

        transaction = {
            "id": f"tx_generated_{account_id}_{i+1:03d}",
            "ts": timestamp.isoformat() + "+05:30",
            "amount": amount,
            "type": tx_type,
            "raw_desc": f"{merchant}-{random.randint(100000, 999999)}",
            "account_id": account_id
        }

        transactions.append(transaction)

    # Sort by timestamp (newest first)
    transactions.sort(key=lambda x: x["ts"], reverse=True)

    return transactions


# Global client instance
aa_client = AAClient()