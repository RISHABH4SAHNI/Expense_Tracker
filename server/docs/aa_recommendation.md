# Account Aggregator Real Integration Checklist

This document provides a step-by-step checklist for migrating from mock to real Account Aggregator (AA) provider integration. Follow these steps when you get permission from your AA provider (Setu, Finvu, etc.).

## 📋 Pre-Integration Requirements

Before starting the migration, ensure you have:

- [ ] **AA Provider Account**: Approved sandbox/production account with Setu, Finvu, or other provider
- [ ] **API Credentials**: Client ID, Client Secret, API Keys from the provider
- [ ] **Webhook URL**: Your production webhook endpoint URL accessible to the provider
- [ ] **SSL Certificate**: Valid HTTPS certificate for webhook security
- [ ] **RBI Compliance**: Ensure your application meets RBI AA guidelines
- [ ] **Audit Logs**: Our audit system is already implemented ✅

---

## 🚀 Step-by-Step Migration Guide

### Phase 1: Environment Configuration

#### 1.1 Update Environment Variables ⚠️ **CRITICAL**

Update your `.env` file with real AA provider credentials:

```bash
# Switch to real AA mode
USE_REAL_AA=true

# Real AA Provider Configuration (replace mock values)
AA_BASE_URL=https://api.setu.co/v2  # Or your provider's URL
AA_API_KEY=your_real_api_key_from_setu
AA_SECRET=your_real_client_secret_from_setu

# Security Configuration
AA_WEBHOOK_SECRET=your_webhook_secret_from_provider
AA_ENCRYPTION_KEY=generate_new_32_char_encryption_key
AA_ENCRYPTION_SALT=generate_new_salt_value

# Disable development routes
DEV_MODE=false
```

**✅ Verification**: Check that `is_real_aa()` returns `True` in your configuration.

#### 1.2 Install Real AA SDK

Choose your provider's SDK:

```bash
# For Setu
pip install setu-aa-python-sdk

# For Finvu
pip install finvu-aa-python-sdk

# For other providers, check their documentation
```

Update `requirements.txt`:
```txt
setu-aa-python-sdk>=1.0.0  # Add your provider's SDK
```

---

### Phase 2: Authentication & Security

#### 2.1 Implement Request Signing 🔐

Real AA providers require HMAC-SHA256 request signing. Update `app/services/aa_client.py`:

```python
import hmac
import hashlib
from datetime import datetime

def _sign_request(self, method: str, path: str, body: str = "") -> Dict[str, str]:
    """Sign AA API request with HMAC-SHA256"""
    timestamp = str(int(datetime.utcnow().timestamp()))
    
    # Create signature string
    string_to_sign = f"{method}|{path}|{body}|{timestamp}"
    
    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        self.aa_secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return {
        "Authorization": f"Bearer {self.aa_api_key}",
        "X-Timestamp": timestamp,
        "X-Signature": signature,
        "Content-Type": "application/json"
    }
```

#### 2.2 Implement Webhook Signature Verification 🔐

Add webhook signature verification in `app/routes/aa.py`:

```python
def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature from AA provider"""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

@router.post("/webhook")
async def aa_webhook_handler(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Signature", "")
    
    if not verify_webhook_signature(payload, signature, AA_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Process webhook...
```

#### 2.3 Implement Replay Protection 🛡️

Add webhook replay protection:

```python
# In webhook handler
timestamp = request.headers.get("X-Timestamp")
if not timestamp:
    raise HTTPException(status_code=400, detail="Missing timestamp")

# Check if timestamp is within acceptable range (5 minutes)
now = datetime.utcnow().timestamp()
if abs(now - int(timestamp)) > 300:
    raise HTTPException(status_code=400, detail="Request too old")

# Store and check webhook ID to prevent replay
webhook_id = request.headers.get("X-Webhook-ID")
# Check against your cache/database for duplicate webhook_id
```

---

### Phase 3: Replace Mock Implementation

#### 3.1 Update AA Client Methods 🔄

Replace mock methods in `app/services/aa_client.py` with real API calls:

