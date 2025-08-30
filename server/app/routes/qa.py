# Q&A routes with intelligent financial analysis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import asyncpg
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

class QuestionRequest(BaseModel):
    question: str
    context_days: int = 30

class QuestionResponse(BaseModel):
    answer: str
    confidence: float
    sources: List[Dict[str, Any]] = []
    analysis_summary: Dict[str, Any] = {}

@router.post("/", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    db: asyncpg.Connection = Depends(get_db)
):
    """Ask financial questions with intelligent analysis"""
    
    logger.info(f"💬 Question received: '{request.question}'")
    
    try:
        # Get transaction data
        transactions = await get_transactions_data(db, request.context_days)
        logger.info(f"📊 Found {len(transactions)} transactions")
        
        # Analyze question and generate answer
        analysis = analyze_financial_question(request.question, transactions)
        
        logger.info(f"✅ Generated answer: {analysis['answer'][:50]}...")
        
        return QuestionResponse(
            answer=analysis["answer"],
            confidence=analysis["confidence"],
            sources=analysis.get("sources", []),
            analysis_summary=analysis.get("summary", {})
        )
    
    except Exception as e:
        logger.error(f"❌ Error processing question: {e}")
        return QuestionResponse(
            answer="I encountered an error while analyzing your financial data. Please try again.",
            confidence=0.1,
            sources=[],
            analysis_summary={}
        )

async def get_transactions_data(db: asyncpg.Connection, context_days: int) -> List[Dict]:
    """Get transaction data from database or return mock data"""
    
    if not db:
        logger.info("📝 Using mock data (no database)")
        return get_mock_transactions()
    
    try:
        # Get transactions from database
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=context_days)
        
        query = """
            SELECT bank_transaction_id, ts, amount, type, raw_desc, 
                   account_id, merchant, category
            FROM transactions 
            WHERE ts >= $1 AND ts <= $2
            ORDER BY ts DESC
            LIMIT 100
        """
        
        rows = await db.fetch(query, start_date, end_date)
        
        transactions = []
        for row in rows:
            transactions.append({
                'id': row['bank_transaction_id'],
                'date': row['ts'],
                'amount': float(row['amount']),
                'type': row['type'],
                'description': row['raw_desc'],
                'merchant': row['merchant'],
                'category': row['category']
            })
        
        return transactions
        
    except Exception as e:
        logger.warning(f"Database query failed: {e}, using mock data")
        return get_mock_transactions()

def get_mock_transactions() -> List[Dict]:
    """Generate realistic mock transaction data for testing"""
    
    mock_data = [
        {
            'id': 'txn_001',
            'date': datetime.now() - timedelta(days=1),
            'amount': 450.0,
            'type': 'debit',
            'description': 'ZOMATO ORDER #12345',
            'merchant': 'Zomato',
            'category': 'food'
        },
        {
            'id': 'txn_002',
            'date': datetime.now() - timedelta(days=3),
            'amount': 1200.0,
            'type': 'debit',
            'description': 'AMAZON.IN PURCHASE',
            'merchant': 'Amazon',
            'category': 'shopping'
        },
        {
            'id': 'txn_003',
            'date': datetime.now() - timedelta(days=2),
            'amount': 300.0,
            'type': 'debit',
            'description': 'UBER TRIP',
            'merchant': 'Uber',
            'category': 'transport'
        },
        {
            'id': 'txn_004',
            'date': datetime.now() - timedelta(days=7),
            'amount': 50000.0,
            'type': 'credit',
            'description': 'SALARY CREDIT',
            'merchant': 'Company',
            'category': 'salary'
        },
        {
            'id': 'txn_005',
            'date': datetime.now() - timedelta(days=5),
            'amount': 800.0,
            'type': 'debit',
            'description': 'SWIGGY ORDER',
            'merchant': 'Swiggy',
            'category': 'food'
        }
    ]
    
    return mock_data

def analyze_financial_question(question: str, transactions: List[Dict]) -> Dict[str, Any]:
    """Analyze financial question and generate intelligent response"""
    
    question_lower = question.lower()
    
    # Calculate basic financial metrics
    total_spent = sum(tx['amount'] for tx in transactions if tx['type'] == 'debit')
    total_received = sum(tx['amount'] for tx in transactions if tx['type'] == 'credit')
    net_flow = total_received - total_spent
    
    # Category breakdown
    categories = {}
    for tx in transactions:
        if tx['type'] == 'debit' and tx['category']:
            cat = tx['category']
            categories[cat] = categories.get(cat, 0) + tx['amount']
    
    # Merchant breakdown
    merchants = {}
    for tx in transactions:
        if tx['type'] == 'debit' and tx['merchant']:
            merchant = tx['merchant']
            merchants[merchant] = merchants.get(merchant, 0) + tx['amount']
    
    # Sort by amount
    top_categories = dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))
    top_merchants = dict(sorted(merchants.items(), key=lambda x: x[1], reverse=True))
    
    # Generate response based on question type
    response = generate_smart_response(
        question_lower, 
        {
            'total_spent': total_spent,
            'total_received': total_received,
            'net_flow': net_flow,
            'transaction_count': len(transactions),
            'categories': top_categories,
            'merchants': top_merchants,
            'transactions': transactions
        }
    )
    
    return response

