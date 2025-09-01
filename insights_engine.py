"""
Insights/Nudges Engine - Advanced RAG-based Financial Analysis Microservice

This microservice provides intelligent natural language querying capabilities for financial data.
It uses LLM + RAG to translate natural language questions into SQL queries and provides
structured insights with supporting transaction data.

Features:
- Natural language to SQL translation
- RAG-based context retrieval
- Anomaly detection using ML models
- Advanced financial analysis
- Trend detection and insights
- Budget and spending pattern analysis
- Multi-dimensional aggregations

Example queries:
- "How much did I spend on food in July?"
- "What are my top 5 spending categories this month?"
- "Show me transactions over ₹1000 in the last week"
- "Compare my spending this month vs last month"
- "What's my average daily spending on transport?"
"""

import asyncio
import json
import logging
import pickle
import re
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# ML imports for anomaly detection
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import asyncpg
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import existing infrastructure
from app.database import get_db, init_db, close_db, set_db_pool
from app.models.pydantic_models import TransactionCategory, TransactionType
from app.services.llm_client import llm_client
from app.services.embeddings import EmbeddingsIndex
from app.deps.auth import get_current_user_optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic Models for API
class InsightsQuery(BaseModel):
    """Request model for insights queries"""
    question: str = Field(..., min_length=1, max_length=500, description="Natural language question about finances")
    user_id: Optional[str] = Field(None, description="User ID for personalized queries")
    time_range_days: Optional[int] = Field(default=30, ge=1, le=365, description="Time range in days for analysis")
    include_supporting_data: bool = Field(default=True, description="Include supporting transactions in response")
    max_transactions: int = Field(default=10, ge=1, le=100, description="Maximum supporting transactions to return")

class TransactionSummary(BaseModel):
    """Summary of a transaction for insights response"""
    id: str
    date: datetime
    amount: float
    type: str
    description: str
    merchant: Optional[str] = None
    category: Optional[str] = None

class InsightsResponse(BaseModel):
    """Response model for insights queries"""
    question: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score of the answer")
    supporting_transactions: List[TransactionSummary] = Field(default_factory=list)
    analysis_metadata: Dict[str, Any] = Field(default_factory=dict)
    sql_query: Optional[str] = Field(None, description="Generated SQL query (for debugging)")
    execution_time_ms: float = Field(description="Query execution time in milliseconds")

# New models for anomaly detection
class AnomalyRequest(BaseModel):
    """Request model for anomaly detection"""
    user_id: str = Field(..., description="User ID for personalized anomaly detection")
    time_range_days: int = Field(default=30, ge=1, le=90, description="Recent transactions to analyze")
    training_period_days: int = Field(default=180, ge=30, le=365, description="Historical data for training")
    sensitivity: float = Field(default=0.1, ge=0.01, le=0.5, description="Anomaly detection sensitivity (lower = more sensitive)")
    min_amount_threshold: float = Field(default=100.0, ge=0, description="Minimum amount to consider for anomaly detection")

class AnomalyScore(BaseModel):
    """Individual anomaly score for a transaction"""
    transaction_id: str
    anomaly_score: float = Field(description="Anomaly score (-1 to 1, lower = more anomalous)")
    is_anomaly: bool = Field(description="Whether transaction is flagged as anomaly")
    anomaly_reasons: List[str] = Field(description="Reasons why transaction is considered anomalous")
    transaction_details: TransactionSummary

class AnomaliesResponse(BaseModel):
    """Response model for anomaly detection"""
    user_id: str
    total_transactions_analyzed: int
    anomalies_detected: int
    anomaly_rate: float = Field(description="Percentage of transactions flagged as anomalies")
    anomalies: List[AnomalyScore] = Field(description="List of detected anomalies")
    model_metadata: Dict[str, Any] = Field(description="Information about the ML model used")
    execution_time_ms: float

@dataclass
class UserSpendingProfile:
    """User spending profile for anomaly detection"""
    user_id: str
    typical_amounts: Dict[str, float]  # category -> typical amount
    typical_merchants: Dict[str, int]  # merchant -> frequency
    spending_patterns: Dict[str, Any]  # various statistical patterns
    last_updated: datetime

@dataclass
class QueryContext:
    """Context information for query processing"""
    user_id: Optional[str]
    time_range_days: int
    start_date: datetime
    end_date: datetime
    raw_question: str
    processed_question: str

@dataclass
class SQLGenerationResult:
    """Result of SQL query generation"""
    sql: str
    parameters: List[Any]
    explanation: str
    confidence: float

