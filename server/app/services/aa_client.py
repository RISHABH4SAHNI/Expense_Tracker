"""
Setu Account Aggregator Sandbox Client Mock

This module provides a lightweight mock implementation of the Setu AA client
for development and testing purposes. It generates realistic sample transaction
data and simulates the AA consent flow.

PRODUCTION REPLACEMENT GUIDE:
============================
To replace with real Setu/Finvu client:

1. Install Setu AA SDK: pip install setu-aa-python-sdk
2. Replace SetuSandboxClient with SetuAAClient
3. Update environment variables:
   - SETU_CLIENT_ID
   - SETU_CLIENT_SECRET  
   - SETU_BASE_URL
   - SETU_REDIRECT_URL
4. Implement real OAuth consent flow
5. Handle real FIP (Financial Information Provider) responses
6. Add proper error handling and retries
7. Implement data encryption/decryption for FI data

Real implementation would look like:
```python
from setu import SetuAAClient

client = SetuAAClient(
    client_id=os.getenv("SETU_CLIENT_ID"),
    client_secret=os.getenv("SETU_CLIENT_SECRET"),
    base_url=os.getenv("SETU_BASE_URL")
)

# Real consent creation
consent = await client.create_consent(
    user_id=user_id,
    fip_ids=["HDFC", "ICICI", "SBI"],
    data_range={"from": from_date, "to": to_date}
)

# Real data fetch
data = await client.fetch_financial_information(
    consent_handle=consent_handle,
    data_session_id=session_id
)
```
"""

import asyncio
import uuid
import random
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from app.models.pydantic_models import TransactionIn, TransactionType

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class ConsentResponse:
    """Mock consent response from AA"""
    consent_handle: str
    consent_id: str
    status: str
    user_id: str
    account_ids: List[str]
    expires_at: datetime
    redirect_url: str

@dataclass
class AccountInfo:
    """Mock account information"""
    account_id: str
    account_number: str
    ifsc: str
    bank_name: str
    account_type: str
    branch: str
    balance: Decimal

