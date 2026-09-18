from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.auth.service import require_csrf
from app.chat.service import ChatService
from app.config import get_settings
from app.database import get_db
from app.deps import get_active_user
from app.schemas import ChatRequest
from app.security.ratelimit import rate_limit_chat

router = APIRouter(tags=["chat"])


@router.post("/api/chat")
def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_active_user),
):
    require_csrf(request)
    rate_limit_chat(request, user.id)
    result = ChatService(db).ask(user, payload.query, payload.conversation_id)
    AuditService(db).record(
        actor_user_id=user.id,
        action="chat",
        request_id=request.headers.get("X-Request-ID", "chat"),
        status="SUCCESS",
        query=payload.query,
        result_count=result["result_count"],
        denied_result_count=result["denied_result_count"],
        ip=request.client.host if request.client else None,
        secret=get_settings().session_secret,
    )
    return {
        "conversation_id": result["conversation_id"],
        "answer": result["answer"],
        "citations": result["citations"],
    }


@router.get("/api/conversations")
def conversations(db: Session = Depends(get_db), user=Depends(get_active_user)):
    items = ChatService(db).list_conversations(user.id)
    return [
        {
            "id": c.id,
            "title": c.title,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in items
    ]


@router.get("/api/conversations/{conversation_id}")
def conversation(conversation_id: str, db: Session = Depends(get_db), user=Depends(get_active_user)):
    conv = ChatService(db).get_conversation(user.id, conversation_id)
    return {
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": json.loads(m.citations_json) if m.citations_json else [],
            }
            for m in conv.messages
        ],
    }