def generate_smart_response(question: str, data: Dict) -> Dict[str, Any]:
    """Generate intelligent responses based on question patterns"""
    
    # Food spending questions
    if any(word in question for word in ['food', 'eat', 'restaurant', 'dining', 'zomato', 'swiggy']):
        food_amount = data['categories'].get('food', 0)
        if food_amount > 0:
            answer = f"You spent ₹{food_amount:,.2f} on food in the analyzed period. "
            if 'food' in data['categories']:
                percentage = (food_amount / data['total_spent']) * 100 if data['total_spent'] > 0 else 0
                answer += f"That's {percentage:.1f}% of your total spending."
        else:
            answer = "No food-related transactions found in the analyzed period."
        
        return {
            "answer": answer,
            "confidence": 0.9,
            "sources": [tx for tx in data['transactions'] if tx.get('category') == 'food'][:3]
        }
    
    # Transport spending questions
    elif any(word in question for word in ['transport', 'travel', 'uber', 'taxi', 'metro']):
        transport_amount = data['categories'].get('transport', 0)
        if transport_amount > 0:
            answer = f"You spent ₹{transport_amount:,.2f} on transport. "
            answer += f"This includes rides, public transport, and travel expenses."
        else:
            answer = "No transport-related transactions found."
        
        return {
            "answer": answer,
            "confidence": 0.9,
            "sources": [tx for tx in data['transactions'] if tx.get('category') == 'transport'][:3]
        }
    
    # Shopping questions
    elif any(word in question for word in ['shopping', 'shop', 'buy', 'purchase', 'amazon']):
        shopping_amount = data['categories'].get('shopping', 0)
        if shopping_amount > 0:
            answer = f"You spent ₹{shopping_amount:,.2f} on shopping. "
            answer += f"This includes online and offline purchases."
        else:
            answer = "No shopping transactions found."
        
        return {
            "answer": answer,
            "confidence": 0.9,
            "sources": [tx for tx in data['transactions'] if tx.get('category') == 'shopping'][:3]
        }
    
    # Total spending questions
    elif any(word in question for word in ['total', 'spent', 'spending', 'expense']):
        answer = f"Your total spending was ₹{data['total_spent']:,.2f} across {data['transaction_count']} transactions. "
        if data['categories']:
            top_category = list(data['categories'].keys())[0]
            top_amount = list(data['categories'].values())[0]
            answer += f"Your highest spending category was {top_category} at ₹{top_amount:,.2f}."
        
        return {
            "answer": answer,
            "confidence": 0.95,
            "summary": {
                "total_spent": data['total_spent'],
                "categories": dict(list(data['categories'].items())[:3])
            }
        }
    
    # Income questions
    elif any(word in question for word in ['income', 'salary', 'earned', 'received']):
        answer = f"You received ₹{data['total_received']:,.2f} during the analyzed period. "
        salary_transactions = [tx for tx in data['transactions'] if tx.get('category') == 'salary']
        if salary_transactions:
            answer += f"This includes salary and other income sources."
        
        return {
            "answer": answer,
            "confidence": 0.9,
            "sources": [tx for tx in data['transactions'] if tx['type'] == 'credit'][:3]
        }
    
    # Balance/net flow questions
    elif any(word in question for word in ['balance', 'net', 'flow', 'left', 'remaining']):
        if data['net_flow'] > 0:
            answer = f"Your net cash flow is positive at ₹{data['net_flow']:,.2f}. "
            answer += f"You received ₹{data['total_received']:,.2f} and spent ₹{data['total_spent']:,.2f}."
        else:
            answer = f"Your net cash flow is ₹{data['net_flow']:,.2f}. "
            answer += f"You spent ₹{data['total_spent']:,.2f} and received ₹{data['total_received']:,.2f}."
        
        return {
            "answer": answer,
            "confidence": 0.95,
            "summary": {
                "net_flow": data['net_flow'],
                "total_spent": data['total_spent'],
                "total_received": data['total_received']
            }
        }
    
    # Category breakdown questions
    elif any(word in question for word in ['category', 'categories', 'breakdown', 'where']):
        if data['categories']:
            answer = "Here's your spending breakdown by category: "
            category_list = []
            for cat, amount in list(data['categories'].items())[:5]:
                percentage = (amount / data['total_spent']) * 100 if data['total_spent'] > 0 else 0
                category_list.append(f"{cat}: ₹{amount:,.2f} ({percentage:.1f}%)")
            answer += ", ".join(category_list) + "."
        else:
            answer = "No spending categories found in the analyzed period."

        return {
            "answer": answer,
            "confidence": 0.85,
            "summary": {"categories": dict(list(data['categories'].items())[:3])}
        }
    
    # Default response
    else:
        answer = f"Based on your {data['transaction_count']} transactions, you spent ₹{data['total_spent']:,.2f} "
        answer += f"and received ₹{data['total_received']:,.2f}. "
        
        if data['categories']:
            top_category = list(data['categories'].keys())[0]
            answer += f"Your top spending category was {top_category}."
        
        return {
            "answer": answer,
            "confidence": 0.7,
            "summary": {
                "total_spent": data['total_spent'],
                "total_received": data['total_received'],
                "top_category": list(data['categories'].keys())[0] if data['categories'] else None
            }
        }

# Test function for development
if __name__ == "__main__":
    async def test_qa():
        """Test the QA functionality"""
        test_questions = [
            "How much did I spend on food?",
            "What's my total spending?",
            "How much did I spend on transport?",
            "What are my top categories?",
            "What's my net balance?"
        ]
        
        print("🧪 Testing QA System\n")
        
        for question in test_questions:
            mock_transactions = get_mock_transactions()
            result = analyze_financial_question(question, mock_transactions)
            print(f"Q: {question}")
            print(f"A: {result['answer']}")
            print(f"Confidence: {result['confidence']}")
            print("-" * 50)
    
    import asyncio
    asyncio.run(test_qa())