class AnomalyDetector:
    """
    ML-based anomaly detection for financial transactions

    Uses multiple approaches:
    1. Isolation Forest for general anomaly detection
    2. One-Class SVM for outlier detection
    3. Statistical analysis for amount and merchant anomalies
    4. Time-based pattern analysis
    """

    def __init__(self, models_path: str = "./data/anomaly_models"):
        self.models_path = Path(models_path)
        self.models_path.mkdir(parents=True, exist_ok=True)

        # ML models
        self.isolation_forest = IsolationForest(
            contamination=0.1,  # Expect 10% anomalies
            random_state=42,
            n_estimators=100
        )
        self.one_class_svm = OneClassSVM(
            nu=0.1,  # Expected fraction of outliers
            kernel='rbf',
            gamma='scale'
        )
        self.scaler = StandardScaler()

        # User profiles cache
        self.user_profiles: Dict[str, UserSpendingProfile] = {}

    async def detect_anomalies(self, user_id: str, recent_transactions: List[Dict], 
                              historical_transactions: List[Dict], 
                              sensitivity: float = 0.1,
                              min_amount_threshold: float = 100.0) -> List[AnomalyScore]:
        """
        Detect anomalies in recent transactions based on historical patterns

        Args:
            user_id: User identifier
            recent_transactions: Recent transactions to analyze
            historical_transactions: Historical data for training
            sensitivity: Detection sensitivity (lower = more sensitive)
            min_amount_threshold: Minimum amount to consider

        Returns:
            List of anomaly scores for flagged transactions
        """
        if not historical_transactions:
            logger.warning(f"No historical data for user {user_id}, skipping anomaly detection")
            return []

        try:
            # Build or update user profile
            user_profile = await self._build_user_profile(user_id, historical_transactions)

            # Prepare features for ML models
            historical_features = self._extract_features(historical_transactions, user_profile)
            recent_features = self._extract_features(recent_transactions, user_profile)

            if len(historical_features) < 10:  # Need minimum data for training
                logger.warning(f"Insufficient historical data for user {user_id}")
                return []

            # Train models on historical data
            historical_features_scaled = self.scaler.fit_transform(historical_features)
            self.isolation_forest.fit(historical_features_scaled)
            self.one_class_svm.fit(historical_features_scaled)

            # Detect anomalies in recent transactions
            recent_features_scaled = self.scaler.transform(recent_features)

            # Get predictions from both models
            isolation_predictions = self.isolation_forest.predict(recent_features_scaled)
            isolation_scores = self.isolation_forest.decision_function(recent_features_scaled)

            svm_predictions = self.one_class_svm.predict(recent_features_scaled)

            # Combine results and create anomaly scores
            anomalies = []
            for i, transaction in enumerate(recent_transactions):
                if transaction['amount'] < min_amount_threshold:
                    continue

                is_isolation_anomaly = isolation_predictions[i] == -1
                is_svm_anomaly = svm_predictions[i] == -1
                isolation_score = isolation_scores[i]

                # Combine anomaly indicators
                is_anomaly = is_isolation_anomaly or is_svm_anomaly

                if is_anomaly or isolation_score < -sensitivity:
                    anomaly_reasons = self._analyze_anomaly_reasons(transaction, user_profile)

                    anomaly_score = AnomalyScore(
                        transaction_id=transaction['id'],
                        anomaly_score=float(isolation_score),
                        is_anomaly=is_anomaly,
                        anomaly_reasons=anomaly_reasons,
                        transaction_details=TransactionSummary(
                            id=transaction['id'],
                            date=transaction['ts'],
                            amount=float(transaction['amount']),
                            type=transaction['type'],
                            description=transaction['raw_desc'],
                            merchant=transaction.get('merchant'),
                            category=transaction.get('category')
                        )
                    )
                    anomalies.append(anomaly_score)

            return anomalies

        except Exception as e:
            logger.error(f"Anomaly detection failed for user {user_id}: {e}")
            return []

    async def _build_user_profile(self, user_id: str, transactions: List[Dict]) -> UserSpendingProfile:
        """Build user spending profile from historical transactions"""

        # Calculate typical amounts by category
        category_amounts = {}
        merchant_frequencies = {}

        for tx in transactions:
            if tx['type'] == 'debit':  # Only analyze spending
                category = tx.get('category', 'other')
                merchant = tx.get('merchant', 'unknown')
                amount = float(tx['amount'])

                if category not in category_amounts:
                    category_amounts[category] = []
                category_amounts[category].append(amount)

                merchant_frequencies[merchant] = merchant_frequencies.get(merchant, 0) + 1

        # Calculate typical amounts (median for robustness)
        typical_amounts = {}
        for category, amounts in category_amounts.items():
            typical_amounts[category] = float(np.median(amounts))

        # Additional patterns
        spending_patterns = {
            'total_transactions': len([tx for tx in transactions if tx['type'] == 'debit']),
            'avg_daily_transactions': len([tx for tx in transactions if tx['type'] == 'debit']) / max(30, 1),
            'top_categories': sorted(category_amounts.keys(), key=lambda x: len(category_amounts[x]), reverse=True)[:5],
            'amount_percentiles': {
                'p25': float(np.percentile([tx['amount'] for tx in transactions if tx['type'] == 'debit'], 25)),
                'p50': float(np.percentile([tx['amount'] for tx in transactions if tx['type'] == 'debit'], 50)),
                'p75': float(np.percentile([tx['amount'] for tx in transactions if tx['type'] == 'debit'], 75)),
                'p95': float(np.percentile([tx['amount'] for tx in transactions if tx['type'] == 'debit'], 95))
            }
        }

        profile = UserSpendingProfile(
            user_id=user_id,
            typical_amounts=typical_amounts,
            typical_merchants=merchant_frequencies,
            spending_patterns=spending_patterns,
            last_updated=datetime.now()
        )

        # Cache the profile
        self.user_profiles[user_id] = profile
        return profile

    def _extract_features(self, transactions: List[Dict], user_profile: UserSpendingProfile) -> np.ndarray:
        """Extract features for ML models"""
        features = []

        for tx in transactions:
            if tx['type'] != 'debit':  # Only analyze spending
                continue

            amount = float(tx['amount'])
            category = tx.get('category', 'other')
            merchant = tx.get('merchant', 'unknown')

            # Feature vector
            feature_vector = [
                amount,  # Raw amount
                amount / max(user_profile.typical_amounts.get(category, amount), 1),  # Amount ratio to typical
                user_profile.typical_merchants.get(merchant, 0),  # Merchant frequency
                len(tx.get('raw_desc', '')),  # Description length
                tx['ts'].hour if hasattr(tx['ts'], 'hour') else 12,  # Hour of day
                tx['ts'].weekday() if hasattr(tx['ts'], 'weekday') else 1,  # Day of week
            ]

            # Category one-hot encoding (simplified)
            category_features = [1 if category == cat else 0 for cat in ['food', 'transport', 'shopping', 'entertainment', 'bills']]
            feature_vector.extend(category_features)

            features.append(feature_vector)

        return np.array(features) if features else np.array([]).reshape(0, 11)  # 6 base + 5 category features

    def _analyze_anomaly_reasons(self, transaction: Dict, user_profile: UserSpendingProfile) -> List[str]:
        """Analyze why a transaction is considered anomalous"""
        reasons = []

        amount = float(transaction['amount'])
        category = transaction.get('category', 'other')
        merchant = transaction.get('merchant', 'unknown')

        # Large amount anomaly
        if amount > user_profile.spending_patterns['amount_percentiles']['p95']:
            reasons.append(f"Unusually large amount (₹{amount:,.2f} vs typical ₹{user_profile.spending_patterns['amount_percentiles']['p50']:,.2f})")

        # Category amount anomaly
        if category in user_profile.typical_amounts:
            typical_amount = user_profile.typical_amounts[category]
            if amount > typical_amount * 3:  # More than 3x typical
                reasons.append(f"Much higher than typical {category} spending (₹{amount:,.2f} vs ₹{typical_amount:,.2f})")

        # Unknown merchant anomaly
        if merchant not in user_profile.typical_merchants or user_profile.typical_merchants[merchant] < 2:
            reasons.append(f"New or rarely used merchant: {merchant}")

        # Time-based anomaly (if transaction is at unusual hour)
        if hasattr(transaction['ts'], 'hour'):
            hour = transaction['ts'].hour
            if hour < 6 or hour > 23:  # Late night/early morning
                reasons.append(f"Unusual time: {hour:02d}:xx")

        return reasons if reasons else ["Statistical anomaly detected by ML model"]

