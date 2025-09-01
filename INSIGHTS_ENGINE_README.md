# Financial Insights Engine 🧠💰

An advanced RAG-based microservice that translates natural language questions about financial data into SQL queries and provides intelligent insights with supporting transaction data.

## Features 🚀

- **Natural Language Processing**: Ask questions in plain English about your spending patterns
- **SQL Query Generation**: Automatically converts queries to optimized SQL using LLM + pattern matching
- **RAG Integration**: Retrieval-Augmented Generation for contextual financial insights
- **Multi-dimensional Analysis**: Category, merchant, time-based, and comparative analysis
- **Supporting Evidence**: Returns relevant transactions that support the insights
- **High Performance**: Optimized query patterns with fallback to LLM for complex queries

## Architecture 🏗️

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Natural        │    │   Insights       │    │   PostgreSQL    │
│  Language       │───▶│   Engine         │───▶│   Database      │
│  Query          │    │   (RAG + LLM)    │    │   (Transactions)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Structured     │
                       │   Response       │
                       │   + Evidence     │
                       └──────────────────┘
```

### Components

1. **Query Processing Pipeline**
   - Natural language preprocessing
   - Pattern matching for common queries
   - LLM-based SQL generation for complex queries
   - Query optimization and validation

2. **Knowledge Base**
   - Database schema context
   - Query pattern library
   - Financial domain knowledge
   - Category and merchant mappings

3. **Response Generation**
   - Natural language answer synthesis
   - Supporting transaction retrieval
   - Confidence scoring
   - Metadata extraction

## Installation 🛠️

### Prerequisites

- Python 3.8+
- PostgreSQL database with transaction data
- Existing FastAPI application infrastructure

### Setup

1. **Install dependencies** (already in your requirements.txt):
```bash
pip install fastapi uvicorn asyncpg pydantic httpx
pip install scikit-learn sentence-transformers  # For embeddings
```

2. **Start the insights engine**:
```bash
python insights_engine.py
```

The service will start on `http://localhost:8001`

3. **Test the service**:
```bash
python test_insights_engine.py
```

## API Endpoints 📡

### POST `/insights`
Process natural language financial queries.

**Request:**
```json
{
  "question": "How much did I spend on food in July?",
  "user_id": "user-123",
  "time_range_days": 30,
  "include_supporting_data": true,
  "max_transactions": 10
}
```

**Response:**
```json
{
  "question": "How much did I spend on food in July?",
  "answer": "You spent ₹12,450.00 on food in July across 23 transactions, averaging ₹541.30 per transaction.",
  "confidence": 0.95,
  "supporting_transactions": [
    {
      "id": "txn_001",
      "date": "2024-07-15T10:30:00Z",
      "amount": 450.0,
      "type": "debit",
      "description": "ZOMATO ORDER #12345",
      "merchant": "Zomato",
      "category": "food"
    }
  ],
  "analysis_metadata": {
    "result_count": 23,
    "total_amount": 12450.0,
    "avg_amount": 541.3
  },
  "sql_query": "SELECT SUM(amount)...",
  "execution_time_ms": 156.7
}
```

### GET `/insights/patterns`
Get available query patterns and examples.

### GET `/insights/schema`
Get database schema information for debugging.

### GET `/health`
Health check endpoint.

## Supported Query Types 🔍

### Spending Analysis
- "How much did I spend on food this month?"
- "What's my total spending in July?"
- "Show me expenses over ₹1000"
- "Average daily spending on transport"

### Category Analysis
- "What are my top spending categories?"
- "Break down expenses by category"
- "Food vs transport spending comparison"

### Merchant Analysis
- "Which merchants do I spend most at?"
- "Show me my Amazon purchases"
- "Top 5 restaurants by spending"

### Time-based Analysis
- "Spending trend over the last month"
- "Daily spending analysis"
- "This month vs last month comparison"

### Income Analysis
- "How much did I earn this month?"
- "Show my salary credits"
- "Total income breakdown"

### Complex Queries
- "Net cash flow for last 30 days"
- "Transactions above average spending"
- "Weekend vs weekday spending patterns"

## Integration Guide 🔧

### With Existing FastAPI App

Add to your main application's `main.py`:

```python
from fastapi import FastAPI
import httpx

# Add insights proxy endpoint
@app.post("/api/insights")
async def proxy_insights(query: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/insights",
            json=query
        )
        return response.json()
```

### With Authentication

Modify the insights engine to use your existing auth:

```python
from app.deps.auth import get_current_user

@app.post("/insights")
async def query_insights(
    query: InsightsQuery,
    db: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user)  # Add auth
):
    query.user_id = current_user.id  # Set user context
    return await insights_engine.process_query(query, db)
```

## Configuration ⚙️

### Environment Variables

```bash
# LLM Configuration
USE_REMOTE_LLM=true
LLM_ENDPOINT=http://localhost:8080/v1/llm
LLM_TIMEOUT=30

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost/expense_db

# Service Configuration
INSIGHTS_PORT=8001
LOG_LEVEL=INFO
```

### Customization

1. **Add Custom Query Patterns**: Modify `_build_query_patterns()` in `InsightsEngine`
2. **Extend Schema Context**: Update `_build_schema_context()` for new tables
3. **Custom Response Formats**: Modify response generation methods
4. **Add New Categories**: Extend the category analysis logic

## Performance Optimization 🚀

1. **Query Pattern Matching**: Fast pattern-based SQL generation for common queries
2. **Database Indexing**: Ensure proper indexes on `user_id`, `ts`, `category`, `merchant`
3. **Result Caching**: Consider adding Redis caching for frequent queries
4. **Batch Processing**: Group similar queries for efficiency

## Monitoring & Logging 📊

The service includes comprehensive logging:
- Query processing time
- Confidence scores
- SQL query generation
- Error tracking
- Usage patterns

Monitor these metrics:
- Average response time
- Query success rate
- Confidence score distribution
- Most common query patterns

## Future Enhancements 🔮

- [ ] Advanced time series analysis
- [ ] Predictive spending insights
- [ ] Budget recommendations
- [ ] Anomaly detection
- [ ] Multi-user comparative analysis
- [ ] Custom financial goals tracking
- [ ] Integration with external financial APIs
- [ ] Voice query support
- [ ] Real-time streaming insights

## Troubleshooting 🔧

### Common Issues

1. **Database Connection Issues**
   - Check database URL and credentials
   - Ensure database is running and accessible
   - Verify table schema matches expectations

2. **Low Confidence Scores**
   - Add more specific query patterns
   - Improve LLM prompts
   - Enhance preprocessing logic

3. **Slow Query Performance**
   - Add database indexes
   - Optimize SQL queries
   - Consider result caching

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
