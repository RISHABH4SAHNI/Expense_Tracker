"""
Merchant Categorization Service

This module provides intelligent merchant categorization using embeddings and similarity matching.
It classifies merchants into predefined categories (Food, Travel, Groceries, etc.) and handles
unknown merchants with feedback mechanisms.

Added features:
- User-defined categorization overrides stored in PostgreSQL
- Personalized rules that take priority over embeddings
Features:
2. Stores embeddings in FAISS for efficient similarity search
3. Pre-trained category embeddings for quick classification
4. Fallback to "Unknown" category with user feedback flagging
5. Integration with existing merchant knowledge base
6. Continuous learning through feedback
"""

import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

import numpy as np

# Database imports
import asyncpg

# Import existing infrastructure
from .embeddings import EmbeddingsIndex, MerchantResult
from ..models.pydantic_models import TransactionCategory

# Optional FAISS import
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

logger = logging.getLogger(__name__)

class CategorizationConfidence(str, Enum):
    """Confidence levels for categorization"""
    HIGH = "high"           # > 0.8
    MEDIUM = "medium"       # 0.6 - 0.8
    LOW = "low"            # 0.4 - 0.6
    UNKNOWN = "unknown"     # < 0.4

@dataclass
class CategoryResult:
    """Result from merchant categorization"""
    category: str
    confidence: float
    confidence_level: CategorizationConfidence
    similar_merchants: List[str]
    needs_feedback: bool = False
    reasoning: Optional[str] = None

@dataclass
class CategoryEmbedding:
    """Category with its representative embedding"""
    category: str
    embedding: np.ndarray
    examples: List[str]
    keywords: List[str]

@dataclass
class FeedbackEntry:
    """User feedback for improving categorization"""
    merchant: str
    suggested_category: str
    actual_category: str
    confidence: float
    timestamp: datetime
    user_id: Optional[str] = None

@dataclass
class UserOverrideRule:
    """User-defined categorization override rule"""
    id: Optional[str] = None
    user_id: str = ""
    merchant_pattern: str = ""
    category: str = ""
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def matches_merchant(self, merchant: str) -> bool:
        """Check if this rule matches the given merchant"""
        merchant_lower = merchant.lower()
        pattern_lower = self.merchant_pattern.lower()

        # Simple pattern matching - can be enhanced with regex later
        return pattern_lower in merchant_lower or merchant_lower in pattern_lower

