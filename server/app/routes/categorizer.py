"""
FastAPI routes for merchant categorization functionality.

This module provides REST API endpoints for:
1. Categorizing merchants using embeddings
2. Adding user feedback for improving categorization
3. Getting categorizer statistics and health
4. Batch categorization for multiple merchants
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..services.categorizer import categorizer, CategoryResult, CategorizationConfidence
from ..deps.auth import get_current_user  # Assuming auth exists

router = APIRouter(prefix="/categorizer", tags=["categorizer"])

# Request/Response Models
class CategorizationRequest(BaseModel):
    """Request model for merchant categorization"""
    merchant: str = Field(..., min_length=1, description="Merchant name to categorize")
    amount: Optional[float] = Field(None, gt=0, description="Transaction amount (optional)")

class CategorizationResponse(BaseModel):
    """Response model for merchant categorization"""
    merchant: str
    category: str
    confidence: float
    confidence_level: str
    similar_merchants: List[str]
    needs_feedback: bool
    reasoning: Optional[str] = None

class FeedbackRequest(BaseModel):
    """Request model for categorization feedback"""
    merchant: str = Field(..., min_length=1, description="Merchant name")
    correct_category: str = Field(..., min_length=1, description="Correct category")

class FeedbackResponse(BaseModel):
    """Response model for feedback submission"""
    success: bool
    message: str
    updated_category: str

class BatchCategorizationRequest(BaseModel):
    """Request model for batch categorization"""
    merchants: List[str] = Field(..., min_items=1, max_items=100, description="List of merchant names")

class BatchCategorizationResponse(BaseModel):
    """Response model for batch categorization"""
    results: List[CategorizationResponse]
    total_processed: int
    unknown_count: int
    needs_feedback_count: int

@router.post("/categorize", response_model=CategorizationResponse)
async def categorize_merchant(request: CategorizationRequest):
    """
    Categorize a single merchant using embeddings and similarity matching.
    """
    try:
        result = await categorizer.categorize_merchant(request.merchant, request.amount)

        return CategorizationResponse(
            merchant=request.merchant,
            category=result.category,
            confidence=result.confidence,
            confidence_level=result.confidence_level.value,
            similar_merchants=result.similar_merchants,
            needs_feedback=result.needs_feedback,
            reasoning=result.reasoning
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Categorization failed: {str(e)}")

@router.post("/categorize/batch", response_model=BatchCategorizationResponse)
async def categorize_merchants_batch(request: BatchCategorizationRequest):
    """
    Categorize multiple merchants in a single request.
    Useful for processing historical transaction data.
    """
    try:
        results = []
        unknown_count = 0
        needs_feedback_count = 0

        for merchant in request.merchants:
            result = await categorizer.categorize_merchant(merchant)

            if result.category == "unknown":
                unknown_count += 1
            if result.needs_feedback:
                needs_feedback_count += 1

            results.append(CategorizationResponse(
                merchant=merchant,
                category=result.category,
                confidence=result.confidence,
                confidence_level=result.confidence_level.value,
                similar_merchants=result.similar_merchants,
                needs_feedback=result.needs_feedback,
                reasoning=result.reasoning
            ))

        return BatchCategorizationResponse(
            results=results,
            total_processed=len(results),
            unknown_count=unknown_count,
            needs_feedback_count=needs_feedback_count
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch categorization failed: {str(e)}")

@router.post("/feedback", response_model=FeedbackResponse)
async def add_categorization_feedback(request: FeedbackRequest, current_user: Dict = Depends(get_current_user)):
    """
    Add user feedback to improve categorization accuracy.
    Requires authentication to track feedback quality.
    """
    try:
        user_id = current_user.get("user_id", "anonymous")
        success = await categorizer.add_feedback(request.merchant, request.correct_category, user_id)

        if success:
            return FeedbackResponse(
                success=True,
                message="Feedback recorded successfully",
                updated_category=request.correct_category
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to record feedback")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback submission failed: {str(e)}")

@router.get("/stats")
async def get_categorizer_stats() -> Dict[str, Any]:
    """
    Get categorizer statistics and health information.
    """
    try:
        stats = await categorizer.get_stats()
        return {
            "status": "healthy" if stats["initialized"] else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            **stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@router.post("/initialize")
async def initialize_categorizer():
    """
    Initialize or reinitialize the categorizer.
    Useful for admin operations or after configuration changes.
    """
    try:
        success = await categorizer.initialize()
        if success:
            return {"status": "initialized", "message": "Categorizer initialized successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to initialize categorizer")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")

@router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    try:
        stats = await categorizer.get_stats()
        return {
            "status": "healthy" if stats["initialized"] else "initializing",
            "backend": stats["backend"]["backend"],
            "categories": stats["categories_count"]
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}