# Merchant Embeddings System

This system provides semantic similarity search for merchant names in your expense tracker. It helps with:

- **Merchant deduplication**: Finding similar merchant names (e.g., "Starbucks Coffee" vs "Starbucks Corp")
- **Transaction categorization**: Suggesting categories based on similar merchants
- **Data cleaning**: Normalizing merchant names across transactions

## Architecture

The system uses a flexible backend approach that automatically chooses the best available option:

1. **SQLite-VSS** (Preferred for production) - Fast, persistent vector storage
2. **Sentence Transformers** (Good for development) - High-quality embeddings
3. **TF-IDF** (Basic fallback) - Simple text similarity
4. **Random vectors** (Testing only) - For testing when nothing else is available

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Test the System

```bash
# Test basic functionality
python test_embeddings.py

# Check system info
python build_embeddings.py info
```

### 3. Build Index from Database

```bash
# Build embeddings index from existing transactions
python build_embeddings.py build

# Test similarity search
python build_embeddings.py test "Starbucks"
```

## Usage in Code

### Simple Usage

```python
from app.services.embeddings import EmbeddingsIndex

# Initialize
embeddings = EmbeddingsIndex()
await embeddings.init_embeddings_index("./data/merchants.db")

# Add merchant
await embeddings.upsert_merchant_embedding("Starbucks Coffee")

# Find similar merchants
query_vector = await embeddings._generate_embedding("Starbucks Cafe")
results = await embeddings.query_nearest(query_vector, k=5)

for result in results:
    print(f"{result.merchant}: {result.score:.3f}")
```

### High-Level Service

```python
from app.services.merchant_similarity import MerchantSimilarityService

# Initialize service
service = MerchantSimilarityService()
await service.initialize()

# Build index from database
await service.build_index_from_transactions(db_connection)

# Find similar merchants
results = await service.find_similar_merchants("Starbucks", k=5)

# Get normalization suggestion
suggestion = await service.suggest_merchant_normalization("STARBUCKS*ORDER123")
```

## Production Setup with SQLite-VSS

For production deployments, install SQLite-VSS for better performance:

### 1. Install SQLite-VSS

```bash
# Using pip (if available)
pip install sqlite-vss

# Or build from source
git clone https://github.com/asg017/sqlite-vss.git
cd sqlite-vss
make loadable
```

### 2. Update Embeddings Code

The code is already structured to use SQLite-VSS automatically when available. Simply uncomment the SQLite-VSS implementation sections in `embeddings.py`:

```python
# In _init_sqlite_vss method - uncomment these lines:
self._sqlite_conn = sqlite3.connect(self.db_path)
self._sqlite_conn.execute("SELECT vss_version()")

# Create merchants table with vector support
self._sqlite_conn.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS merchant_embeddings USING vss0(
        merchant TEXT PRIMARY KEY,
        embedding(384)
    )
""")