class MerchantCategorizer:
    """
    Intelligent merchant categorization service using embeddings and similarity matching.
    Now supports user-defined overrides stored in PostgreSQL.
    """

    def __init__(self, data_path: str = "./data/categorizer", db_pool: Optional[asyncpg.Pool] = None):
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)

        # Core components
        self.embeddings = EmbeddingsIndex()
        self.category_embeddings: Dict[str, CategoryEmbedding] = {}
        self.merchant_categories: Dict[str, str] = {}
        self.feedback_history: List[FeedbackEntry] = []

        # User overrides (cached in memory, synced with DB)
        self.user_overrides: Dict[str, List[UserOverrideRule]] = {}  # user_id -> rules
        self.db_pool = db_pool

        # FAISS index for category similarity
        self.category_index: Optional[Any] = None
        self.category_names: List[str] = []

        # Configuration
        self.similarity_threshold = 0.4  # Minimum similarity for categorization
        self.high_confidence_threshold = 0.8
        self.medium_confidence_threshold = 0.6

        self._initialized = False

        # Load existing merchant knowledge base
        self.kb_path = Path(__file__).parent / "merchant_kb.json"
        self.merchant_kb = {}

    def set_db_pool(self, db_pool: asyncpg.Pool):
        """Set the database pool for accessing user overrides"""
        self.db_pool = db_pool

    async def initialize(self) -> bool:
        """Initialize the categorizer with embeddings and category data"""
        if self._initialized:
            return True

        try:
            # Initialize embeddings backend
            embeddings_path = str(self.data_path / "embeddings.db")
            if not await self.embeddings.init_embeddings_index(embeddings_path):
                logger.error("Failed to initialize embeddings backend")
                return False

            # Load merchant knowledge base
            await self._load_merchant_kb()

            # Initialize category embeddings
            await self._initialize_category_embeddings()

            # Load existing merchant categories and feedback
            await self._load_merchant_categories()
            await self._load_feedback_history()

            # Initialize database tables for user overrides
            await self._init_user_overrides_table()

            self._initialized = True
            logger.info(f"✅ Merchant categorizer initialized with {len(self.category_embeddings)} categories")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize categorizer: {e}")
            return False

    async def _init_user_overrides_table(self):
        """Initialize the user_categorization_overrides table in PostgreSQL"""
        if not self.db_pool:
            logger.warning("No database pool provided, user overrides will not be available")
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_categorization_overrides (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        merchant_pattern VARCHAR(255) NOT NULL,
                        category transaction_category NOT NULL,
                        is_active BOOLEAN DEFAULT true,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create indexes for performance
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_overrides_user_id 
                    ON user_categorization_overrides(user_id)
                """)

                logger.info("✅ User categorization overrides table initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize user overrides table: {e}")

    async def _load_merchant_kb(self):
        """Load existing merchant knowledge base"""
        try:
            if self.kb_path.exists():
                with open(self.kb_path, 'r') as f:
                    self.merchant_kb = json.load(f)
                logger.info(f"Loaded merchant KB with {len(self.merchant_kb.get('merchant_patterns', {}))} pattern groups")
        except Exception as e:
            logger.warning(f"Could not load merchant KB: {e}")
            self.merchant_kb = {}

    async def _initialize_category_embeddings(self):
        """Initialize embeddings for each transaction category"""

        # Define category keywords and examples for better embeddings
        category_definitions = {
            TransactionCategory.FOOD: {
                "keywords": ["restaurant", "food", "dining", "cafe", "pizza", "burger", "coffee", "delivery", "takeout", "meal"],
                "examples": ["McDonald's", "Starbucks", "Zomato", "Swiggy", "Pizza Hut", "KFC", "Domino's", "restaurant", "cafe", "food delivery"]
            },
            TransactionCategory.TRANSPORT: {
                "keywords": ["transport", "travel", "taxi", "uber", "flight", "train", "bus", "metro", "fuel", "petrol", "gas"],
                "examples": ["Uber", "Ola", "IRCTC", "IndiGo", "metro", "bus", "taxi", "petrol pump", "gas station", "airline"]
            },
            TransactionCategory.SHOPPING: {
                "keywords": ["shopping", "store", "mall", "retail", "clothes", "electronics", "grocery", "supermarket", "online"],
                "examples": ["Amazon", "Flipkart", "Myntra", "BigBasket", "supermarket", "mall", "retail store", "electronics", "clothing"]
            },
            TransactionCategory.ENTERTAINMENT: {
                "keywords": ["entertainment", "movie", "music", "streaming", "netflix", "spotify", "games", "cinema", "theatre"],
                "examples": ["Netflix", "Spotify", "BookMyShow", "cinema", "theatre", "streaming", "music", "games", "entertainment"]
            },
            TransactionCategory.BILLS: {
                "keywords": ["bill", "utility", "electricity", "water", "gas", "internet", "phone", "mobile", "broadband", "payment"],
                "examples": ["electricity bill", "water bill", "internet", "mobile recharge", "broadband", "utility payment", "phone bill"]
            },
            TransactionCategory.HEALTHCARE: {
                "keywords": ["health", "medical", "doctor", "hospital", "pharmacy", "medicine", "clinic", "healthcare", "dental"],
                "examples": ["hospital", "pharmacy", "doctor", "medical", "healthcare", "clinic", "medicine", "dental", "health"]
            },
            TransactionCategory.EDUCATION: {
                "keywords": ["education", "school", "college", "course", "learning", "training", "university", "tuition", "books"],
                "examples": ["school fee", "college", "course", "training", "books", "education", "tuition", "university", "learning"]
            },
            TransactionCategory.SALARY: {
                "keywords": ["salary", "income", "payroll", "wages", "compensation", "payment", "credit", "earnings"],
                "examples": ["salary credit", "payroll", "wages", "income", "compensation", "earnings", "payment received"]
            },
            TransactionCategory.INVESTMENT: {
                "keywords": ["investment", "stocks", "mutual fund", "dividend", "interest", "trading", "portfolio", "sip", "finance"],
                "examples": ["dividend", "mutual fund", "stocks", "investment", "SIP", "trading", "interest", "portfolio", "finance"]
            },
            TransactionCategory.OTHER: {
                "keywords": ["transfer", "withdrawal", "deposit", "bank", "atm", "upi", "payment", "transaction"],
                "examples": ["ATM withdrawal", "bank transfer", "UPI", "NEFT", "payment", "deposit", "withdrawal", "transaction"]
            }
        }

        # Generate embeddings for each category
        for category, definition in category_definitions.items():
            # Combine keywords and examples for richer embedding
            category_text = f"{category.value} " + " ".join(definition["keywords"]) + " " + " ".join(definition["examples"])

            # Generate embedding
            embedding = await self.embeddings._generate_embedding(category_text)
            if embedding is not None:
                self.category_embeddings[category.value] = CategoryEmbedding(
                    category=category.value,
                    embedding=embedding,
                    examples=definition["examples"],
                    keywords=definition["keywords"]
                )

        # Initialize FAISS index for fast category similarity search
        await self._build_category_index()

        logger.info(f"Initialized {len(self.category_embeddings)} category embeddings")

    async def _build_category_index(self):
        """Build FAISS index for category embeddings"""
        if not FAISS_AVAILABLE or not self.category_embeddings:
            logger.info("FAISS not available or no category embeddings, using linear search")
            return

        try:
            # Get all category embeddings
            embeddings_list = []
            category_names = []

            for category, cat_emb in self.category_embeddings.items():
                embeddings_list.append(cat_emb.embedding)
                category_names.append(category)

            # Create FAISS index
            embeddings_array = np.array(embeddings_list).astype('float32')
            dimension = embeddings_array.shape[1]

            # Use L2 distance (can be converted to cosine similarity)
            self.category_index = faiss.IndexFlatL2(dimension)
            self.category_index.add(embeddings_array)
            self.category_names = category_names

            logger.info(f"Built FAISS index with {len(category_names)} categories")

        except Exception as e:
            logger.warning(f"Failed to build FAISS index: {e}")
            self.category_index = None

    async def categorize_merchant(self, merchant: str, user_id: Optional[str] = None, amount: Optional[float] = None) -> CategoryResult:
        """
        Categorize a merchant using embeddings and similarity matching.

        Args:
            merchant: Merchant name to categorize
            amount: Transaction amount (optional, for additional context)

        Returns:
            CategoryResult with predicted category and confidence
        """
        if not self._initialized:
            await self.initialize()

        # STEP 1: Check user-defined overrides first (highest priority)
        if user_id:
            override_result = await self._check_user_overrides(merchant, user_id)
            if override_result:
                return override_result

        # First check if we have this merchant in our knowledge base
        kb_result = await self._check_knowledge_base(merchant)
        if kb_result:
            return kb_result

        # Check if we've seen this merchant before
        if merchant.lower() in self.merchant_categories:
            category = self.merchant_categories[merchant.lower()]
            return CategoryResult(
                category=category,
                confidence=0.95,  # High confidence for known merchants
                confidence_level=CategorizationConfidence.HIGH,
                similar_merchants=[],
                reasoning="Previously categorized merchant"
            )

        # Generate embedding for the merchant
        merchant_embedding = await self.embeddings._generate_embedding(merchant)
        if merchant_embedding is None:
            return self._unknown_category_result(merchant, "Could not generate embedding")

        # Find most similar category
        best_category, similarity, similar_merchants = await self._find_most_similar_category(merchant_embedding, merchant)

        # Determine confidence level and whether feedback is needed
        confidence_level = self._get_confidence_level(similarity)
        needs_feedback = confidence_level == CategorizationConfidence.UNKNOWN

        if needs_feedback:
            return self._unknown_category_result(merchant, f"Low similarity ({similarity:.3f}) to known categories", similar_merchants)

        return CategoryResult(
            category=best_category,
            confidence=similarity,
            confidence_level=confidence_level,
            similar_merchants=similar_merchants,
            needs_feedback=confidence_level == CategorizationConfidence.LOW,
            reasoning=f"Similarity-based classification (similarity: {similarity:.3f})"
        )

    async def _check_user_overrides(self, merchant: str, user_id: str) -> Optional[CategoryResult]:
        """Check if user has defined any override rules for this merchant"""
        try:
            # Load user overrides if not cached
            if user_id not in self.user_overrides:
                await self._load_user_overrides(user_id)

            # Check each override rule for this user
            for rule in self.user_overrides.get(user_id, []):
                if rule.is_active and rule.matches_merchant(merchant):
                    return CategoryResult(
                        category=rule.category,
                        confidence=1.0,  # User-defined rules have highest confidence
                        confidence_level=CategorizationConfidence.HIGH,
                        similar_merchants=[],
                        needs_feedback=False,
                        reasoning=f"User-defined override rule: '{rule.merchant_pattern}' → {rule.category}"
                    )

            return None

        except Exception as e:
            logger.error(f"Error checking user overrides: {e}")
            return None

    async def _load_user_overrides(self, user_id: str):
        """Load user override rules from database"""
        if not self.db_pool:
            return

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, user_id, merchant_pattern, category, is_active, created_at, updated_at
                    FROM user_categorization_overrides 
                    WHERE user_id = $1 AND is_active = true
                    ORDER BY created_at DESC
                """, user_id)

                rules = []
                for row in rows:
                    rule = UserOverrideRule(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        merchant_pattern=row['merchant_pattern'],
                        category=row['category'],
                        is_active=row['is_active'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    rules.append(rule)

                self.user_overrides[user_id] = rules
                logger.info(f"Loaded {len(rules)} override rules for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to load user overrides: {e}")
            self.user_overrides[user_id] = []

    async def add_user_override(self, user_id: str, merchant_pattern: str, category: str) -> bool:
        """
        Add a user-defined categorization override rule.

        Args:
            user_id: User identifier
            merchant_pattern: Pattern to match against merchant names
            category: Category to assign when pattern matches

        Returns:
            True if rule was successfully added
        """
        if not self.db_pool:
            logger.error("No database pool available for adding user overrides")
            return False

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_categorization_overrides (user_id, merchant_pattern, category)
                    VALUES ($1, $2, $3)
                """, user_id, merchant_pattern, category)

                # Clear cache to force reload
                if user_id in self.user_overrides:
                    del self.user_overrides[user_id]

                logger.info(f"Added user override rule: {merchant_pattern} → {category} for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to add user override: {e}")
            return False

    async def update_user_override(self, user_id: str, rule_id: str, merchant_pattern: Optional[str] = None, 
                                  category: Optional[str] = None, is_active: Optional[bool] = None) -> bool:
        """
        Update an existing user override rule.

        Args:
            user_id: User identifier
            rule_id: Rule identifier
            merchant_pattern: New merchant pattern (optional)
            category: New category (optional)
            is_active: New active status (optional)

        Returns:
            True if rule was successfully updated
        """
        if not self.db_pool:
            logger.error("No database pool available for updating user overrides")
            return False

        # Build dynamic update query
        update_fields = []
        params = [rule_id, user_id]
        param_count = 2

        if merchant_pattern is not None:
            param_count += 1
            update_fields.append(f"merchant_pattern = ${param_count}")
            params.append(merchant_pattern)

        if category is not None:
            param_count += 1
            update_fields.append(f"category = ${param_count}")
            params.append(category)

        if is_active is not None:
            param_count += 1
            update_fields.append(f"is_active = ${param_count}")
            params.append(is_active)

        if not update_fields:
            return True  # Nothing to update

        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        try:
            async with self.db_pool.acquire() as conn:
                query = f"""
                    UPDATE user_categorization_overrides 
                    SET {', '.join(update_fields)}
                    WHERE id = $1 AND user_id = $2
                """
                result = await conn.execute(query, *params)

                # Clear cache to force reload
                if user_id in self.user_overrides:
                    del self.user_overrides[user_id]

                # Check if any rows were updated
                rows_affected = int(result.split()[-1])
                if rows_affected > 0:
                    logger.info(f"Updated user override rule {rule_id} for user {user_id}")
                    return True
                else:
                    logger.warning(f"No override rule found with id {rule_id} for user {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to update user override: {e}")
            return False

    async def delete_user_override(self, user_id: str, rule_id: str) -> bool:
        """
        Delete a user override rule.

        Args:
            user_id: User identifier
            rule_id: Rule identifier

        Returns:
            True if rule was successfully deleted
        """
        if not self.db_pool:
            logger.error("No database pool available for deleting user overrides")
            return False

        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM user_categorization_overrides 
                    WHERE id = $1 AND user_id = $2
                """, rule_id, user_id)

                # Clear cache to force reload
                if user_id in self.user_overrides:
                    del self.user_overrides[user_id]

                # Check if any rows were deleted
                rows_affected = int(result.split()[-1])
                if rows_affected > 0:
                    logger.info(f"Deleted user override rule {rule_id} for user {user_id}")
                    return True
                else:
                    logger.warning(f"No override rule found with id {rule_id} for user {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete user override: {e}")
            return False

    async def get_user_overrides(self, user_id: str) -> List[UserOverrideRule]:
        """
        Get all override rules for a user.

        Args:
            user_id: User identifier

        Returns:
            List of user override rules
        """
        await self._load_user_overrides(user_id)
        return self.user_overrides.get(user_id, [])

    async def _check_knowledge_base(self, merchant: str) -> Optional[CategoryResult]:
        """Check merchant against existing knowledge base patterns"""
        if not self.merchant_kb.get('merchant_patterns'):
            return None

        merchant_upper = merchant.upper()

        # Check all pattern groups
        for group_name, patterns in self.merchant_kb['merchant_patterns'].items():
            for pattern, data in patterns.items():
                if pattern in merchant_upper or merchant_upper in pattern:
                    confidence = data.get('confidence', 0.8)
                    category = data.get('category', 'other')

                    return CategoryResult(
                        category=category,
                        confidence=confidence,
                        confidence_level=self._get_confidence_level(confidence),
                        similar_merchants=[data.get('name', pattern)],
                        reasoning=f"Matched knowledge base pattern: {pattern}"
                    )

        return None

    async def _find_most_similar_category(self, merchant_embedding: np.ndarray, merchant: str) -> Tuple[str, float, List[str]]:
        """Find the most similar category using FAISS or linear search"""

        if self.category_index is not None and FAISS_AVAILABLE:
            return await self._faiss_similarity_search(merchant_embedding, merchant)
        else:
            return await self._linear_similarity_search(merchant_embedding, merchant)

    async def _faiss_similarity_search(self, merchant_embedding: np.ndarray, merchant: str) -> Tuple[str, float, List[str]]:
        """Use FAISS for fast similarity search"""
        try:
            # Search for nearest categories
            query_vector = merchant_embedding.reshape(1, -1).astype('float32')
            distances, indices = self.category_index.search(query_vector, k=3)

            # Convert L2 distance to cosine similarity (approximate)
            # For normalized vectors: cosine_sim ≈ 1 - (l2_distance^2 / 2)
            best_idx = indices[0][0]
            best_distance = distances[0][0]
            best_similarity = max(0.0, 1.0 - (best_distance / 2.0))  # Approximate conversion

            best_category = self.category_names[best_idx]

            # Get similar merchants from the category
            similar_merchants = self.category_embeddings[best_category].examples[:3]

            return best_category, best_similarity, similar_merchants

        except Exception as e:
            logger.warning(f"FAISS search failed: {e}, falling back to linear search")
            return await self._linear_similarity_search(merchant_embedding, merchant)

    async def _linear_similarity_search(self, merchant_embedding: np.ndarray, merchant: str) -> Tuple[str, float, List[str]]:
        """Linear search through category embeddings"""
        best_similarity = 0.0
        best_category = "other"

        for category, cat_emb in self.category_embeddings.items():
            # Calculate cosine similarity
            similarity = np.dot(merchant_embedding, cat_emb.embedding) / (
                np.linalg.norm(merchant_embedding) * np.linalg.norm(cat_emb.embedding)
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_category = category

        # Get similar merchants from the best category
        similar_merchants = self.category_embeddings[best_category].examples[:3]

        return best_category, best_similarity, similar_merchants

    def _get_confidence_level(self, similarity: float) -> CategorizationConfidence:
        """Convert similarity score to confidence level"""
        if similarity >= self.high_confidence_threshold:
            return CategorizationConfidence.HIGH
        elif similarity >= self.medium_confidence_threshold:
            return CategorizationConfidence.MEDIUM
        elif similarity >= self.similarity_threshold:
            return CategorizationConfidence.LOW
        else:
            return CategorizationConfidence.UNKNOWN

    def _unknown_category_result(self, merchant: str, reason: str, similar_merchants: List[str] = None) -> CategoryResult:
        """Create result for unknown category with feedback flag"""
        return CategoryResult(
            category="unknown",
            confidence=0.0,
            confidence_level=CategorizationConfidence.UNKNOWN,
            similar_merchants=similar_merchants or [],
            needs_feedback=True,
            reasoning=reason
        )

    async def add_feedback(self, merchant: str, correct_category: str, user_id: Optional[str] = None) -> bool:
        """
        Add user feedback to improve categorization.

        Args:
            merchant: Merchant name that was incorrectly categorized
            correct_category: The correct category provided by user
            user_id: Optional user identifier

        Returns:
            True if feedback was successfully recorded
        """
        try:
            # Get current prediction for comparison
            current_result = await self.categorize_merchant(merchant)

            # Record feedback
            feedback = FeedbackEntry(
                merchant=merchant,
                suggested_category=current_result.category,
                actual_category=correct_category,
                confidence=current_result.confidence,
                timestamp=datetime.utcnow(),
                user_id=user_id
            )

            self.feedback_history.append(feedback)

            # Update merchant categories with correct classification
            self.merchant_categories[merchant.lower()] = correct_category

            # Save feedback and categories
            await self._save_feedback_history()
            await self._save_merchant_categories()

            logger.info(f"Added feedback for merchant '{merchant}': {current_result.category} → {correct_category}")
            return True

        except Exception as e:
            logger.error(f"Failed to add feedback: {e}")
            return False

    async def _load_merchant_categories(self):
        """Load previously categorized merchants"""
        categories_file = self.data_path / "merchant_categories.json"
        try:
            if categories_file.exists():
                with open(categories_file, 'r') as f:
                    self.merchant_categories = json.load(f)
                logger.info(f"Loaded {len(self.merchant_categories)} merchant categories")
        except Exception as e:
            logger.warning(f"Could not load merchant categories: {e}")
            self.merchant_categories = {}

    async def _save_merchant_categories(self):
        """Save merchant categories to disk"""
        categories_file = self.data_path / "merchant_categories.json"
        try:
            with open(categories_file, 'w') as f:
                json.dump(self.merchant_categories, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save merchant categories: {e}")

    async def _load_feedback_history(self):
        """Load feedback history from disk"""
        feedback_file = self.data_path / "feedback_history.json"
        try:
            if feedback_file.exists():
                with open(feedback_file, 'r') as f:
                    feedback_data = json.load(f)
                    self.feedback_history = [
                        FeedbackEntry(**item) for item in feedback_data
                    ]
                logger.info(f"Loaded {len(self.feedback_history)} feedback entries")
        except Exception as e:
            logger.warning(f"Could not load feedback history: {e}")
            self.feedback_history = []

    async def _save_feedback_history(self):
        """Save feedback history to disk"""
        feedback_file = self.data_path / "feedback_history.json"
        try:
            feedback_data = [
                {**asdict(entry), 'timestamp': entry.timestamp.isoformat()}
                for entry in self.feedback_history
            ]
            with open(feedback_file, 'w') as f:
                json.dump(feedback_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save feedback history: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get categorizer statistics"""
        return {
            "initialized": self._initialized,
            "categories_count": len(self.category_embeddings),
            "known_merchants": len(self.merchant_categories),
            "feedback_entries": len(self.feedback_history),
            "backend": self.embeddings.get_backend_info(),
            "faiss_available": FAISS_AVAILABLE,
            "using_faiss": self.category_index is not None,
            "similarity_threshold": self.similarity_threshold,
            "high_confidence_threshold": self.high_confidence_threshold,
            "medium_confidence_threshold": self.medium_confidence_threshold
        }

# Global instance - will be initialized with db_pool in main.py
categorizer = MerchantCategorizer()
"""
Merchant Categorization Service

This module provides intelligent merchant categorization using embeddings and similarity matching.
It classifies merchants into predefined categories (Food, Travel, Groceries, etc.) and handles
unknown merchants with feedback mechanisms.

Added features:
- User-defined categorization overrides stored in PostgreSQL
- Personalized rules that take priority over embeddings
Features:
2. Stores embeddings in FAISS for efficient similarity search
3. Pre-trained category embeddings for quick classification
4. Fallback to "Unknown" category with user feedback flagging
5. Integration with existing merchant knowledge base
6. Continuous learning through feedback
"""

import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

import numpy as np

# Database imports
import asyncpg

# Import existing infrastructure
from .embeddings import EmbeddingsIndex, MerchantResult
from ..models.pydantic_models import TransactionCategory

# Optional FAISS import
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

logger = logging.getLogger(__name__)

class CategorizationConfidence(str, Enum):
    """Confidence levels for categorization"""
    HIGH = "high"           # > 0.8
    MEDIUM = "medium"       # 0.6 - 0.8
    LOW = "low"            # 0.4 - 0.6
    UNKNOWN = "unknown"     # < 0.4

@dataclass
class CategoryResult:
    """Result from merchant categorization"""
    category: str
    confidence: float
    confidence_level: CategorizationConfidence
    similar_merchants: List[str]
    needs_feedback: bool = False
    reasoning: Optional[str] = None

@dataclass
class CategoryEmbedding:
    """Category with its representative embedding"""
    category: str
    embedding: np.ndarray
    examples: List[str]
    keywords: List[str]

@dataclass
class FeedbackEntry:
    """User feedback for improving categorization"""
    merchant: str
    suggested_category: str
    actual_category: str
    confidence: float
    timestamp: datetime
    user_id: Optional[str] = None

@dataclass
class UserOverrideRule:
    """User-defined categorization override rule"""
    id: Optional[str] = None
    user_id: str = ""
    merchant_pattern: str = ""
    category: str = ""
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def matches_merchant(self, merchant: str) -> bool:
        """Check if this rule matches the given merchant"""
        merchant_lower = merchant.lower()
        pattern_lower = self.merchant_pattern.lower()

        # Simple pattern matching - can be enhanced with regex later
        return pattern_lower in merchant_lower or merchant_lower in pattern_lower

class MerchantCategorizer:
    """
    Intelligent merchant categorization service using embeddings and similarity matching.
    Now supports user-defined overrides stored in PostgreSQL.
    """

    def __init__(self, data_path: str = "./data/categorizer", db_pool: Optional[asyncpg.Pool] = None):
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)

        # Core components
        self.embeddings = EmbeddingsIndex()
        self.category_embeddings: Dict[str, CategoryEmbedding] = {}
        self.merchant_categories: Dict[str, str] = {}
        self.feedback_history: List[FeedbackEntry] = []

        # User overrides (cached in memory, synced with DB)
        self.user_overrides: Dict[str, List[UserOverrideRule]] = {}  # user_id -> rules
        self.db_pool = db_pool

        # FAISS index for category similarity
        self.category_index: Optional[Any] = None
        self.category_names: List[str] = []

        # Configuration
        self.similarity_threshold = 0.4  # Minimum similarity for categorization
        self.high_confidence_threshold = 0.8
        self.medium_confidence_threshold = 0.6

        self._initialized = False

        # Load existing merchant knowledge base
        self.kb_path = Path(__file__).parent / "merchant_kb.json"
        self.merchant_kb = {}

    def set_db_pool(self, db_pool: asyncpg.Pool):
        """Set the database pool for accessing user overrides"""
        self.db_pool = db_pool

    async def initialize(self) -> bool:
        """Initialize the categorizer with embeddings and category data"""
        if self._initialized:
            return True

        try:
            # Initialize embeddings backend
            embeddings_path = str(self.data_path / "embeddings.db")
            if not await self.embeddings.init_embeddings_index(embeddings_path):
                logger.error("Failed to initialize embeddings backend")
                return False

            # Load merchant knowledge base
            await self._load_merchant_kb()

            # Initialize category embeddings
            await self._initialize_category_embeddings()

            # Load existing merchant categories and feedback
            await self._load_merchant_categories()
            await self._load_feedback_history()

            # Initialize database tables for user overrides
            await self._init_user_overrides_table()

            self._initialized = True
            logger.info(f"✅ Merchant categorizer initialized with {len(self.category_embeddings)} categories")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize categorizer: {e}")
            return False

    async def _init_user_overrides_table(self):
        """Initialize the user_categorization_overrides table in PostgreSQL"""
        if not self.db_pool:
            logger.warning("No database pool provided, user overrides will not be available")
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_categorization_overrides (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        merchant_pattern VARCHAR(255) NOT NULL,
                        category transaction_category NOT NULL,
                        is_active BOOLEAN DEFAULT true,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create indexes for performance
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_overrides_user_id 
                    ON user_categorization_overrides(user_id)
                """)

                logger.info("✅ User categorization overrides table initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize user overrides table: {e}")

    async def _load_merchant_kb(self):
        """Load existing merchant knowledge base"""
        try:
            if self.kb_path.exists():
                with open(self.kb_path, 'r') as f:
                    self.merchant_kb = json.load(f)
                logger.info(f"Loaded merchant KB with {len(self.merchant_kb.get('merchant_patterns', {}))} pattern groups")
        except Exception as e:
            logger.warning(f"Could not load merchant KB: {e}")
            self.merchant_kb = {}

    async def _initialize_category_embeddings(self):
        """Initialize embeddings for each transaction category"""

        # Define category keywords and examples for better embeddings
        category_definitions = {
            TransactionCategory.FOOD: {
                "keywords": ["restaurant", "food", "dining", "cafe", "pizza", "burger", "coffee", "delivery", "takeout", "meal"],
                "examples": ["McDonald's", "Starbucks", "Zomato", "Swiggy", "Pizza Hut", "KFC", "Domino's", "restaurant", "cafe", "food delivery"]
            },
            TransactionCategory.TRANSPORT: {
                "keywords": ["transport", "travel", "taxi", "uber", "flight", "train", "bus", "metro", "fuel", "petrol", "gas"],
                "examples": ["Uber", "Ola", "IRCTC", "IndiGo", "metro", "bus", "taxi", "petrol pump", "gas station", "airline"]
            },
            TransactionCategory.SHOPPING: {
                "keywords": ["shopping", "store", "mall", "retail", "clothes", "electronics", "grocery", "supermarket", "online"],
                "examples": ["Amazon", "Flipkart", "Myntra", "BigBasket", "supermarket", "mall", "retail store", "electronics", "clothing"]
            },
            TransactionCategory.ENTERTAINMENT: {
                "keywords": ["entertainment", "movie", "music", "streaming", "netflix", "spotify", "games", "cinema", "theatre"],
                "examples": ["Netflix", "Spotify", "BookMyShow", "cinema", "theatre", "streaming", "music", "games", "entertainment"]
            },
            TransactionCategory.BILLS: {
                "keywords": ["bill", "utility", "electricity", "water", "gas", "internet", "phone", "mobile", "broadband", "payment"],
                "examples": ["electricity bill", "water bill", "internet", "mobile recharge", "broadband", "utility payment", "phone bill"]
            },
            TransactionCategory.HEALTHCARE: {
                "keywords": ["health", "medical", "doctor", "hospital", "pharmacy", "medicine", "clinic", "healthcare", "dental"],
                "examples": ["hospital", "pharmacy", "doctor", "medical", "healthcare", "clinic", "medicine", "dental", "health"]
            },
            TransactionCategory.EDUCATION: {
                "keywords": ["education", "school", "college", "course", "learning", "training", "university", "tuition", "books"],
                "examples": ["school fee", "college", "course", "training", "books", "education", "tuition", "university", "learning"]
            },
            TransactionCategory.SALARY: {
                "keywords": ["salary", "income", "payroll", "wages", "compensation", "payment", "credit", "earnings"],
                "examples": ["salary credit", "payroll", "wages", "income", "compensation", "earnings", "payment received"]
            },
            TransactionCategory.INVESTMENT: {
                "keywords": ["investment", "stocks", "mutual fund", "dividend", "interest", "trading", "portfolio", "sip", "finance"],
                "examples": ["dividend", "mutual fund", "stocks", "investment", "SIP", "trading", "interest", "portfolio", "finance"]
            },
            TransactionCategory.OTHER: {
                "keywords": ["transfer", "withdrawal", "deposit", "bank", "atm", "upi", "payment", "transaction"],
                "examples": ["ATM withdrawal", "bank transfer", "UPI", "NEFT", "payment", "deposit", "withdrawal", "transaction"]
            }
        }

        # Generate embeddings for each category
        for category, definition in category_definitions.items():
            # Combine keywords and examples for richer embedding
            category_text = f"{category.value} " + " ".join(definition["keywords"]) + " " + " ".join(definition["examples"])

            # Generate embedding
            embedding = await self.embeddings._generate_embedding(category_text)
            if embedding is not None:
                self.category_embeddings[category.value] = CategoryEmbedding(
                    category=category.value,
                    embedding=embedding,
                    examples=definition["examples"],
                    keywords=definition["keywords"]
                )

        # Initialize FAISS index for fast category similarity search
        await self._build_category_index()

        logger.info(f"Initialized {len(self.category_embeddings)} category embeddings")

    async def _build_category_index(self):
        """Build FAISS index for category embeddings"""
        if not FAISS_AVAILABLE or not self.category_embeddings:
            logger.info("FAISS not available or no category embeddings, using linear search")
            return

        try:
            # Get all category embeddings
            embeddings_list = []
            category_names = []

            for category, cat_emb in self.category_embeddings.items():
                embeddings_list.append(cat_emb.embedding)
                category_names.append(category)

            # Create FAISS index
            embeddings_array = np.array(embeddings_list).astype('float32')
            dimension = embeddings_array.shape[1]

            # Use L2 distance (can be converted to cosine similarity)
            self.category_index = faiss.IndexFlatL2(dimension)
            self.category_index.add(embeddings_array)
            self.category_names = category_names

            logger.info(f"Built FAISS index with {len(category_names)} categories")

        except Exception as e:
            logger.warning(f"Failed to build FAISS index: {e}")
            self.category_index = None

    async def categorize_merchant(self, merchant: str, user_id: Optional[str] = None, amount: Optional[float] = None) -> CategoryResult:
        """
        Categorize a merchant using embeddings and similarity matching.

        Args:
            merchant: Merchant name to categorize
            amount: Transaction amount (optional, for additional context)

        Returns:
            CategoryResult with predicted category and confidence
        """
        if not self._initialized:
            await self.initialize()

        # STEP 1: Check user-defined overrides first (highest priority)
        if user_id:
            override_result = await self._check_user_overrides(merchant, user_id)
            if override_result:
                return override_result

        # First check if we have this merchant in our knowledge base
        kb_result = await self._check_knowledge_base(merchant)
        if kb_result:
            return kb_result

        # Check if we've seen this merchant before
        if merchant.lower() in self.merchant_categories:
            category = self.merchant_categories[merchant.lower()]
            return CategoryResult(
                category=category,
                confidence=0.95,  # High confidence for known merchants
                confidence_level=CategorizationConfidence.HIGH,
                similar_merchants=[],
                reasoning="Previously categorized merchant"
            )

        # Generate embedding for the merchant
        merchant_embedding = await self.embeddings._generate_embedding(merchant)
        if merchant_embedding is None:
            return self._unknown_category_result(merchant, "Could not generate embedding")

        # Find most similar category
        best_category, similarity, similar_merchants = await self._find_most_similar_category(merchant_embedding, merchant)

        # Determine confidence level and whether feedback is needed
        confidence_level = self._get_confidence_level(similarity)
        needs_feedback = confidence_level == CategorizationConfidence.UNKNOWN

        if needs_feedback:
            return self._unknown_category_result(merchant, f"Low similarity ({similarity:.3f}) to known categories", similar_merchants)

        return CategoryResult(
            category=best_category,
            confidence=similarity,
            confidence_level=confidence_level,
            similar_merchants=similar_merchants,
            needs_feedback=confidence_level == CategorizationConfidence.LOW,
            reasoning=f"Similarity-based classification (similarity: {similarity:.3f})"
        )

    async def _check_user_overrides(self, merchant: str, user_id: str) -> Optional[CategoryResult]:
        """Check if user has defined any override rules for this merchant"""
        try:
            # Load user overrides if not cached
            if user_id not in self.user_overrides:
                await self._load_user_overrides(user_id)

            # Check each override rule for this user
            for rule in self.user_overrides.get(user_id, []):
                if rule.is_active and rule.matches_merchant(merchant):
                    return CategoryResult(
                        category=rule.category,
                        confidence=1.0,  # User-defined rules have highest confidence
                        confidence_level=CategorizationConfidence.HIGH,
                        similar_merchants=[],
                        needs_feedback=False,
                        reasoning=f"User-defined override rule: '{rule.merchant_pattern}' → {rule.category}"
                    )

            return None

        except Exception as e:
            logger.error(f"Error checking user overrides: {e}")
            return None

    async def _load_user_overrides(self, user_id: str):
        """Load user override rules from database"""
        if not self.db_pool:
            return

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, user_id, merchant_pattern, category, is_active, created_at, updated_at
                    FROM user_categorization_overrides 
                    WHERE user_id = $1 AND is_active = true
                    ORDER BY created_at DESC
                """, user_id)

                rules = []
                for row in rows:
                    rule = UserOverrideRule(
                        id=str(row['id']),
                        user_id=str(row['user_id']),
                        merchant_pattern=row['merchant_pattern'],
                        category=row['category'],
                        is_active=row['is_active'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    rules.append(rule)

                self.user_overrides[user_id] = rules
                logger.info(f"Loaded {len(rules)} override rules for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to load user overrides: {e}")
            self.user_overrides[user_id] = []

    async def add_user_override(self, user_id: str, merchant_pattern: str, category: str) -> bool:
        """
        Add a user-defined categorization override rule.

        Args:
            user_id: User identifier
            merchant_pattern: Pattern to match against merchant names
            category: Category to assign when pattern matches

        Returns:
            True if rule was successfully added
        """
        if not self.db_pool:
            logger.error("No database pool available for adding user overrides")
            return False

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_categorization_overrides (user_id, merchant_pattern, category)
                    VALUES ($1, $2, $3)
                """, user_id, merchant_pattern, category)

                # Clear cache to force reload
                if user_id in self.user_overrides:
                    del self.user_overrides[user_id]

                logger.info(f"Added user override rule: {merchant_pattern} → {category} for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to add user override: {e}")
            return False

    async def update_user_override(self, user_id: str, rule_id: str, merchant_pattern: Optional[str] = None, 
                                  category: Optional[str] = None, is_active: Optional[bool] = None) -> bool:
        """
        Update an existing user override rule.

        Args:
            user_id: User identifier
            rule_id: Rule identifier
            merchant_pattern: New merchant pattern (optional)
            category: New category (optional)
            is_active: New active status (optional)

        Returns:
            True if rule was successfully updated
        """
        if not self.db_pool:
            logger.error("No database pool available for updating user overrides")
            return False

        # Build dynamic update query
        update_fields = []
        params = [rule_id, user_id]
        param_count = 2

        if merchant_pattern is not None:
            param_count += 1
            update_fields.append(f"merchant_pattern = ${param_count}")
            params.append(merchant_pattern)

        if category is not None:
            param_count += 1
            update_fields.append(f"category = ${param_count}")
            params.append(category)

        if is_active is not None:
            param_count += 1
            update_fields.append(f"is_active = ${param_count}")
            params.append(is_active)

        if not update_fields:
            return True  # Nothing to update

        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        try:
            async with self.db_pool.acquire() as conn:
                query = f"""
                    UPDATE user_categorization_overrides 
                    SET {', '.join(update_fields)}
                    WHERE id = $1 AND user_id = $2
                """
                result = await conn.execute(query, *params)

                # Clear cache to force reload
                if user_id in self.user_overrides:
                    del self.user_overrides[user_id]

                # Check if any rows were updated
                rows_affected = int(result.split()[-1])
                if rows_affected > 0:
                    logger.info(f"Updated user override rule {rule_id} for user {user_id}")
                    return True
                else:
                    logger.warning(f"No override rule found with id {rule_id} for user {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to update user override: {e}")
            return False

    async def delete_user_override(self, user_id: str, rule_id: str) -> bool:
        """
        Delete a user override rule.

        Args:
            user_id: User identifier
            rule_id: Rule identifier

        Returns:
            True if rule was successfully deleted
        """
        if not self.db_pool:
            logger.error("No database pool available for deleting user overrides")
            return False

        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM user_categorization_overrides 
                    WHERE id = $1 AND user_id = $2
                """, rule_id, user_id)

                # Clear cache to force reload
                if user_id in self.user_overrides:
                    del self.user_overrides[user_id]

                # Check if any rows were deleted
                rows_affected = int(result.split()[-1])
                if rows_affected > 0:
                    logger.info(f"Deleted user override rule {rule_id} for user {user_id}")
                    return True
                else:
                    logger.warning(f"No override rule found with id {rule_id} for user {user_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete user override: {e}")
            return False

    async def get_user_overrides(self, user_id: str) -> List[UserOverrideRule]:
        """
        Get all override rules for a user.

        Args:
            user_id: User identifier

        Returns:
            List of user override rules
        """
        await self._load_user_overrides(user_id)
        return self.user_overrides.get(user_id, [])

    async def _check_knowledge_base(self, merchant: str) -> Optional[CategoryResult]:
        """Check merchant against existing knowledge base patterns"""
        if not self.merchant_kb.get('merchant_patterns'):
            return None

        merchant_upper = merchant.upper()

        # Check all pattern groups
        for group_name, patterns in self.merchant_kb['merchant_patterns'].items():
            for pattern, data in patterns.items():
                if pattern in merchant_upper or merchant_upper in pattern:
                    confidence = data.get('confidence', 0.8)
                    category = data.get('category', 'other')

                    return CategoryResult(
                        category=category,
                        confidence=confidence,
                        confidence_level=self._get_confidence_level(confidence),
                        similar_merchants=[data.get('name', pattern)],
                        reasoning=f"Matched knowledge base pattern: {pattern}"
                    )

        return None

    async def _find_most_similar_category(self, merchant_embedding: np.ndarray, merchant: str) -> Tuple[str, float, List[str]]:
        """Find the most similar category using FAISS or linear search"""

        if self.category_index is not None and FAISS_AVAILABLE:
            return await self._faiss_similarity_search(merchant_embedding, merchant)
        else:
            return await self._linear_similarity_search(merchant_embedding, merchant)

    async def _faiss_similarity_search(self, merchant_embedding: np.ndarray, merchant: str) -> Tuple[str, float, List[str]]:
        """Use FAISS for fast similarity search"""
        try:
            # Search for nearest categories
            query_vector = merchant_embedding.reshape(1, -1).astype('float32')
            distances, indices = self.category_index.search(query_vector, k=3)

            # Convert L2 distance to cosine similarity (approximate)
            # For normalized vectors: cosine_sim ≈ 1 - (l2_distance^2 / 2)
            best_idx = indices[0][0]
            best_distance = distances[0][0]
            best_similarity = max(0.0, 1.0 - (best_distance / 2.0))  # Approximate conversion

            best_category = self.category_names[best_idx]

            # Get similar merchants from the category
            similar_merchants = self.category_embeddings[best_category].examples[:3]

            return best_category, best_similarity, similar_merchants

        except Exception as e:
            logger.warning(f"FAISS search failed: {e}, falling back to linear search")
            return await self._linear_similarity_search(merchant_embedding, merchant)

    async def _linear_similarity_search(self, merchant_embedding: np.ndarray, merchant: str) -> Tuple[str, float, List[str]]:
        """Linear search through category embeddings"""
        best_similarity = 0.0
        best_category = "other"

        for category, cat_emb in self.category_embeddings.items():
            # Calculate cosine similarity
            similarity = np.dot(merchant_embedding, cat_emb.embedding) / (
                np.linalg.norm(merchant_embedding) * np.linalg.norm(cat_emb.embedding)
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_category = category

        # Get similar merchants from the best category
        similar_merchants = self.category_embeddings[best_category].examples[:3]

        return best_category, best_similarity, similar_merchants

    def _get_confidence_level(self, similarity: float) -> CategorizationConfidence:
        """Convert similarity score to confidence level"""
        if similarity >= self.high_confidence_threshold:
            return CategorizationConfidence.HIGH
        elif similarity >= self.medium_confidence_threshold:
            return CategorizationConfidence.MEDIUM
        elif similarity >= self.similarity_threshold:
            return CategorizationConfidence.LOW
        else:
            return CategorizationConfidence.UNKNOWN

    def _unknown_category_result(self, merchant: str, reason: str, similar_merchants: List[str] = None) -> CategoryResult:
        """Create result for unknown category with feedback flag"""
        return CategoryResult(
            category="unknown",
            confidence=0.0,
            confidence_level=CategorizationConfidence.UNKNOWN,
            similar_merchants=similar_merchants or [],
            needs_feedback=True,
            reasoning=reason
        )

    async def add_feedback(self, merchant: str, correct_category: str, user_id: Optional[str] = None) -> bool:
        """
        Add user feedback to improve categorization.

        Args:
            merchant: Merchant name that was incorrectly categorized
            correct_category: The correct category provided by user
            user_id: Optional user identifier

        Returns:
            True if feedback was successfully recorded
        """
        try:
            # Get current prediction for comparison
            current_result = await self.categorize_merchant(merchant)

            # Record feedback
            feedback = FeedbackEntry(
                merchant=merchant,
                suggested_category=current_result.category,
                actual_category=correct_category,
                confidence=current_result.confidence,
                timestamp=datetime.utcnow(),
                user_id=user_id
            )

            self.feedback_history.append(feedback)

            # Update merchant categories with correct classification
            self.merchant_categories[merchant.lower()] = correct_category

            # Save feedback and categories
            await self._save_feedback_history()
            await self._save_merchant_categories()

            logger.info(f"Added feedback for merchant '{merchant}': {current_result.category} → {correct_category}")
            return True

        except Exception as e:
            logger.error(f"Failed to add feedback: {e}")
            return False

    async def _load_merchant_categories(self):
        """Load previously categorized merchants"""
        categories_file = self.data_path / "merchant_categories.json"
        try:
            if categories_file.exists():
                with open(categories_file, 'r') as f:
                    self.merchant_categories = json.load(f)
                logger.info(f"Loaded {len(self.merchant_categories)} merchant categories")
        except Exception as e:
            logger.warning(f"Could not load merchant categories: {e}")
            self.merchant_categories = {}

    async def _save_merchant_categories(self):
        """Save merchant categories to disk"""
        categories_file = self.data_path / "merchant_categories.json"
        try:
            with open(categories_file, 'w') as f:
                json.dump(self.merchant_categories, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save merchant categories: {e}")

    async def _load_feedback_history(self):
        """Load feedback history from disk"""
        feedback_file = self.data_path / "feedback_history.json"
        try:
            if feedback_file.exists():
                with open(feedback_file, 'r') as f:
                    feedback_data = json.load(f)
                    self.feedback_history = [
                        FeedbackEntry(**item) for item in feedback_data
                    ]
                logger.info(f"Loaded {len(self.feedback_history)} feedback entries")
        except Exception as e:
            logger.warning(f"Could not load feedback history: {e}")
            self.feedback_history = []

    async def _save_feedback_history(self):
        """Save feedback history to disk"""
        feedback_file = self.data_path / "feedback_history.json"
        try:
            feedback_data = [
                {**asdict(entry), 'timestamp': entry.timestamp.isoformat()}
                for entry in self.feedback_history
            ]
            with open(feedback_file, 'w') as f:
                json.dump(feedback_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save feedback history: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get categorizer statistics"""
        return {
            "initialized": self._initialized,
            "categories_count": len(self.category_embeddings),
            "known_merchants": len(self.merchant_categories),
            "feedback_entries": len(self.feedback_history),
            "backend": self.embeddings.get_backend_info(),
            "faiss_available": FAISS_AVAILABLE,
            "using_faiss": self.category_index is not None,
            "similarity_threshold": self.similarity_threshold,
            "high_confidence_threshold": self.high_confidence_threshold,
            "medium_confidence_threshold": self.medium_confidence_threshold
        }

# Global instance - will be initialized with db_pool in main.py
categorizer = MerchantCategorizer()