**Before (Mock)**:
```python
async def start_consent(self, user_id: str) -> ConsentResponse:
    # Mock consent creation
    ref_id = f"mock_consent_{uuid.uuid4().hex[:8]}"
    return ConsentResponse(
        consent_url=f"https://mock-aa.example.com/consent/{ref_id}",
        ref_id=ref_id
    )
```

**After (Real)**:
```python
async def start_consent(self, user_id: str) -> ConsentResponse:
    """Start real consent flow with AA provider"""
    async with httpx.AsyncClient() as client:
        payload = {
            "user_id": user_id,
            "fip_ids": ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK"],  # Real bank FIP IDs
            "data_range": {
                "from": (datetime.utcnow() - timedelta(days=365)).isoformat(),
                "to": datetime.utcnow().isoformat()
            },
            "data_types": ["DEPOSIT", "TERM_DEPOSIT"],
            "redirect_url": f"{self.base_url}/aa/callback"  # Your callback URL
        }
        
        headers = self._sign_request("POST", "/consent", json.dumps(payload))
        
        response = await client.post(
            f"{self.aa_base_url}/consent",
            headers=headers,
            json=payload,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Consent creation failed")
        
        data = response.json()
        return ConsentResponse(
            consent_url=data["consent_url"],
            ref_id=data["consent_id"]
        )
```

#### 3.2 Update Transaction Fetching 📊

Replace mock transaction fetching with real FI data decryption:

```python
async def fetch_transactions(
    self, 
    account_id: str, 
    since_ts: Optional[datetime] = None, 
    limit: int = 500
) -> List[Dict[str, Any]]:
    """Fetch real transactions from AA provider"""
    
    async with httpx.AsyncClient() as client:
        params = {
            "account_id": account_id,
            "limit": limit
        }
        
        if since_ts:
            params["from_date"] = since_ts.isoformat()
        
        headers = self._sign_request("GET", f"/accounts/{account_id}/transactions")
        
        response = await client.get(
            f"{self.aa_base_url}/accounts/{account_id}/transactions",
            headers=headers,
            params=params,
            timeout=60.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Transaction fetch failed")
        
        data = response.json()
        
        # Transform real AA response to your internal format
        transactions = []
        for fi_data in data.get("financial_information", []):
            for account in fi_data.get("accounts", []):
                for transaction in account.get("transactions", []):
                    transactions.append({
                        "id": transaction.get("txn_id"),
                        "account_id": account.get("linked_acc_ref"),
                        "amount": Decimal(transaction.get("amount", "0")),
                        "type": transaction.get("type", "").lower(),
                        "ts": transaction.get("value_date"),
                        "raw_desc": transaction.get("narration", ""),
                        "balance": Decimal(transaction.get("current_balance", "0"))
                    })
        
        return transactions
```

#### 3.3 Implement Consent Status Polling 🔄

```python
async def poll_consent_status(self, ref_id: str) -> str:
    """Poll real consent status from AA provider"""
    async with httpx.AsyncClient() as client:
        headers = self._sign_request("GET", f"/consent/{ref_id}/status")
        
        response = await client.get(
            f"{self.aa_base_url}/consent/{ref_id}/status",
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code != 200:
            return "failed"
        
        data = response.json()
        status = data.get("status", "").upper()
        
        # Map provider status to your internal status
        status_mapping = {
            "PENDING": AAConsentStatus.PENDING,
            "ACTIVE": AAConsentStatus.ACTIVE,
            "EXPIRED": AAConsentStatus.EXPIRED,
            "REVOKED": AAConsentStatus.REVOKED,
            "REJECTED": AAConsentStatus.FAILED
        }
        
        return status_mapping.get(status, AAConsentStatus.FAILED)
```

---

### Phase 4: Token Security & Lifecycle

#### 4.1 Implement Token Refresh 🔄

```python
async def refresh_consent_token(self, consent_id: str) -> Optional[str]:
    """Refresh expired consent token"""
    # Implementation depends on your AA provider's refresh mechanism
    # Some providers require re-consent, others support token refresh
    pass
```