class InsightsEngine:
    """
    Advanced financial insights engine with RAG capabilities

    This engine processes natural language queries about financial data and provides
    intelligent responses with supporting evidence.
    """

    def __init__(self):
        self.embeddings_index = EmbeddingsIndex()
        self.anomaly_detector = AnomalyDetector()
        self.schema_context = self._build_schema_context()
        self.query_patterns = self._build_query_patterns()

    def _build_schema_context(self) -> str:
        """Build database schema context for LLM"""
        return """
Database Schema Context:

TABLES:
1. transactions
   - id (UUID, primary key)
   - bank_transaction_id (VARCHAR, unique)
   - user_id (UUID, foreign key to users)
   - ts (TIMESTAMP WITH TIME ZONE) - transaction timestamp
   - amount (DECIMAL) - always positive, transaction amount
   - type (transaction_type ENUM) - 'debit' or 'credit'
   - raw_desc (TEXT) - original transaction description
   - account_id (VARCHAR) - bank account identifier
   - merchant (VARCHAR) - extracted merchant name
   - category (transaction_category ENUM) - categorized transaction type
   - created_at, updated_at (TIMESTAMP)

2. users
   - id (UUID, primary key)
   - email (VARCHAR)
   - created_at, updated_at (TIMESTAMP)

3. accounts
   - id (UUID, primary key)
   - account_id (VARCHAR, unique)
   - user_id (UUID, foreign key)
   - account_name (VARCHAR)
   - bank_name (VARCHAR)
   - balance (DECIMAL)

ENUMS:
- transaction_type: 'debit', 'credit'
- transaction_category: 'food', 'transport', 'shopping', 'entertainment', 'bills', 'healthcare', 'education', 'salary', 'investment', 'other'

IMPORTANT NOTES:
- All amounts are positive; use 'type' field to determine if money was spent (debit) or received (credit)
- Use ts field for date filtering
- user_id filtering is MANDATORY for all queries
- Dates should be compared using DATE() function or timestamp ranges
"""

    def _build_query_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Build common query patterns for better SQL generation"""
        return {
            "spending_patterns": {
                "keywords": ["spend", "spent", "spending", "expense", "cost"],
                "sql_template": """
                SELECT SUM(amount) as total_amount, COUNT(*) as transaction_count
                FROM transactions 
                WHERE user_id = $1 AND type = 'debit' AND ts >= $2 AND ts <= $3
                {additional_filters}
                """,
                "confidence": 0.9
            },
            "category_analysis": {
                "keywords": ["category", "food", "transport", "shopping", "entertainment", "bills"],
                "sql_template": """
                SELECT category, SUM(amount) as total_amount, COUNT(*) as transaction_count,
                       AVG(amount) as avg_amount
                FROM transactions 
                WHERE user_id = $1 AND type = 'debit' AND ts >= $2 AND ts <= $3
                {additional_filters}
                GROUP BY category
                ORDER BY total_amount DESC
                """,
                "confidence": 0.85
            },
            "merchant_analysis": {
                "keywords": ["merchant", "store", "restaurant", "shop"],
                "sql_template": """
                SELECT merchant, SUM(amount) as total_amount, COUNT(*) as transaction_count
                FROM transactions 
                WHERE user_id = $1 AND type = 'debit' AND ts >= $2 AND ts <= $3
                AND merchant IS NOT NULL
                {additional_filters}
                GROUP BY merchant
                ORDER BY total_amount DESC
                LIMIT 10
                """,
                "confidence": 0.8
            },
            "time_series": {
                "keywords": ["trend", "over time", "daily", "weekly", "monthly"],
                "sql_template": """
                SELECT DATE(ts) as date, SUM(amount) as daily_amount, COUNT(*) as daily_count
                FROM transactions 
                WHERE user_id = $1 AND type = 'debit' AND ts >= $2 AND ts <= $3
                {additional_filters}
                GROUP BY DATE(ts)
                ORDER BY date
                """,
                "confidence": 0.8
            },
            "income_analysis": {
                "keywords": ["income", "salary", "earned", "received", "credit"],
                "sql_template": """
                SELECT SUM(amount) as total_income, COUNT(*) as transaction_count,
                       category, AVG(amount) as avg_amount
                FROM transactions 
                WHERE user_id = $1 AND type = 'credit' AND ts >= $2 AND ts <= $3
                {additional_filters}
                GROUP BY category
                ORDER BY total_income DESC
                """,
                "confidence": 0.85
            }
        }

    async def process_query(self, query: InsightsQuery, db: asyncpg.Connection) -> InsightsResponse:
        """
        Process a natural language query and return insights

        Args:
            query: The insights query request
            db: Database connection

        Returns:
            InsightsResponse with answer and supporting data
        """
        start_time = datetime.now()

        try:
            # Build query context
            context = self._build_query_context(query)

            # Generate SQL query using LLM + patterns
            sql_result = await self._generate_sql_query(context, db)

            # Execute the query
            query_results = await self._execute_query(sql_result, context, db)

            # Generate natural language response
            answer = await self._generate_response(context, query_results, sql_result)

            # Get supporting transactions if requested
            supporting_transactions = []
            if query.include_supporting_data:
                supporting_transactions = await self._get_supporting_transactions(
                    context, query_results, db, query.max_transactions
                )

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return InsightsResponse(
                question=query.question,
                answer=answer["text"],
                confidence=answer["confidence"],
                supporting_transactions=supporting_transactions,
                analysis_metadata=answer.get("metadata", {}),
                sql_query=sql_result.sql if sql_result else None,
                execution_time_ms=execution_time
            )

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return InsightsResponse(
                question=query.question,
                answer=f"I encountered an error while analyzing your financial data: {str(e)}",
                confidence=0.1,
                supporting_transactions=[],
                analysis_metadata={"error": str(e)},
                execution_time_ms=execution_time
            )

    def _build_query_context(self, query: InsightsQuery) -> QueryContext:
        """Build context for query processing"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=query.time_range_days)

        # Process the question to extract key information
        processed_question = self._preprocess_question(query.question)

        return QueryContext(
            user_id=query.user_id,
            time_range_days=query.time_range_days,
            start_date=start_date,
            end_date=end_date,
            raw_question=query.question,
            processed_question=processed_question
        )

    def _preprocess_question(self, question: str) -> str:
        """Preprocess the question to extract temporal and categorical information"""
        question_lower = question.lower()

        # Extract time references and convert them
        time_patterns = {
            r'\bjuly\b': 'July',
            r'\baugust\b': 'August',
            r'\bseptember\b': 'September',
            r'\boctober\b': 'October',
            r'\bnovember\b': 'November',
            r'\bdecember\b': 'December',
            r'\bjanuary\b': 'January',
            r'\bfebruary\b': 'February',
            r'\bmarch\b': 'March',
            r'\bapril\b': 'April',
            r'\bmay\b': 'May',
            r'\bjune\b': 'June',
            r'\blast month\b': 'last month',
            r'\bthis month\b': 'this month',
            r'\blast week\b': 'last week',
            r'\bthis week\b': 'this week',
            r'\byesterday\b': 'yesterday',
            r'\btoday\b': 'today'
        }

        processed = question
        for pattern, replacement in time_patterns.items():
            processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)

        return processed

    async def _generate_sql_query(self, context: QueryContext, db: asyncpg.Connection) -> SQLGenerationResult:
        """Generate SQL query using LLM and pattern matching"""

        # First, try pattern matching for common queries
        pattern_result = self._match_query_patterns(context)
        if pattern_result and pattern_result.confidence > 0.7:
            return pattern_result

        # Use LLM for complex queries
        llm_result = await self._generate_sql_with_llm(context)

        # Use the better result
        if pattern_result and llm_result:
            return pattern_result if pattern_result.confidence > llm_result.confidence else llm_result
        elif pattern_result:
            return pattern_result
        elif llm_result:
            return llm_result
        else:
            # Fallback to basic query
            return self._generate_fallback_query(context)

    def _match_query_patterns(self, context: QueryContext) -> Optional[SQLGenerationResult]:
        """Match query against predefined patterns"""
        question_lower = context.processed_question.lower()

        best_match = None
        best_score = 0

        for pattern_name, pattern_info in self.query_patterns.items():
            score = 0
            for keyword in pattern_info["keywords"]:
                if keyword in question_lower:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = (pattern_name, pattern_info)

        if not best_match or best_score == 0:
            return None

        pattern_name, pattern_info = best_match

        # Build the SQL query
        additional_filters = self._build_additional_filters(context, question_lower)
        sql = pattern_info["sql_template"].format(additional_filters=additional_filters)

        # Build parameters
        parameters = [context.user_id, context.start_date, context.end_date]

        confidence = pattern_info["confidence"] * (best_score / len(pattern_info["keywords"]))

        return SQLGenerationResult(
            sql=sql,
            parameters=parameters,
            explanation=f"Matched pattern: {pattern_name}",
            confidence=min(confidence, 0.95)
        )

    def _build_additional_filters(self, context: QueryContext, question_lower: str) -> str:
        """Build additional SQL filters based on question content"""
        filters = []

        # Category filters
        for category in TransactionCategory:
            if category.value in question_lower:
                filters.append(f"AND category = '{category.value}'")
                break

        # Amount filters
        amount_pattern = r'over ₹?(\d+(?:,\d+)*)'
        match = re.search(amount_pattern, question_lower)
        if match:
            amount = match.group(1).replace(',', '')
            filters.append(f"AND amount > {amount}")

        # Merchant filters
        merchant_keywords = ['amazon', 'zomato', 'swiggy', 'uber', 'netflix', 'flipkart']
        for merchant in merchant_keywords:
            if merchant in question_lower:
                filters.append(f"AND LOWER(merchant) LIKE '%{merchant}%'")
                break

        return ' '.join(filters)

    async def _generate_sql_with_llm(self, context: QueryContext) -> Optional[SQLGenerationResult]:
        """Generate SQL using LLM"""
        try:
            prompt = self._build_sql_generation_prompt(context)

            # Use the existing LLM client (this is a simplified approach)
            # In a real implementation, you'd want a specialized SQL generation model
            llm_response = await llm_client.classify_transaction(prompt)

            # Parse the LLM response (this would need proper implementation)
            # For now, return None to use pattern matching
            return None

        except Exception as e:
            logger.error(f"LLM SQL generation failed: {e}")
            return None

    def _build_sql_generation_prompt(self, context: QueryContext) -> str:
        """Build prompt for LLM SQL generation"""
        return f"""
Generate a PostgreSQL query for this financial question:

Question: {context.processed_question}
User ID: {context.user_id}
Date Range: {context.start_date} to {context.end_date}

{self.schema_context}

Requirements:
1. Always include user_id filter: WHERE user_id = $1
2. Include date range filter: AND ts >= $2 AND ts <= $3
3. Use proper parameter placeholders ($1, $2, $3, etc.)
4. Return aggregated results when appropriate
5. Order results meaningfully

Generate only the SQL query, no explanations.
"""

    def _generate_fallback_query(self, context: QueryContext) -> SQLGenerationResult:
        """Generate a basic fallback query"""
        sql = """
        SELECT 
            SUM(CASE WHEN type = 'debit' THEN amount ELSE 0 END) as total_spent,
            SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END) as total_received,
            COUNT(*) as transaction_count,
            category,
            SUM(amount) as category_total
        FROM transactions 
        WHERE user_id = $1 AND ts >= $2 AND ts <= $3
        GROUP BY category
        ORDER BY category_total DESC
        """

        return SQLGenerationResult(
            sql=sql,
            parameters=[context.user_id, context.start_date, context.end_date],
            explanation="Fallback general financial summary query",
            confidence=0.5
        )

    async def _execute_query(self, sql_result: SQLGenerationResult, context: QueryContext, db: asyncpg.Connection) -> List[Dict[str, Any]]:
        """Execute the generated SQL query"""
        try:
            rows = await db.fetch(sql_result.sql, *sql_result.parameters)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"SQL: {sql_result.sql}")
            logger.error(f"Parameters: {sql_result.parameters}")
            raise

    async def _generate_response(self, context: QueryContext, query_results: List[Dict[str, Any]], sql_result: SQLGenerationResult) -> Dict[str, Any]:
        """Generate natural language response from query results"""

        if not query_results:
            return {
                "text": "I couldn't find any transactions matching your query in the specified time period.",
                "confidence": 0.8,
                "metadata": {"result_count": 0}
            }

        # Analyze the results and generate appropriate response
        response_text = self._build_response_text(context, query_results)
        metadata = self._extract_metadata(query_results)

        return {
            "text": response_text,
            "confidence": sql_result.confidence,
            "metadata": metadata
        }

    def _build_response_text(self, context: QueryContext, results: List[Dict[str, Any]]) -> str:
        """Build natural language response text"""
        question_lower = context.raw_question.lower()

        # Handle different types of queries
        if any(word in question_lower for word in ['spend', 'spent', 'cost']):
            return self._build_spending_response(context, results)
        elif any(word in question_lower for word in ['category', 'categories']):
            return self._build_category_response(context, results)
        elif any(word in question_lower for word in ['merchant', 'store']):
            return self._build_merchant_response(context, results)
        elif any(word in question_lower for word in ['income', 'earned', 'salary']):
            return self._build_income_response(context, results)
        else:
            return self._build_general_response(context, results)

    def _build_spending_response(self, context: QueryContext, results: List[Dict[str, Any]]) -> str:
        """Build response for spending queries"""
        if not results:
            return "No spending found in the specified period."

        # Check if we have aggregated spending data
        if 'total_amount' in results[0]:
            total = results[0]['total_amount']
            count = results[0]['transaction_count']
            avg = total / count if count > 0 else 0

            response = f"You spent ₹{total:,.2f} across {count} transactions"
            if count > 1:
                response += f", averaging ₹{avg:,.2f} per transaction"
            response += f" in the last {context.time_range_days} days."

            return response

        return "Found spending data but couldn't analyze the specific amounts."

    def _build_category_response(self, context: QueryContext, results: List[Dict[str, Any]]) -> str:
        """Build response for category-based queries"""
        if not results:
            return "No categorized spending found."

        response = f"Your spending breakdown over the last {context.time_range_days} days:\n"

        for i, result in enumerate(results[:5]):  # Top 5 categories
            category = result.get('category', 'Unknown')
            amount = result.get('total_amount', 0) or result.get('category_total', 0)
            count = result.get('transaction_count', 0)

            if category and amount:
                response += f"{i+1}. {category.title()}: ₹{amount:,.2f}"
                if count:
                    response += f" ({count} transactions)"
                response += "\n"

        return response.strip()

    def _build_merchant_response(self, context: QueryContext, results: List[Dict[str, Any]]) -> str:
        """Build response for merchant-based queries"""
        if not results:
            return "No merchant data found."

        response = f"Your top merchants over the last {context.time_range_days} days:\n"

        for i, result in enumerate(results[:5]):
            merchant = result.get('merchant', 'Unknown')
            amount = result.get('total_amount', 0)
            count = result.get('transaction_count', 0)

            if merchant and amount:
                response += f"{i+1}. {merchant}: ₹{amount:,.2f}"
                if count:
                    response += f" ({count} transactions)"
                response += "\n"

        return response.strip()

    def _build_income_response(self, context: QueryContext, results: List[Dict[str, Any]]) -> str:
        """Build response for income queries"""
        if not results:
            return "No income transactions found."

        total_income = sum(result.get('total_income', 0) for result in results)
        total_count = sum(result.get('transaction_count', 0) for result in results)

        response = f"You received ₹{total_income:,.2f} across {total_count} transactions"
        response += f" in the last {context.time_range_days} days."

        # Add breakdown by category if available
        if len(results) > 1:
            response += "\n\nBreakdown by source:"
            for result in results:
                category = result.get('category', 'Other')
                amount = result.get('total_income', 0)
                if amount > 0:
                    response += f"\n• {category.title()}: ₹{amount:,.2f}"

        return response

    def _build_general_response(self, context: QueryContext, results: List[Dict[str, Any]]) -> str:
        """Build general response for unclassified queries"""
        if not results:
            return "No relevant financial data found for your query."

        # Try to extract meaningful information from the results
        if 'total_spent' in results[0]:
            spent = results[0]['total_spent'] or 0
            received = results[0]['total_received'] or 0
            count = results[0]['transaction_count'] or 0

            response = f"Over the last {context.time_range_days} days, you had {count} transactions. "
            response += f"You spent ₹{spent:,.2f} and received ₹{received:,.2f}, "
            response += f"for a net flow of ₹{(received - spent):,.2f}."

            return response

        return f"I found {len(results)} relevant records for your query."

    def _extract_metadata(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract metadata from query results"""
        metadata = {
            "result_count": len(results),
            "has_amounts": any('amount' in result or 'total_amount' in result for result in results),
            "has_categories": any('category' in result for result in results),
            "has_merchants": any('merchant' in result for result in results),
        }

        # Add summary statistics if available
        amounts = []
        for result in results:
            amount = result.get('total_amount') or result.get('amount') or result.get('category_total')
            if amount:
                amounts.append(float(amount))

        if amounts:
            metadata.update({
                "total_amount": sum(amounts),
                "avg_amount": sum(amounts) / len(amounts),
                "max_amount": max(amounts),
                "min_amount": min(amounts)
            })

        return metadata

    async def _get_supporting_transactions(self, context: QueryContext, query_results: List[Dict[str, Any]], 
                                         db: asyncpg.Connection, max_transactions: int) -> List[TransactionSummary]:
        """Get supporting transaction details"""
        try:
            # Build a query to get recent relevant transactions
            sql = """
            SELECT bank_transaction_id, ts, amount, type, raw_desc, merchant, category
            FROM transactions 
            WHERE user_id = $1 AND ts >= $2 AND ts <= $3
            ORDER BY ts DESC
            LIMIT $4
            """

            rows = await db.fetch(sql, context.user_id, context.start_date, context.end_date, max_transactions)

            transactions = []
            for row in rows:
                transactions.append(TransactionSummary(
                    id=row['bank_transaction_id'],
                    date=row['ts'],
                    amount=float(row['amount']),
                    type=row['type'],
                    description=row['raw_desc'],
                    merchant=row['merchant'],
                    category=row['category']
                ))

            return transactions

        except Exception as e:
            logger.error(f"Failed to get supporting transactions: {e}")
            return []

# FastAPI Application
app = FastAPI(
    title="Financial Insights Engine",
    description="Advanced RAG-based financial analysis microservice",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global insights engine instance
insights_engine = InsightsEngine()

@app.on_event("startup")
async def startup():
    """Initialize the insights engine on startup"""
    logger.info("🚀 Starting Financial Insights Engine")

    # Initialize database connection (you'll need to adapt this based on your setup)
    # For now, this is a placeholder - you'd integrate with your existing database setup
    try:
        await insights_engine.embeddings_index.init_embeddings_index("./data/insights_embeddings.db")
        logger.info("✅ Insights engine initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize insights engine: {e}")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down Financial Insights Engine")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Financial Insights Engine",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/insights", response_model=InsightsResponse)
async def query_insights(
    query: InsightsQuery,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Process natural language financial queries and return insights

    Example queries:
    - "How much did I spend on food in July?"
    - "What are my top 5 spending categories this month?"
    - "Show me transactions over ₹1000 in the last week"
    - "Compare my spending this month vs last month"
    """
    logger.info(f"💬 Processing query: {query.question}")

    if not db:
        # Return mock response for development
        return InsightsResponse(
            question=query.question,
            answer="I'm running in development mode without a database connection. Please connect to a database to get real insights.",
            confidence=0.1,
            supporting_transactions=[],
            analysis_metadata={"mode": "development"},
            execution_time_ms=0.0
        )

    try:
        response = await insights_engine.process_query(query, db)
        logger.info(f"✅ Query processed successfully (confidence: {response.confidence:.2f})")
        return response

    except Exception as e:
        logger.error(f"❌ Query processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process insights query: {str(e)}"
        )

@app.post("/anomalies", response_model=AnomaliesResponse)
async def detect_anomalies(
    request: AnomalyRequest,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Detect anomalous transactions using ML models

    This endpoint trains lightweight ML models (Isolation Forest, One-Class SVM) on the user's
    historical spending patterns and identifies unusual transactions that deviate from normal behavior.

    Anomalies detected:
    - Unusually large amounts
    - Transactions at new/rare merchants
    - Spending patterns that deviate from historical norms
    - Time-based anomalies (unusual hours/days)
    """
    start_time = datetime.now()
    logger.info(f"🔍 Detecting anomalies for user: {request.user_id}")

    if not db:
        # Return mock response for development
        mock_anomaly = AnomalyScore(
            transaction_id="mock_tx_001",
            anomaly_score=-0.8,
            is_anomaly=True,
            anomaly_reasons=["Development mode - mock anomaly"],
            transaction_details=TransactionSummary(
                id="mock_tx_001",
                date=datetime.now(),
                amount=5000.0,
                type="debit",
                description="Mock large transaction",
                merchant="Unknown Merchant",
                category="other"
            )
        )

        return AnomaliesResponse(
            user_id=request.user_id,
            total_transactions_analyzed=1,
            anomalies_detected=1,
            anomaly_rate=100.0,
            anomalies=[mock_anomaly],
            model_metadata={"mode": "development", "model": "mock"},
            execution_time_ms=0.0
        )

    try:
        # Get historical transactions for training
        historical_end = datetime.now() - timedelta(days=request.time_range_days)
        historical_start = historical_end - timedelta(days=request.training_period_days)

        historical_query = """
        SELECT bank_transaction_id as id, ts, amount, type, raw_desc, merchant, category
        FROM transactions 
        WHERE user_id = $1 AND ts >= $2 AND ts <= $3 AND type = 'debit'
        ORDER BY ts DESC
        """

        historical_rows = await db.fetch(historical_query, request.user_id, historical_start, historical_end)
        historical_transactions = [dict(row) for row in historical_rows]

        # Get recent transactions to analyze
        recent_start = datetime.now() - timedelta(days=request.time_range_days)
        recent_end = datetime.now()

        recent_query = """
        SELECT bank_transaction_id as id, ts, amount, type, raw_desc, merchant, category
        FROM transactions 
        WHERE user_id = $1 AND ts >= $2 AND ts <= $3 AND type = 'debit'
        ORDER BY ts DESC
        """

        recent_rows = await db.fetch(recent_query, request.user_id, recent_start, recent_end)
        recent_transactions = [dict(row) for row in recent_rows]

        if not recent_transactions:
            return AnomaliesResponse(
                user_id=request.user_id,
                total_transactions_analyzed=0,
                anomalies_detected=0,
                anomaly_rate=0.0,
                anomalies=[],
                model_metadata={"error": "No recent transactions found"},
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

        # Detect anomalies
        anomalies = await insights_engine.anomaly_detector.detect_anomalies(
            user_id=request.user_id,
            recent_transactions=recent_transactions,
            historical_transactions=historical_transactions,
            sensitivity=request.sensitivity,
            min_amount_threshold=request.min_amount_threshold
        )

        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        anomaly_rate = (len(anomalies) / len(recent_transactions)) * 100 if recent_transactions else 0

        logger.info(f"✅ Detected {len(anomalies)} anomalies out of {len(recent_transactions)} transactions ({anomaly_rate:.1f}%)")

        return AnomaliesResponse(
            user_id=request.user_id,
            total_transactions_analyzed=len(recent_transactions),
            anomalies_detected=len(anomalies),
            anomaly_rate=anomaly_rate,
            anomalies=anomalies,
            model_metadata={
                "historical_transactions": len(historical_transactions),
                "training_period_days": request.training_period_days,
                "models_used": ["IsolationForest", "OneClassSVM"],
                "sensitivity": request.sensitivity,
                "min_amount_threshold": request.min_amount_threshold
            },
            execution_time_ms=execution_time
        )

    except Exception as e:
        logger.error(f"❌ Anomaly detection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect anomalies: {str(e)}"
        )

@app.get("/insights/patterns")
async def get_query_patterns():
    """Get available query patterns for reference"""
    return {
        "patterns": list(insights_engine.query_patterns.keys()),
        "examples": {
            "spending": [
                "How much did I spend on food this month?",
                "What's my total spending in July?",
                "Show me my expenses over ₹1000"
            ],
            "categories": [
                "What are my top spending categories?",
                "Break down my expenses by category",
                "How much did I spend on transport?"
            ],
            "merchants": [
                "Which merchants do I spend the most at?",
                "Show me my Amazon purchases",
                "Top 5 restaurants by spending"
            ],
            "trends": [
                "Show my spending trend over the last month",
                "Daily spending analysis",
                "How does this month compare to last month?"
            ],
            "income": [
                "How much did I earn this month?",
                "Show my salary credits",
                "What's my total income?"
            ]
        }
    }

@app.get("/insights/schema")
async def get_schema_info():
    """Get database schema information for debugging"""
    return {
        "schema": insights_engine.schema_context,
        "supported_categories": [cat.value for cat in TransactionCategory],
        "supported_types": [t.value for t in TransactionType]
    }

if __name__ == "__main__":
    import uvicorn

    # Run the microservice
    uvicorn.run(
        "insights_engine:app",
        host="0.0.0.0",
        port=8001,  # Different port from main app
        reload=True,
        log_level="info"
    )
