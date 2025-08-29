# Q&A routes
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import asyncpg
from app.database import get_db

router = APIRouter()

class QuestionRequest(BaseModel):
    question: str
    context_days: int = 30

class QuestionResponse(BaseModel):
    answer: str
    confidence: float
    sources: list = []

@router.post("/", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    db: asyncpg.Connection = Depends(get_db)
):
    """Ask financial questions using AI"""
    # TODO: Implement LLM integration with Llama-3 8B
    return QuestionResponse(
        answer=f"Based on your spending patterns over the last {request.context_days} days, here's what I found regarding: '{request.question}'. This feature is coming soon!",
        confidence=0.8,
        sources=["transactions_analysis"]
    )