#### 4.2 Move Encryption Keys to Secure Storage 🔐

**Production Security**: Move encryption keys from environment variables to AWS KMS, HashiCorp Vault, or similar:

```python
# Instead of: AA_ENCRYPTION_KEY=hardcoded_key
# Use: AWS KMS, Vault, or other key management service

async def get_encryption_key() -> str:
    """Get encryption key from secure key management service"""
    # AWS KMS example
    import boto3
    kms = boto3.client('kms')
    response = kms.decrypt(CiphertextBlob=encrypted_key)
    return response['Plaintext'].decode('utf-8')
```

---

### Phase 5: Disable Development Features

#### 5.1 Remove DEV_MODE Routes ⚠️

Ensure development routes are disabled in production:

```python
# In main.py, conditionally include dev routes
if is_dev_mode():
    from app.routes import dev_aa
    app.include_router(dev_aa.router)
    logger.warning("⚠️  Development AA routes are ENABLED")
else:
    logger.info("✅ Development routes disabled for production")
```

#### 5.2 Update Route Registration

Remove or conditionally include mock webhook endpoints:

```python
# Remove mock webhook routes in production
if not is_real_aa():
    app.include_router(dev_aa.router)  # Only in mock mode
```

---

### Phase 6: Testing & Validation

#### 6.1 Provider Sandbox Testing 🧪

1. **Test in Provider Sandbox**:
   ```bash
   USE_REAL_AA=true
   AA_BASE_URL=https://api.setu.co/sandbox  # Sandbox URL
   ```

2. **Verify Core Flows**:
   - [ ] Consent creation and redirection
   - [ ] Consent status polling
   - [ ] Transaction fetching
   - [ ] Webhook receipt and processing
   - [ ] Error handling and retries

3. **Run Audit Verification**:
   ```bash
   python verify_audit.py
   ```

4. **Check Logs**:
   ```bash
   # Look for audit events with correlation IDs
   SELECT event_type, correlation_id, payload, created_at 
   FROM audit_events 
   WHERE event_type LIKE '%webhook%' 
   ORDER BY created_at DESC;
   ```

#### 6.2 Production Enablement Request 🚀

Submit production enablement request to your AA provider with:

- [ ] **Completed sandbox testing** with successful transaction flows
- [ ] **Webhook endpoint verification** (HTTPS, signature verification working)
- [ ] **Security audit completion** (encryption, request signing, etc.)
- [ ] **RBI compliance documentation**
- [ ] **Expected transaction volumes**

---

## 🎯 Final Production Checklist

Before going live:

- [ ] **Environment Variables**: All real AA credentials configured
- [ ] **Request Signing**: HMAC-SHA256 implementation working
- [ ] **Webhook Security**: Signature verification and replay protection active
- [ ] **Token Encryption**: Keys moved to secure key management
- [ ] **DEV_MODE**: Disabled (`DEV_MODE=false`)
- [ ] **Audit Logging**: Working with correlation IDs
- [ ] **Error Handling**: Comprehensive error handling and retries
- [ ] **Monitoring**: Logs and metrics configured
- [ ] **Backup Plan**: Mock mode available if needed (`USE_REAL_AA=false`)

---

## 🚨 Rollback Plan

If issues occur in production:

1. **Immediate Rollback**:
   ```bash
   USE_REAL_AA=false  # Switch back to mock mode
   ```

2. **Verify Mock Mode**:
   ```bash
   curl -X POST /aa/dev/mock-webhook  # Should work in mock mode
   ```

3. **Check Audit Logs** for error correlation IDs to debug issues

---

## 📞 Support & Documentation

- **AA Provider Documentation**: Check your provider's integration guide
- **RBI Guidelines**: [Account Aggregator Ecosystem Guidelines](https://rbi.org.in)
- **Internal Audit Logs**: Use correlation IDs to trace issues
- **Debug Mode**: Use `DEV_MODE=true` in non-production for testing

---

**⚠️ Remember**: This migration affects financial data flows. Test thoroughly in sandbox before production deployment!
