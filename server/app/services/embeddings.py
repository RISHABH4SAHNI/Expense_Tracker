"""
Embeddings wrapper for merchant similarity search.

This module provides a flexible interface for vector similarity search that can work with:
1. Development fallback: TF-IDF or sentence transformers with in-memory storage
2. Production: SQLite-VSS (sqlite-vss) for persistent vector storage

Usage:
    embeddings = EmbeddingsIndex()
    await embeddings.init_embeddings_index("./data/merchants.db")

    # Store merchant embeddings
    await embeddings.upsert_merchant_embedding("Starbucks Coffee", vector)

    # Find similar merchants
    results = await embeddings.query_nearest(query_vector, k=5)
"""

import sqlite3
import numpy as np
import asyncio
import logging
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import json
import pickle
import os
from dataclasses import dataclass, asdict

# Development fallback imports
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Production imports - sqlite-vss
try:
    import sqlite_vss
    SQLITE_VSS_AVAILABLE = True
except ImportError:
    SQLITE_VSS_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class MerchantResult:
    """Result from merchant similarity search"""
    merchant: str
    distance: float
    score: float  # 1 - distance, higher is better

class EmbeddingsIndex:
    """
    Embeddings wrapper that provides a unified interface for merchant similarity search.

    Automatically chooses the best available backend:
    1. SQLite-VSS (preferred for production)
    2. Sentence Transformers (good for development)
    3. TF-IDF (basic fallback)
    4. Random vectors (last resort for testing)
    """

    def __init__(self):
        self.db_path: Optional[str] = None
        self.backend: str = "none"
        self.dimension: int = 384  # Default dimension for sentence transformers

        # Backend-specific storage
        self._sqlite_conn: Optional[sqlite3.Connection] = None
        self._tfidf_vectorizer: Optional[Any] = None
        self._sentence_model: Optional[Any] = None
        self._memory_store: Dict[str, np.ndarray] = {}
        self._merchant_list: List[str] = []

    async def init_embeddings_index(self, path: str) -> bool:
        """
        Initialize the embeddings index.

        Args:
            path: Path to the SQLite database file (for sqlite-vss) or directory (for other backends)

        Returns:
            True if initialization successful
        """
        self.db_path = path

        # Try to initialize backends in order of preference
        if await self._init_sqlite_vss():
            self.backend = "sqlite-vss"
            logger.info("✅ Initialized SQLite-VSS backend")
            return True
        elif await self._init_sentence_transformers():
            self.backend = "sentence-transformers"
            logger.info("✅ Initialized Sentence Transformers backend")
            return True
        elif await self._init_tfidf():
            self.backend = "tfidf"
            logger.info("✅ Initialized TF-IDF backend")
            return True
        else:
            self.backend = "random"
            logger.warning("⚠️  Using random vector backend (for testing only)")
            return True

    async def _init_sqlite_vss(self) -> bool:
        """Initialize SQLite-VSS backend"""
        if not SQLITE_VSS_AVAILABLE:
            logger.debug("SQLite-VSS not available")
            return False

        try:
            # TODO: Implement SQLite-VSS initialization
            # This is where you'd set up the sqlite-vss connection
            # For now, we'll return False to use fallback

            # Example implementation (uncomment when sqlite-vss is installed):
            # self._sqlite_conn = sqlite3.connect(self.db_path)
            # self._sqlite_conn.execute("SELECT vss_version()")  # Test connection
            # 
            # # Create merchants table with vector support
            # self._sqlite_conn.execute("""
            #     CREATE VIRTUAL TABLE IF NOT EXISTS merchant_embeddings USING vss0(
            #         merchant TEXT PRIMARY KEY,
            #         embedding(384)  -- 384-dimensional vectors
            #     )
            # """)
            # self._sqlite_conn.commit()

            return False  # Return True when implementation is ready
        except Exception as e:
            logger.debug(f"Failed to initialize SQLite-VSS: {e}")
            return False

    async def _init_sentence_transformers(self) -> bool:
        """Initialize Sentence Transformers backend"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.debug("Sentence Transformers not available")
            return False

        try:
            # Use a lightweight model for development
            self._sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.dimension = self._sentence_model.get_sentence_embedding_dimension()

            # Load existing embeddings if available
            await self._load_memory_store()
            return True
        except Exception as e:
            logger.debug(f"Failed to initialize Sentence Transformers: {e}")
            return False

    async def _init_tfidf(self) -> bool:
        """Initialize TF-IDF backend"""
        if not SKLEARN_AVAILABLE:
            logger.debug("Scikit-learn not available")
            return False

        try:
            self._tfidf_vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2)
            )
            self.dimension = 1000  # Max features

            # Load existing data if available
            await self._load_memory_store()
            return True
        except Exception as e:
            logger.debug(f"Failed to initialize TF-IDF: {e}")
            return False

    async def _load_memory_store(self):
        """Load existing embeddings from disk for memory-based backends"""
        if not self.db_path:
            return

        store_path = Path(self.db_path).parent / "embeddings_store.pkl"
        if store_path.exists():
            try:
                with open(store_path, 'rb') as f:
                    data = pickle.load(f)
                    self._memory_store = data.get('embeddings', {})
                    self._merchant_list = list(self._memory_store.keys())
                logger.info(f"Loaded {len(self._memory_store)} existing embeddings")
            except Exception as e:
                logger.warning(f"Failed to load existing embeddings: {e}")

    async def _save_memory_store(self):
        """Save embeddings to disk for memory-based backends"""
        if not self.db_path:
            return

        store_path = Path(self.db_path).parent / "embeddings_store.pkl"
        os.makedirs(store_path.parent, exist_ok=True)

        try:
            with open(store_path, 'wb') as f:
                pickle.dump({
                    'embeddings': self._memory_store,
                    'backend': self.backend,
                    'dimension': self.dimension
                }, f)
        except Exception as e:
            logger.warning(f"Failed to save embeddings: {e}")

    async def upsert_merchant_embedding(self, merchant: str, vector: Optional[np.ndarray] = None) -> bool:
        """
        Store or update a merchant embedding.

        Args:
            merchant: Merchant name/identifier
            vector: Pre-computed vector (optional, will be generated if not provided)

        Returns:
            True if successful
        """
        if not merchant:
            return False

        # Generate vector if not provided
        if vector is None:
            vector = await self._generate_embedding(merchant)

        if vector is None:
            return False

        # Store based on backend
        if self.backend == "sqlite-vss":
            return await self._upsert_sqlite_vss(merchant, vector)
        else:
            # Memory-based backends
            self._memory_store[merchant] = vector
            if merchant not in self._merchant_list:
                self._merchant_list.append(merchant)
            await self._save_memory_store()
            return True

    async def _generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding vector for text based on current backend"""
        if self.backend == "sentence-transformers" and self._sentence_model:
            return self._sentence_model.encode(text)
        elif self.backend == "tfidf" and self._tfidf_vectorizer:
            # For TF-IDF, we need to fit on all merchants first
            if not self._merchant_list:
                # First merchant, initialize with just this text
                vectors = self._tfidf_vectorizer.fit_transform([text])
                return vectors.toarray()[0]
            else:
                # Re-fit with all merchants including the new one
                all_merchants = self._merchant_list + [text] if text not in self._merchant_list else self._merchant_list
                vectors = self._tfidf_vectorizer.fit_transform(all_merchants)
                # Update existing embeddings
                for i, merchant in enumerate(all_merchants):
                    self._memory_store[merchant] = vectors.toarray()[i]
                return self._memory_store[text]
        elif self.backend == "random":
            # Random vectors for testing
            np.random.seed(hash(text) % 2**32)  # Deterministic randomness
            return np.random.normal(0, 1, self.dimension)

        return None

    async def _upsert_sqlite_vss(self, merchant: str, vector: np.ndarray) -> bool:
        """Store embedding in SQLite-VSS"""
        # TODO: Implement SQLite-VSS storage
        # Example:
        # try:
        #     self._sqlite_conn.execute(
        #         "INSERT OR REPLACE INTO merchant_embeddings (merchant, embedding) VALUES (?, ?)",
        #         (merchant, vector.tobytes())
        #     )
        #     self._sqlite_conn.commit()
        #     return True
        # except Exception as e:
        #     logger.error(f"Failed to store embedding: {e}")
        #     return False
        return False

    async def query_nearest(self, vector: np.ndarray, k: int = 5) -> List[MerchantResult]:
        """
        Find k nearest merchants to the query vector.

        Args:
            vector: Query vector
            k: Number of results to return

        Returns:
            List of MerchantResult sorted by similarity (highest first)
        """
        if self.backend == "sqlite-vss":
            return await self._query_sqlite_vss(vector, k)
        else:
            return await self._query_memory(vector, k)

    async def _query_memory(self, vector: np.ndarray, k: int) -> List[MerchantResult]:
        """Query memory-based backends"""
        if not self._memory_store:
            return []

        results = []
        for merchant, stored_vector in self._memory_store.items():
            # Calculate cosine similarity
            similarity = cosine_similarity([vector], [stored_vector])[0][0]
            distance = 1 - similarity  # Convert to distance
            results.append(MerchantResult(
                merchant=merchant,
                distance=distance,
                score=similarity
            ))

        # Sort by similarity (highest first) and return top k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]

    async def _query_sqlite_vss(self, vector: np.ndarray, k: int) -> List[MerchantResult]:
        """Query SQLite-VSS backend"""
        # TODO: Implement SQLite-VSS querying
        return []

    async def get_merchant_count(self) -> int:
        """Get total number of stored merchants"""
        if self.backend == "sqlite-vss":
            # TODO: Implement for SQLite-VSS
            return 0
        else:
            return len(self._memory_store)

    async def list_merchants(self, limit: int = 100) -> List[str]:
        """Get list of stored merchants"""
        if self.backend == "sqlite-vss":
            # TODO: Implement for SQLite-VSS
            return []
        else:
            return list(self._memory_store.keys())[:limit]

    def get_backend_info(self) -> Dict[str, Any]:
        """Get information about the current backend"""
        return {
            "backend": self.backend,
            "dimension": self.dimension,
            "db_path": self.db_path,
            "sqlite_vss_available": SQLITE_VSS_AVAILABLE,
            "sentence_transformers_available": SENTENCE_TRANSFORMERS_AVAILABLE,
            "sklearn_available": SKLEARN_AVAILABLE
        }