"""
Merchant similarity service for expense tracker.

This service provides high-level functions for:
1. Building embeddings index from existing transactions
2. Finding similar merchants for new transactions
3. Merchant name normalization and deduplication
"""

import asyncio
import logging
from typing import List, Optional, Dict, Set
import asyncpg
from .embeddings import EmbeddingsIndex, MerchantResult
import re

logger = logging.getLogger(__name__)

class MerchantSimilarityService:
    """Service for merchant similarity and normalization"""

    def __init__(self, embeddings_path: str = "./data/merchants.db"):
        self.embeddings = EmbeddingsIndex()
        self.embeddings_path = embeddings_path
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the service"""
        if self._initialized:
            return True

        success = await self.embeddings.init_embeddings_index(self.embeddings_path)
        self._initialized = success

        if success:
            logger.info(f"✅ Merchant similarity service initialized with {await self.embeddings.get_merchant_count()} merchants")
        else:
            logger.error("❌ Failed to initialize merchant similarity service")

        return success

    async def build_index_from_transactions(self, db_connection: asyncpg.Connection) -> Dict[str, int]:
        """
        Build embeddings index from existing transactions in the database.

        Args:
            db_connection: Database connection

        Returns:
            Stats about the indexing process
        """
        stats = {
            "processed": 0,
            "indexed": 0,
            "skipped": 0,
            "errors": 0
        }

        try:
            # Get all unique merchants from transactions
            query = """
                SELECT DISTINCT merchant, COUNT(*) as frequency
                FROM transactions 
                WHERE merchant IS NOT NULL 
                  AND merchant != '' 
                  AND merchant != 'null'
                GROUP BY merchant
                ORDER BY frequency DESC
            """

            merchants = await db_connection.fetch(query)
            logger.info(f"Found {len(merchants)} unique merchants to index")

            for row in merchants:
                merchant = row['merchant']
                frequency = row['frequency']
                stats["processed"] += 1

                try:
                    # Normalize merchant name
                    normalized_merchant = self.normalize_merchant_name(merchant)

                    # Create embedding
                    success = await self.embeddings.upsert_merchant_embedding(normalized_merchant)

                    if success:
                        stats["indexed"] += 1
                        if stats["indexed"] % 10 == 0:
                            logger.info(f"Indexed {stats['indexed']}/{len(merchants)} merchants")
                    else:
                        stats["errors"] += 1
                        logger.warning(f"Failed to index merchant: {merchant}")

                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"Error processing merchant '{merchant}': {e}")

        except Exception as e:
            logger.error(f"Error building index: {e}")
            stats["errors"] += 1

        logger.info(f"Index building complete: {stats}")
        return stats

    def normalize_merchant_name(self, merchant: str) -> str:
        """
        Normalize merchant name for better matching.

        Args:
            merchant: Raw merchant name

        Returns:
            Normalized merchant name
        """
        if not merchant:
            return ""

        # Convert to lowercase
        normalized = merchant.lower().strip()

        # Remove common prefixes and suffixes
        patterns_to_remove = [
            r'\*[a-z0-9]+$',  # Remove *order, *payment etc at end
            r'^[a-z]{2,4}\s+',  # Remove UPI, ACH etc at start
            r'\s+pvt\s+ltd$',   # Remove Pvt Ltd
            r'\s+ltd$',         # Remove Ltd
            r'\s+inc$',         # Remove Inc
            r'\s+llc$',         # Remove LLC
            r'\s+[0-9]+$',      # Remove trailing numbers
            r'^[0-9]+\s+',      # Remove leading numbers
        ]

        for pattern in patterns_to_remove:
            normalized = re.sub(pattern, '', normalized).strip()

        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)

        return normalized

    async def find_similar_merchants(self, merchant: str, k: int = 5) -> List[MerchantResult]:
        """
        Find similar merchants for the given merchant name.

        Args:
            merchant: Merchant name to find similarities for
            k: Number of similar merchants to return

        Returns:
            List of similar merchants with similarity scores
        """
        if not self._initialized:
            await self.initialize()

        # Normalize the input merchant
        normalized_merchant = self.normalize_merchant_name(merchant)

        # Generate embedding for the query merchant
        query_vector = await self.embeddings._generate_embedding(normalized_merchant)
        if query_vector is None:
            return []

        # Find similar merchants
        results = await self.embeddings.query_nearest(query_vector, k)

        return results

    async def suggest_merchant_normalization(self, merchant: str, threshold: float = 0.8) -> Optional[str]:
        """
        Suggest a normalized merchant name based on existing similar merchants.

        Args:
            merchant: Raw merchant name
            threshold: Minimum similarity threshold for suggestions

        Returns:
            Suggested normalized merchant name or None
        """
        similar_merchants = await self.find_similar_merchants(merchant, k=3)

        # Return the most similar merchant if it's above threshold
        if similar_merchants and similar_merchants[0].score >= threshold:
            return similar_merchants[0].merchant

        return None

    async def get_service_info(self) -> Dict:
        """Get information about the service status"""
        backend_info = self.embeddings.get_backend_info()
        merchant_count = await self.embeddings.get_merchant_count()

        return {
            "initialized": self._initialized,
            "merchant_count": merchant_count,
            "embeddings_path": self.embeddings_path,
            **backend_info
        }