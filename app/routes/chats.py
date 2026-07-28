import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Chat, Message
from app.auth import get_current_user
from app.schemas import (
    ChatCreate, ChatSummary, ChatDetail, MessageOut,
    ChatRequest, ChatResponse, SourceChunk,
)
from app.rag.vector_store import query as vector_query
from app.rag.llm import generate_answer, generate_follow_up_questions
from app.rate_limit import limiter, CHAT_LIMIT

router = APIRouter(prefix="/chats", tags=["chat-history"])


@router.post("", response_model=ChatSummary)
def create_chat(
    request: ChatCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = Chat(user_id=current_user.id, title=request.title or "New chat")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get("", response_model=list[ChatSummary])
def list_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chats = (
        db.query(Chat)
        .filter(Chat.user_id == current_user.id)
        .order_by(Chat.updated_at.desc())
        .all()
    )
    return chats


@router.get("/{chat_id}", response_model=ChatDetail)
def get_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(404, "Chat not found")

    messages = [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            sources=json.loads(m.sources_json) if m.sources_json else [],
            follow_up_questions=json.loads(m.follow_up_questions_json) if m.follow_up_questions_json else [],
        )
        for m in chat.messages
    ]
    return ChatDetail(id=chat.id, title=chat.title, messages=messages)


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(404, "Chat not found")
    db.delete(chat)
    db.commit()
    return {"status": "deleted"}


@router.post("/{chat_id}/messages", response_model=ChatResponse)
@limiter.limit(CHAT_LIMIT)
def send_message(
    request: Request,
    chat_id: str,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Same RAG pipeline as the standalone /chat endpoint, but persists both the
    user's question and the assistant's answer to this chat's history, and
    auto-uses the logged-in user's saved profile if none is passed explicitly.
    """
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(404, "Chat not found")

    # Use the payload's profile if given, otherwise fall back to the user's saved profile
    if payload.profile:
        profile_dict = payload.profile.model_dump(exclude_none=True)
    else:
        profile_dict = {
            k: v for k, v in {
                "state": current_user.state,
                "age": current_user.age,
                "occupation": current_user.occupation,
                "annual_income": current_user.annual_income,
                "gender": current_user.gender,
                "category": current_user.category,
            }.items() if v is not None
        } or None

   
    hits = vector_query(payload.question)

if not hits:
    answer = "I couldn't find a scheme confidently matching your question. Could you rephrase it or share more details (like your state, occupation, or what kind of support you're looking for)?"
    follow_ups = []
    sources = []
else:
    answer = generate_answer(payload.question, hits, profile_dict)
    follow_ups = generate_follow_up_questions(
        question=payload.question, answer=answer, context_chunks=hits, language=payload.language,
    )
    sources = [
        SourceChunk(scheme_name=h["scheme_name"], source_file=h["source_file"],
                    text=h["text"], score=round(h["score"], 4))
        for h in hits
    ]

    # Persist both sides of the exchange
    db.add(Message(chat_id=chat.id, role="user", content=payload.question))
    db.add(Message(
        chat_id=chat.id, role="assistant", content=answer,
        sources_json=json.dumps([s.model_dump() for s in sources]),
        follow_up_questions_json=json.dumps(follow_ups),
    ))

    # Auto-title new chats from the first question asked
    if chat.title == "New chat":
        chat.title = payload.question[:60]

    db.commit()

    return ChatResponse(answer=answer, sources=sources, follow_up_questions=follow_ups)
