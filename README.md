# Expense Tracker

Mobile-first personal finance app with AI-powered transaction parsing and Q&A capabilities.

cd /Users/rishabh.sahni/Desktop/Expense_Tracker/server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

cd /Users/rishabh.sahni/Desktop/Expense_Tracker/mobile && npx expo start



## Architecture

- **Frontend**: React Native (Expo) with local SQLite storage
- **Backend**: FastAPI with async processing
- **Database**: PostgreSQL for persistence, Redis for caching/queues
- **AI**: Llama-3 8B fallback for transaction parsing and financial Q&A
- **External APIs**: Setu Account Aggregator integration

## Tech Stack

```
Mobile App (Expo RN) ← FastAPI ← PostgreSQL + Redis ← Llama-3 8B
```

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose
- Expo CLI: `npm install -g @expo/cli`

### 1. Infrastructure Setup

```bash
# Start PostgreSQL + Redis
docker-compose up -d postgres redis

# Initialize database
docker-compose exec postgres psql -U expenseuser -d expensedb -f /docker-entrypoint-initdb.d/init_db.sql
```

### 2. Backend Setup

```bash
cd server

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Configure API keys, DB credentials

# Run FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Start RQ worker (separate terminal)
python -m app.workers.worker
```

### 3. Mobile App Setup

```bash
cd mobile

# Install dependencies
npm install

# Start Expo development server
npx expo start

# Scan QR code with Expo Go app or run on simulator
```

## Environment Variables

### Backend (.env)

```env
# Database
DATABASE_URL=postgresql://expenseuser:expensepass@localhost:5432/expensedb
REDIS_URL=redis://localhost:6379/0

# Setu Account Aggregator
SETU_CLIENT_ID=your_setu_client_id
SETU_CLIENT_SECRET=your_setu_secret
SETU_BASE_URL=https://api.setu.co/sandbox

# AI/LLM
LLAMA_MODEL_PATH=/path/to/llama-3-8b-model
OPENAI_API_KEY=your_openai_key  # fallback

# App Config
JWT_SECRET=your_jwt_secret_key
ENVIRONMENT=development
```

### Mobile (.env)

```env
API_BASE_URL=http://localhost:8000
EXPO_PUBLIC_API_URL=http://localhost:8000
```

## API Examples

### Transaction Sync

```bash
# Sync transactions from bank accounts
curl -X POST http://localhost:8000/transactions/sync \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "account_id": "acc_12345",
    "from_date": "2024-01-01",
    "to_date": "2024-01-31"
  }'
```

### Financial Q&A

```bash
# Ask questions about your finances
curl -X POST http://localhost:8000/qa \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "question": "How much did I spend on food last month?",
    "context_days": 30
  }'
```

## Project Structure

```
/mobile/                # React Native (Expo)
  /src/screens/         # HomeScreen, TransactionsScreen, ChatScreen
  /src/components/      # Reusable UI components
  /src/services/        # API client, local storage
  /src/storage/         # SQLite wrapper with secure storage

/server/                # FastAPI backend
  /app/routes/          # auth, transactions, qa endpoints
  /app/services/        # Setu client, LLM interface, parsers
  /app/workers/         # Background job processing
  /tests/               # Unit and integration tests

/infra/                 # Database migrations, Docker configs
/docs/                  # Architecture notes, API contracts
```

## Development

- **Mobile**: Hot reload with Expo, local SQLite for offline support
- **Backend**: FastAPI auto-reload, async request handling
- **Database**: PostgreSQL with Redis for caching and job queues
- **AI**: Local Llama-3 8B model with OpenAI fallback

## Testing

```bash
# Backend tests
cd server && python -m pytest tests/

# Mobile tests
cd mobile && npm test


/README.md
/.github/workflows/ci.yml
/docker-compose.yml
/infra/init_db.sql

/mobile/                # React Native (Expo)
  /package.json
  /app.json
  /src/
    /App.js
    /screens/
      HomeScreen.js
      TransactionsScreen.js
      ChatScreen.js
    /components/
      TransactionCard.js
    /services/
      api.js
      storage.js
    /storage/
      db.js        # sqlite wrapper (expo-sqlite + secure storage)
    /llm/
      llm_stub.js  # local LLM-call stubs

/server/                # FastAPI backend
  /requirements.txt
  /Dockerfile
  /main.py
  /app/
    /routes/
      auth.py
      transactions.py
      qa.py
    /models/
      pydantic_models.py
    /services/
      aa_client.py      # Setu sandbox/mock client
      parser.py         # regex -> merchant KB -> LLM fallback
      llm_client.py     # Llama-3 stub interface
      embeddings.py     # sqlite-vss or server vector store wrapper
    /workers/
      worker.py         # RQ worker
  /tests/
    test_parser.py

/docs/                 # architecture notes, API contracts
