from __future__ import annotations

import json
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.service import AuthUser
from app.config import Settings, get_settings
from app.llm.provider import INSUFFICIENT, SYSTEM_PROMPT, LLMProvider, build_llm_provider
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.retrieval.context import build_authorized_context, citations_from, relevant_authorized_chunks
from app.retrieval.retriever import Retriever


class ChatService:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        retriever: Retriever | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.retriever = retriever or Retriever(db, self.settings)
        self.llm = llm or build_llm_provider(self.settings)

    def ask(
        self,
        user: AuthUser,
        query: str,
        conversation_id: str | None,
    ) -> dict:
        db_user = self.db.get(User, user.id)
        if db_user is None or not db_user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        if db_user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password change required",
            )

        conversation = self._get_or_create_conversation(user.id, conversation_id)
        history = [
            {"role": m.role, "content": m.content}
            for m in conversation.messages[-8:]
        ]

        # Enhance query with user name for better retrieval if they ask about themselves
        search_query = query
        lower_query = query.lower()
        if any(word in lower_query.split() for word in ["my", "i", "me", "mine", "myself"]):
            search_query = f"{query} {user.full_name}"

        chunks, denied = self.retriever.retrieve(user, search_query)
        chunks = relevant_authorized_chunks(query, chunks)
        # Re-load user in case they were disabled during retrieval
        self.db.refresh(db_user)
        if not db_user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

        # Only inject the profile context if they explicitly ask about themselves using self pronouns
        asking_about_self = any(
            word.strip("?,.!") in ["my", "i", "me", "mine", "myself"] 
            for word in lower_query.split()
        ) or "who am i" in lower_query

        if asking_about_self:
            from app.retrieval.retriever import AuthorizedChunk
            roles_str = ", ".join(user.role_names) if user.role_names else "Employee"
            profile_chunk = AuthorizedChunk(
                chunk_id="user-profile-001",
                document_id="user-profile",
                document_title="Employee Account Details",
                content=f"Employee Name: {user.full_name}\nEmail: {user.email}\nRole: {roles_str}\nCompany: {user.company_name or 'N/A'}",
                score=1.0,
                page_number=1,
                section_title="Profile",
                source_location=None,
            )
            chunks.insert(0, profile_chunk)

        context = build_authorized_context(chunks, self.settings)
        if not context:
            answer = INSUFFICIENT
            citations: list[dict] = []
        else:
            personalized_prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"IMPORTANT: The current user asking this question is {user.full_name} ({user.email}). "
                "If they ask about themselves (using 'I', 'me', 'my'), use their name to find relevant information in the context."
            )
            answer = self.llm.generate(personalized_prompt, context, query, history)
            citations = citations_from(chunks)
            if not answer.strip():
                answer = INSUFFICIENT
                citations = []

        user_msg = Message(conversation_id=conversation.id, role="user", content=query)
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            citations_json=json.dumps(citations),
        )
        self.db.add_all([user_msg, assistant_msg])
        if conversation.title == "Conversation":
            conversation.title = query[:80]
        self.db.commit()
        return {
            "conversation_id": conversation.id,
            "answer": answer,
            "citations": citations,
            "result_count": len(chunks),
            "denied_result_count": denied,
        }

    def list_conversations(self, user_id: str) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )

    def get_conversation(self, user_id: str, conversation_id: str) -> Conversation:
        conv = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .one_or_none()
        )
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return conv

    def _get_or_create_conversation(self, user_id: str, conversation_id: str | None) -> Conversation:
        if conversation_id:
            conv = self.db.get(Conversation, conversation_id)
            if conv is None or conv.user_id != user_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
            return conv
        conv = Conversation(id=str(uuid4()), user_id=user_id, title="Conversation")
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv
