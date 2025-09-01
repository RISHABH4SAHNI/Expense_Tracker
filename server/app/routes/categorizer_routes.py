"""
FastAPI routes for merchant categorization functionality.

Updated with personalization features:
- User-defined override rules management
This module provides REST API endpoints for:
1. Categorizing merchants using embeddings with user overrides
2. Adding user feedback for improving categorization
3. Getting categorizer statistics and health
4. Batch categorization for multiple merchants
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..services.categorizer import categorizer, CategoryResult, CategorizationConfidence, UserOverrideRule
from ..deps.auth import get_current_user

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

class UserOverrideRequest(BaseModel):
    """Request model for creating user override rules"""
    merchant_pattern: str = Field(..., min_length=1, description="Merchant pattern to match")
    category: str = Field(..., min_length=1, description="Category to assign")

class UserOverrideUpdateRequest(BaseModel):
    """Request model for updating user override rules"""
    merchant_pattern: Optional[str] = Field(None, min_length=1, description="New merchant pattern")
    category: Optional[str] = Field(None, min_length=1, description="New category")
    is_active: Optional[bool] = Field(None, description="New active status")

class UserOverrideResponse(BaseModel):
    """Response model for user override rules"""
    id: str
    merchant_pattern: str
    category: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class UserOverrideListResponse(BaseModel):
    """Response model for list of user override rules"""
    rules: List[UserOverrideResponse]
    total_count: int

class UserOverrideActionResponse(BaseModel):
    """Response model for override rule actions"""
    success: bool
    message: str

@router.post("/categorize", response_model=CategorizationResponse)
async def categorize_merchant(request: CategorizationRequest, current_user: Dict = Depends(get_current_user)):
    """
    Categorize a single merchant using embeddings and similarity matching.
    Now includes user-defined override rules.
    """
    try:
        user_id = current_user.get("user_id")
        result = await categorizer.categorize_merchant(request.merchant, user_id, request.amount)

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
async def categorize_merchants_batch(request: BatchCategorizationRequest, current_user: Dict = Depends(get_current_user)):
    """
    Categorize multiple merchants in a single request.
    Applies user overrides to each merchant.
    Useful for processing historical transaction data.
    """
    try:
        results = []
        unknown_count = 0
        needs_feedback_count = 0

        user_id = current_user.get("user_id")
        for merchant in request.merchants:
            result = await categorizer.categorize_merchant(merchant, user_id)

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
async def add_categorization_feedback(request: FeedbackRequest):
    """
    Add user feedback to improve categorization accuracy.
    """
    try:
        success = await categorizer.add_feedback(request.merchant, request.correct_category, "api_user")

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

# User Override Management Endpoints

@router.post("/overrides", response_model=UserOverrideActionResponse)
async def create_user_override(request: UserOverrideRequest, current_user: Dict = Depends(get_current_user)):
    """
    Create a new user-defined categorization override rule.
    Example: Always categorize "Uber" as "business" instead of "transport".
    """
    try:
        user_id = current_user.get("user_id")
        success = await categorizer.add_user_override(user_id, request.merchant_pattern, request.category)

        if success:
            return UserOverrideActionResponse(
                success=True,
                message=f"Override rule created: '{request.merchant_pattern}' → {request.category}"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create override rule")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create override rule: {str(e)}")

@router.get("/overrides", response_model=UserOverrideListResponse)
async def get_user_overrides(current_user: Dict = Depends(get_current_user)):
    """
    Get all categorization override rules for the current user.
    """
    try:
        user_id = current_user.get("user_id")
        rules = await categorizer.get_user_overrides(user_id)

        rule_responses = []
        for rule in rules:
            rule_responses.append(UserOverrideResponse(
                id=rule.id,
                merchant_pattern=rule.merchant_pattern,
                category=rule.category,
                is_active=rule.is_active,
                created_at=rule.created_at,
                updated_at=rule.updated_at
            ))

        return UserOverrideListResponse(
            rules=rule_responses,
            total_count=len(rule_responses)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get override rules: {str(e)}")

@router.put("/overrides/{rule_id}", response_model=UserOverrideActionResponse)
async def update_user_override(rule_id: str, request: UserOverrideUpdateRequest, current_user: Dict = Depends(get_current_user)):
    """
    Update an existing user override rule.
    """
    try:
        user_id = current_user.get("user_id")
        success = await categorizer.update_user_override(
            user_id, rule_id, 
            request.merchant_pattern, request.category, request.is_active
        )

        if success:
            return UserOverrideActionResponse(
                success=True,
                message=f"Override rule {rule_id} updated successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Override rule not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update override rule: {str(e)}")

@router.delete("/overrides/{rule_id}", response_model=UserOverrideActionResponse)
async def delete_user_override(rule_id: str, current_user: Dict = Depends(get_current_user)):
    """
    Delete a user override rule.
    """
    try:
        user_id = current_user.get("user_id")
        success = await categorizer.delete_user_override(user_id, rule_id)

        if success:
            return UserOverrideActionResponse(
                success=True,
                message=f"Override rule {rule_id} deleted successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Override rule not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete override rule: {str(e)}")

# Utility endpoint to test override rules
@router.post("/overrides/test")
async def test_override_rule(merchant: str, current_user: Dict = Depends(get_current_user)):
    """
    Test how a merchant would be categorized with current override rules.
    """
    try:
        user_id = current_user.get("user_id")
        result = await categorizer.categorize_merchant(merchant, user_id)

        return {
            "merchant": merchant,
            "category": result.category,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "used_override": "User-defined override rule" in (result.reasoning or "")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test categorization: {str(e)}")