"""
Development-only Account Aggregator routes for testing and debugging.

These endpoints are only available when DEV_MODE environment variable is set to "true".
They provide utilities for testing webhook delivery and generating mock transaction data.

**WARNING: These endpoints should never be available in production!**
"""

import json
import random
import uuid
import logging
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal
from pathlib import Path

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.database import get_db
from app.deps.auth import get_current_user, AuthenticatedUser
from app.config import is_dev_mode, AA_MOCK_WEBHOOK_SECRET
from app.models.pydantic_models import TransactionType

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aa/dev", tags=["AA Development"])


def _check_dev_mode():
    """
    Check if development mode is enabled, raise 403 if not.
    """
    if not is_dev_mode():
        raise HTTPException(
            status_code=403,
            detail="Development endpoints are not available. Set DEV_MODE=true to enable."
        )


def _load_mock_transactions() -> List[Dict[str, Any]]:
    """
    Load mock transaction data from JSON file.

    Returns:
        List[Dict]: List of mock transactions

    Raises:
        HTTPException: If mock data file cannot be loaded
    """
    try:
        mock_data_path = Path(__file__).parent.parent.parent / "mock_data" / "aa_transactions.json"

        if not mock_data_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Mock data file not found. Please ensure aa_transactions.json exists."
            )

        with open(mock_data_path, 'r') as f:
            data = json.load(f)

        return data.get("sample_transactions", [])

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON in mock data file: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load mock data: {str(e)}"
        )


def _generate_webhook_signature(payload_bytes: bytes, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.

    Args:
        payload_bytes: Raw payload bytes
        secret: Webhook secret

    Returns:
        str: Signature in format "sha256=<hash>"
    """
    if not secret:
        return ""

    mac = hmac.new(
        secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    )
    return f"sha256={mac.hexdigest()}"


async def _call_webhook_endpoint(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Internally call the /aa/webhook endpoint with the given payload.

    Args:
        request: Current request object for accessing the app
        payload: Webhook payload to send

    Returns:
        Dict: Response from webhook endpoint

    Raises:
        HTTPException: If webhook call fails
    """
    try:
        import httpx

        # Convert payload to JSON bytes
        payload_json = json.dumps(payload)
        payload_bytes = payload_json.encode('utf-8')

        # Generate signature
        signature = _generate_webhook_signature(payload_bytes, AA_MOCK_WEBHOOK_SECRET or "")

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-AA-Signature": signature
        }

        # Get base URL from request
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        webhook_url = f"{base_url}/aa/webhook"

        # Make internal HTTP call
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                content=payload_bytes,
                headers=headers,
                timeout=30.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Webhook call failed: {response.text}"
                )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to call webhook endpoint: {str(e)}"
        )


