"""
Database models for user accounts, chat history, and bookmarks.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)

    # Profile fields used to personalize scheme recommendations
    name = Column(String, nullable=True)
    state = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    occupation = Column(String, nullable=True)
    annual_income = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    category = Column(String, nullable=True)

    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    bookmarks = relationship("Bookmark", back_populates="user", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, default="New chat")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    user = relationship("User", back_populates="chats")
    messages = relationship(
        "Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    chat_id = Column(String, ForeignKey("chats.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    sources_json = Column(Text, nullable=True)  # JSON-serialized list of source chunks
    follow_up_questions_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)

    chat = relationship("Chat", back_populates="messages")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    scheme_name = Column(String, nullable=False)
    source_file = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="bookmarks")