class SetuSandboxClient:
    """
    Mock Setu Account Aggregator client for development and testing.
    
    This class simulates the Setu AA API responses with realistic data
    for development purposes. In production, replace this with the actual
    Setu AA SDK client.
    """
    
    def __init__(self, client_id: str = None, client_secret: str = None, base_url: str = None):
        """
        Initialize mock Setu AA client
        
        Args:
            client_id: Mock client ID (not used in sandbox)
            client_secret: Mock client secret (not used in sandbox)  
            base_url: Mock base URL (not used in sandbox)
        """
        self.client_id = client_id or "mock_client_id"
        self.client_secret = client_secret or "mock_client_secret"
        self.base_url = base_url or "https://sandbox.setu.co"
        
        # Mock data for realistic responses
        self.mock_banks = [
            {"name": "HDFC Bank", "ifsc_prefix": "HDFC0", "id": "HDFC"},
            {"name": "ICICI Bank", "ifsc_prefix": "ICIC0", "id": "ICICI"},
            {"name": "State Bank of India", "ifsc_prefix": "SBIN0", "id": "SBI"},
            {"name": "Axis Bank", "ifsc_prefix": "UTIB0", "id": "AXIS"},
            {"name": "Kotak Mahindra Bank", "ifsc_prefix": "KKBK0", "id": "KOTAK"}
        ]
        
        self.mock_merchants = [
            # Food & Dining
            ("SWIGGY*ORDER", "food", [150, 400]),
            ("ZOMATO*DELIVERY", "food", [200, 600]),
            ("MCDONALDS", "food", [250, 500]),
            ("STARBUCKS", "food", [300, 800]),
            ("DOMINOS PIZZA", "food", [400, 800]),
            
            # Shopping
            ("AMAZON PAY", "shopping", [500, 3000]),
            ("FLIPKART", "shopping", [800, 5000]),
            ("BIG BAZAAR", "shopping", [1000, 4000]),
            ("RELIANCE DIGITAL", "shopping", [2000, 15000]),
            ("MYNTRA", "shopping", [800, 3000]),
            
            # Transport
            ("UBER TRIP", "transport", [80, 400]),
            ("OLA CABS", "transport", [60, 350]),
            ("IRCTC", "transport", [400, 2000]),
            ("INDIAN OIL PETROL", "transport", [1000, 3000]),
            ("METRO CARD RECHARGE", "transport", [100, 500]),
            
            # Bills & Utilities
            ("BSES ELECTRICITY", "bills", [800, 3000]),
            ("RELIANCE JIO", "bills", [200, 800]),
            ("AIRTEL POSTPAID", "bills", [300, 1200]),
            ("MAHANAGAR GAS", "bills", [500, 2000]),
            ("VODAFONE IDEA", "bills", [250, 900]),
            
            # Entertainment
            ("NETFLIX", "entertainment", [199, 799]),
            ("AMAZON PRIME", "entertainment", [129, 1499]),
            ("BOOKMYSHOW", "entertainment", [200, 800]),
            ("SPOTIFY", "entertainment", [119, 179]),
            ("HOTSTAR", "entertainment", [299, 1499]),
            
            # Healthcare
            ("APOLLO PHARMACY", "healthcare", [200, 1500]),
            ("PRACTO", "healthcare", [300, 1000]),
            ("MEDPLUS", "healthcare", [150, 800]),
            ("1MG", "healthcare", [100, 2000]),
            
            # Income
            ("SALARY CREDIT", "salary", [25000, 150000]),
            ("INTEREST CREDIT", "investment", [100, 5000]),
            ("DIVIDEND CREDIT", "investment", [500, 10000]),
        ]
        
        logger.info("🏦 Initialized Setu Sandbox Client (Mock)")
    
    async def simulate_consent_flow(self, user_id: str) -> ConsentResponse:
        """
        Simulate the AA consent flow for a user
        
        In production, this would:
        1. Create consent request with Setu
        2. Redirect user to bank login
        3. Handle consent approval/rejection
        4. Return consent handle for data fetching
        
        Args:
            user_id: User identifier
            
        Returns:
            ConsentResponse: Mock consent response with handle and account IDs
        """
        logger.info(f"🔄 Simulating consent flow for user: {user_id}")
        
        # Simulate API delay
        await asyncio.sleep(0.5)
        
        # Generate mock consent response
        consent_handle = f"consent_{uuid.uuid4().hex[:12]}"
        consent_id = f"consent_id_{uuid.uuid4().hex[:8]}"
        
        # Generate 2-3 mock accounts for the user
        num_accounts = random.randint(2, 3)
        account_ids = []
        
        for i in range(num_accounts):
            bank = random.choice(self.mock_banks)
            account_id = f"{bank['id'].lower()}_{user_id}_{i+1}"
            account_ids.append(account_id)
        
        consent = ConsentResponse(
            consent_handle=consent_handle,
            consent_id=consent_id,
            status="ACTIVE",
            user_id=user_id,
            account_ids=account_ids,
            expires_at=datetime.utcnow() + timedelta(days=90),
            redirect_url=f"https://your-app.com/consent/callback?handle={consent_handle}"
        )
        
        logger.info(f"✅ Consent approved for {len(account_ids)} accounts: {account_ids}")
        return consent
    
    async def get_account_info(self, account_id: str) -> AccountInfo:
        """
        Get mock account information
        
        Args:
            account_id: Account identifier
            
        Returns:
            AccountInfo: Mock account details
        """
        # Extract bank info from account_id
        bank_id = account_id.split('_')[0].upper()
        bank = next((b for b in self.mock_banks if b['id'] == bank_id), self.mock_banks[0])
        
        account_info = AccountInfo(
            account_id=account_id,
            account_number=f"{random.randint(10000000, 99999999)}",
            ifsc=f"{bank['ifsc_prefix']}{random.randint(100000, 999999)}",
            bank_name=bank['name'],
            account_type=random.choice(["SAVINGS", "CURRENT"]),
            branch=f"{bank['name']} Branch {random.randint(1, 100)}",
            balance=Decimal(random.randint(5000, 500000))
        )
        
        return account_info
    
    async def fetch_transactions_for_account(
        self, 
        account_id: str, 
        since: datetime,
        until: Optional[datetime] = None
    ) -> List[TransactionIn]:
        """
        Fetch transactions for a specific account from the mock AA
        
        In production, this would:
        1. Use consent handle to fetch encrypted FI data
        2. Decrypt transaction data
        3. Parse bank-specific formats
        4. Return standardized transaction objects
        
        Args:
            account_id: Account identifier from consent
            since: Fetch transactions from this date
            until: Fetch transactions until this date (default: now)
            
        Returns:
            List[TransactionIn]: List of transaction objects
        """
        logger.info(f"📊 Fetching transactions for account: {account_id} since {since}")
        
        # Simulate API delay
        await asyncio.sleep(1.0)
        
        if until is None:
            until = datetime.utcnow()
        
        transactions = []
        
        # Generate 5-15 realistic transactions
        num_transactions = random.randint(5, 15)
        
        for i in range(num_transactions):
            # Random transaction date within the range
            days_diff = (until - since).days
            random_days = random.randint(0, max(1, days_diff))
            tx_date = since + timedelta(days=random_days)
            tx_date = tx_date.replace(
                hour=random.randint(6, 23),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
                tzinfo=timezone(timedelta(hours=5, minutes=30))  # IST
            )
            
            # Choose random merchant and transaction type
            merchant, category, amount_range = random.choice(self.mock_merchants)
            amount = Decimal(random.uniform(amount_range[0], amount_range[1]))
            amount = round(amount, 2)
            
            # Determine transaction type (mostly debits, some credits for salary/interest)
            tx_type = TransactionType.CREDIT if category in ["salary", "investment"] else TransactionType.DEBIT
            
            # Generate unique transaction ID
            tx_id = f"tx_{account_id}_{uuid.uuid4().hex[:8]}_{i}"
            
            transaction = TransactionIn(
                id=tx_id,
                ts=tx_date,
                amount=amount,
                type=tx_type,
                raw_desc=f"{merchant} - {tx_date.strftime('%d%m%Y')}",
                account_id=account_id
            )
            
            transactions.append(transaction)
        
        # Sort by date (newest first)
        transactions.sort(key=lambda x: x.ts, reverse=True)
        
        logger.info(f"✅ Generated {len(transactions)} mock transactions for {account_id}")
        return transactions

# Global client instance
aa_client = SetuSandboxClient()