@router.post("/simulate-webhook")
async def simulate_webhook(
    request: Request,
    account_id: Optional[str] = Query(None, description="Specific account ID to use, or random if not provided"),
    transaction_id: Optional[str] = Query(None, description="Specific transaction ID to use, or random if not provided"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """
    **DEV ONLY**: Simulate a webhook delivery by picking a random mock transaction and posting to /aa/webhook.

    This endpoint:
    1. Loads mock transaction data
    2. Picks a random transaction (or uses specified IDs)
    3. Formats it as a webhook payload
    4. Internally calls the /aa/webhook endpoint

    Useful for testing webhook processing without external AA provider calls.

    Args:
        account_id: Optional specific account ID to use
        transaction_id: Optional specific transaction ID to use

    Returns:
        Dict: Simulation results including webhook response

    Raises:
        HTTPException: 403 if DEV_MODE not enabled, 404 if specified transaction not found
    """
    _check_dev_mode()

    try:
        logger.info(f"Simulating webhook for user {user.id}")

        # Load mock transactions
        transactions = _load_mock_transactions()

        if not transactions:
            raise HTTPException(
                status_code=404,
                detail="No mock transactions available"
            )

        # Find or pick transaction
        selected_transaction = None

        if transaction_id and account_id:
            # Find specific transaction
            selected_transaction = next(
                (tx for tx in transactions 
                 if tx.get("id") == transaction_id and tx.get("account_id") == account_id),
                None
            )
            if not selected_transaction:
                raise HTTPException(
                    status_code=404,
                    detail=f"Transaction not found: {account_id}/{transaction_id}"
                )
        elif account_id:
            # Pick random transaction from specific account
            account_transactions = [tx for tx in transactions if tx.get("account_id") == account_id]
            if not account_transactions:
                raise HTTPException(
                    status_code=404,
                    detail=f"No transactions found for account: {account_id}"
                )
            selected_transaction = random.choice(account_transactions)
        else:
            # Pick completely random transaction
            selected_transaction = random.choice(transactions)

        # Create webhook payload
        webhook_payload = {
            "account_id": selected_transaction["account_id"],
            "transaction": {
                "id": selected_transaction["id"],
                "ts": selected_transaction["ts"],
                "amount": selected_transaction["amount"],
                "type": selected_transaction["type"],
                "raw_desc": selected_transaction["raw_desc"]
            }
        }

        # Call webhook endpoint internally
        webhook_response = await _call_webhook_endpoint(request, webhook_payload)

        logger.info(f"Webhook simulation completed for transaction {selected_transaction['id']}")

        return {
            "status": "success",
            "message": "Webhook simulation completed",
            "simulated_transaction": selected_transaction,
            "webhook_response": webhook_response,
            "simulated_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook simulation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Webhook simulation failed: {str(e)}"
        )


@router.post("/gen-transactions")
async def generate_transactions(
    request: Request,
    account_id: str = Query(..., description="Account ID to generate transactions for"),
    count: int = Query(default=5, ge=1, le=50, description="Number of transactions to generate (1-50)"),
    days_back: int = Query(default=7, ge=1, le=90, description="Generate transactions from N days ago (1-90)"),
    persist_to_db: bool = Query(default=True, description="Whether to persist transactions to database"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """
    **DEV ONLY**: Generate N mock transactions for an account and optionally persist them.

    This endpoint:
    1. Generates realistic mock transactions based on existing patterns
    2. Optionally persists them to the database
    3. Returns the generated transaction data

    Useful for testing with more transaction data or specific scenarios.

    Args:
        account_id: Account ID to generate transactions for
        count: Number of transactions to generate (1-50)
        days_back: Generate transactions from N days ago
        persist_to_db: Whether to save transactions to database

    Returns:
        Dict: Generation results including created transactions

    Raises:
        HTTPException: 403 if DEV_MODE not enabled
    """
    _check_dev_mode()

    try:
        logger.info(f"Generating {count} mock transactions for account {account_id}")

        # Load existing mock data for patterns
        existing_transactions = _load_mock_transactions()

        # Common transaction patterns
        transaction_patterns = [
            {"type": "debit", "amount_range": (50, 500), "desc_templates": [
                "UPI-ZOMATO LIMITED-FOOD DELIVERY-UPI REF NO {ref}",
                "UPI-SWIGGY-FOOD ORDER-UPI REF NO {ref}",
                "UPI-UBER INDIA-RIDE FARE-UPI REF NO {ref}",
                "UPI-OLA CABS-RIDE PAYMENT-UPI REF NO {ref}"
            ]},
            {"type": "debit", "amount_range": (1000, 5000), "desc_templates": [
                "UPI-AMAZON PAY INDIA-SHOPPING-UPI REF NO {ref}",
                "UPI-FLIPKART-ONLINE PURCHASE-UPI REF NO {ref}",
                "IMPS-RELIANCE FRESH-GROCERY-TXN ID {ref}",
                "UPI-BIG BAZAAR-RETAIL SHOPPING-UPI REF NO {ref}"
            ]},
            {"type": "debit", "amount_range": (100, 1000), "desc_templates": [
                "UPI-NETFLIX INDIA-SUBSCRIPTION-UPI REF NO {ref}",
                "UPI-SPOTIFY INDIA-PREMIUM-UPI REF NO {ref}",
                "AUTO DEBIT-ADOBE CREATIVE CLOUD-MONTHLY",
                "UPI-APOLLO PHARMACY-MEDICINES-UPI REF NO {ref}"
            ]},
            {"type": "credit", "amount_range": (10000, 100000), "desc_templates": [
                "SALARY CREDIT-{company}-{month} 2024",
                "BONUS CREDIT-ANNUAL PERFORMANCE BONUS",
                "EXPENSE REIMBURSEMENT-COMPANY CLAIM"
            ]},
            {"type": "credit", "amount_range": (100, 2000), "desc_templates": [
                "UPI-PAYTM-CASHBACK REWARDS-UPI REF NO {ref}",
                "UPI-{merchant}-REFUND ORDER-UPI REF NO {ref}",
                "INTEREST CREDIT-SAVINGS ACCOUNT"
            ]}
        ]

        companies = ["TECH MAHINDRA", "INFOSYS", "TCS", "WIPRO", "ACCENTURE"]
        months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE"]
        merchants = ["AMAZON", "FLIPKART", "SWIGGY", "ZOMATO"]

        generated_transactions = []
        start_date = datetime.utcnow() - timedelta(days=days_back)

        for i in range(count):
            pattern = random.choice(transaction_patterns)

            # Generate random transaction details
            tx_id = f"tx_dev_{uuid.uuid4().hex[:12]}"
            tx_amount = round(random.uniform(*pattern["amount_range"]), 2)
            tx_type = pattern["type"]

            # Generate timestamp within the specified range
            random_hours = random.randint(0, days_back * 24)
            tx_timestamp = start_date + timedelta(hours=random_hours)

            # Generate description
            desc_template = random.choice(pattern["desc_templates"])
            tx_desc = desc_template.format(
                ref=random.randint(100000000000, 999999999999),
                company=random.choice(companies),
                month=random.choice(months),
                merchant=random.choice(merchants)
            )

            transaction = {
                "id": tx_id,
                "ts": tx_timestamp.isoformat(),
                "amount": tx_amount,
                "type": tx_type,
                "raw_desc": tx_desc,
                "account_id": account_id,
                "generated": True
            }

            generated_transactions.append(transaction)

        # Persist to database if requested
        persisted_count = 0
        if persist_to_db:
            for tx in generated_transactions:
                try:
                    # Check if transaction already exists
                    existing = await db.fetchval(
                        "SELECT id FROM transactions WHERE bank_transaction_id = $1",
                        tx["id"]
                    )

                    if not existing:
                        # Insert new transaction
                        await db.execute("""
                            INSERT INTO transactions (
                                bank_transaction_id, user_id, ts, amount, type,
                                raw_desc, account_id, created_at, updated_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
                        """,
                            tx["id"], user.id, 
                            datetime.fromisoformat(tx["ts"].replace('Z', '+00:00')),
                            Decimal(str(tx["amount"])), tx["type"], tx["raw_desc"],
                            account_id, datetime.utcnow()
                        )
                        persisted_count += 1

                except Exception as e:
                    logger.warning(f"Failed to persist transaction {tx['id']}: {e}")

        logger.info(f"Generated {count} transactions, persisted {persisted_count} to database")

        return {
            "status": "success",
            "message": f"Generated {count} mock transactions",
            "account_id": account_id,
            "generated_count": count,
            "persisted_count": persisted_count,
            "transactions": generated_transactions,
            "generated_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transaction generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Transaction generation failed: {str(e)}"
        )