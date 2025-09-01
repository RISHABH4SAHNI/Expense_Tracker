# Transaction Parser Microservice

A focused REST API microservice for parsing messy bank transaction descriptions and extracting structured information like merchant names, transaction types, and cleaned descriptions.

## 🎯 Purpose

Clean up messy bank descriptions like:
- `NEFT-AXIS BANK-1234-UPI-FOODPANDA` → extract merchant: "FoodPanda", type: "NEFT"
- `UPI-AMZN12345678-Shopping` → extract merchant: "Amazon", type: "UPI"
- `ATM WDL HDFC BANK 12:34:56` → extract type: "ATM", no merchant

## 🚀 Quick Start

### 1. Start the Microservice

```bash
# Start server on port 8001
python transaction_parser.py

# Or use the runner script
python run_transaction_parser.py
```

### 2. Test the Service

```bash
# Run tests against running server
python run_transaction_parser.py --test

# Run comprehensive test suite
python -m pytest test_transaction_parser.py -v
```

### 3. API Documentation

Visit `http://localhost:8001/docs` for interactive Swagger documentation.

## 📊 API Usage

### Parse Single Transaction

**POST** `/parse`

```json
{
  "raw_text": "NEFT-AXIS BANK-1234-UPI-FOODPANDA",
  "amount": 450.50,
  "date": "2024-01-15T10:30:00Z"
}
```

**Response:**
```json
{
  "merchant": "FoodPanda",
  "amount": 450.50,
  "date": "2024-01-15T10:30:00Z",
  "raw_text": "NEFT-AXIS BANK-1234-UPI-FOODPANDA",
  "transaction_type": "NEFT",
  "confidence": 0.85,
  "cleaned_description": "FOODPANDA",
  "parsing_method": "regex_dictionary"
}
```

### Parse Multiple Transactions

**POST** `/parse/batch`

```json
[
  {
    "raw_text": "UPI-AMZN123-Payment",
    "amount": 199.99
  },
  {
    "raw_text": "NEFT-ZOMATO456-Food",
    "amount": 350.00
  }
]
```

**Response:** Array of parsed transactions

### Health Check

**GET** `/health`

```json
{
  "status": "healthy",
  "service": "transaction-parser",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🔍 Parsing Features

### Transaction Type Detection

Automatically detects transaction types from patterns:

- **UPI**: `UPI-`, `UPI/`, `via UPI`
- **NEFT**: `NEFT-`, `NEFT/`, `neft transfer`
- **IMPS**: `IMPS-`, `IMPS/`, `imps payment`
- **ATM**: `ATM WDL`, `atm withdrawal`
- **POS**: `POS PURCHASE`, `pos terminal`
- **RTGS**: `RTGS-`, `rtgs transfer`
- **Net Banking**: `NET BANKING`, `NETBANKING`
- **Debit/Credit Card**: `DEBIT CARD`, `CREDIT CARD`
- **Cash**: `CASH`
- **Other**: Unknown transaction types

### Merchant Extraction

Recognizes popular merchants using regex patterns:

#### E-commerce
- Amazon (AMZN, AMAZON)
- Flipkart, Myntra, Nykaa, Meesho, Ajio

#### Food Delivery
- Zomato, Swiggy, Uber Eats, FoodPanda, Dunzo
- Domino's, Pizza Hut, McDonald's, KFC

#### Transportation
- Uber, Ola, Metro, IRCTC, Rapido
- Goibibo, MakeMyTrip

#### Utilities & Bills
- Airtel, Jio, Vodafone, BSNL
- Tata Power, Adani Power, BESCOM, MSEB

#### Entertainment
- Netflix, Amazon Prime, Disney+ Hotstar
- Spotify, YouTube Premium, SonyLIV, ZEE5

#### Finance & Payments
- Paytm, PhonePe, Google Pay
- MobiKwik, FreeCharge

#### Retail & Grocery
- DMart, BigBasket, Blinkit (Grofers)
- Reliance, Spencer's, MORE, EasyDay

### Text Cleaning Rules

The parser applies multiple cleaning rules:

1. **Remove transaction prefixes**: `UPI-`, `NEFT-`, `IMPS-`, etc.
2. **Remove bank names**: `HDFC BANK`, `AXIS BANK`, `SBI`, etc.
3. **Remove transaction IDs**: Long numeric sequences (8+ digits)
4. **Remove timestamps**: `12:34:56`, `01/02/2024`
5. **Remove suffixes**: `REF123`, `TXN456`, `-789`
6. **Normalize separators**: Convert `/`, `-` to spaces
7. **Clean whitespace**: Multiple spaces to single space

### Confidence Scoring

The parser assigns confidence scores based on parsing success:

- **0.85**: High confidence (merchant found + transaction type detected)
- **0.70**: Medium confidence (merchant found only)
- **0.50**: Low confidence (transaction type detected only)
- **0.30**: Minimal confidence (basic cleaning only)

## 🧪 Testing Examples

Run the test suite to see parsing in action:

```bash
python run_transaction_parser.py --test
```

Example test cases:

| Input | Expected Merchant | Expected Type | Confidence |
|-------|------------------|---------------|------------|
| `NEFT-AXIS BANK-1234-UPI-FOODPANDA` | FoodPanda | NEFT | 0.85 |
| `UPI-AMZN12345678-Shopping` | Amazon | UPI | 0.85 |
| `IMPS-ZOMATO87654321-Food` | Zomato | IMPS | 0.85 |
| `NETFLIX SUBSCRIPTION` | Netflix | OTHER | 0.70 |
| `ATM WDL HDFC BANK` | None | ATM | 0.50 |
| `Unknown Payment` | None | OTHER | 0.30 |

## 🔧 Integration

### With Existing Codebase

The microservice is designed to integrate with your existing transaction processing:

```python
import requests

# Parse transaction in your existing code
response = requests.post("http://localhost:8001/parse", json={
    "raw_text": transaction.raw_desc,
    "amount": float(transaction.amount),
    "date": transaction.ts.isoformat()
})

if response.status_code == 200:
    parsed = response.json()
    transaction.merchant = parsed["merchant"]
    transaction.transaction_type = parsed["transaction_type"]
    transaction.confidence = parsed["confidence"]
```

### Future LLM Integration

The service is designed to be modular. You can easily plug in LLM-based parsing:

```python
# In TransactionParser.parse() method
if confidence < 0.7:
    # Fallback to LLM for better parsing
    llm_result = await llm_client.parse_transaction(cleaned_description)
    if llm_result.confidence > confidence:
        return llm_result
```

## 🛠 Development

### Running Tests

```bash
# Run all tests
python -m pytest test_transaction_parser.py -v

# Run specific test class
python -m pytest test_transaction_parser.py::TestMerchantExtraction -v

# Run with coverage
python -m pytest test_transaction_parser.py --cov=transaction_parser
```

### Adding New Merchants

Add new merchant patterns to `MERCHANT_PATTERNS` in `transaction_parser.py`:

```python
MERCHANT_PATTERNS = {
    # Existing patterns...
    r'NEWMERCHANT|NEW\s*MERCHANT': "New Merchant Name",
}
```

### Server Configuration

The microservice runs on port 8001 by default. Configure as needed:

```python
# Change port in transaction_parser.py
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)  # Custom port
