"""
Pydantic models shared across routes.
"""
from typing import Optional
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Optional profile info used to personalize retrieval + answers."""
    state: Optional[str] = None
    age: Optional[int] = None
    occupation: Optional[str] = None            # e.g. "student", "farmer", "business_owner"
    annual_income: Optional[int] = None
    gender: Optional[str] = None
    category: Optional[str] = None              # e.g. "General", "SC", "ST", "OBC" if relevant to schemes


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User's natural-language question")
    profile: Optional[UserProfile] = None
    language: str = Field(default="en", description="ISO code: 'en', 'hi', etc.")


class SourceChunk(BaseModel):
    scheme_name: str
    source_file: str
    text: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    # Backward-compatible addition. Existing clients can ignore this field.
    follow_up_questions: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "This information is generated from official scheme documents but may be "
        "outdated or incomplete. Please verify details on the official portal "
        "before applying."
    )


class SchemeUploadResponse(BaseModel):
    filename: str
    chunks_added: int
    status: str


# ---- Auth ----

class SignupRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    state: Optional[str] = None
    age: Optional[int] = None
    occupation: Optional[str] = None
    annual_income: Optional[int] = None
    gender: Optional[str] = None
    category: Optional[str] = None
    is_admin: bool = False

    model_config = {"from_attributes": True}


# ---- Chat history ----

class ChatCreate(BaseModel):
    title: Optional[str] = "New chat"


class ChatSummary(BaseModel):
    id: str
    title: str

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list[SourceChunk] = []
    follow_up_questions: list[str] = []


class ChatDetail(BaseModel):
    id: str
    title: str
    messages: list[MessageOut]


# ---- Bookmarks ----

class BookmarkCreate(BaseModel):
    scheme_name: str
    source_file: Optional[str] = None
    note: Optional[str] = None


class BookmarkOut(BaseModel):
    id: str
    scheme_name: str
    source_file: Optional[str] = None
    note: Optional[str] = None

    model_config = {"from_attributes": True}
