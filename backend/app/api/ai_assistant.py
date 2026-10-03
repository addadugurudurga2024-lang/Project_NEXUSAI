"""
AI Assistant Router — Phase 8: AI Decision Assistant
Endpoint:
  POST /ai-assistant/chat
RBAC enforced at backend level; calls ai_assistant_service.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.core.deps import get_current_user
from app.db.database import get_database
from app.services.ai_assistant_service import ask_decision_assistant

router = APIRouter()


class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    project_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    response: str
    intent: str
    context_summary: Dict[str, Any] = {}
    recommendations: List[Dict[str, Any]] = []


@router.post("/chat", response_model=ChatResponse)
async def chat_with_decision_assistant(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Query the NexusAI Decision Assistant with a natural-language question.
    Grounded strictly in authorized NexusAI project, task, and ML prediction data.
    """
    history_dicts = [h.dict() for h in request.history] if request.history else None
    
    result = await ask_decision_assistant(
        user=current_user,
        db=db,
        message=request.message,
        project_id=request.project_id,
        history=history_dicts,
    )
    
    # Sanitize recommendations and context_summary for Pydantic serialization
    from bson import ObjectId

    cleaned_recs = []
    for r in result.get("recommendations", []):
        item = dict(r)
        if "_id" in item:
            item["id"] = str(item["_id"])
            del item["_id"]
        # Convert any other ObjectIds
        for k, v in list(item.items()):
            if isinstance(v, ObjectId):
                item[k] = str(v)
        cleaned_recs.append(item)

    cleaned_ctx = {}
    for k, v in result.get("context_summary", {}).items():
        cleaned_ctx[k] = str(v) if isinstance(v, ObjectId) else v

    return ChatResponse(
        response=result.get("response", ""),
        intent=result.get("intent", "general"),
        context_summary=cleaned_ctx,
        recommendations=cleaned_recs,
    )
