from fastapi import APIRouter, Request

from app.schemas import ChatRequest, ChatResponse, SourceChunk
from app.rag.vector_store import query as vector_query
from app.rag.llm import generate_answer, generate_follow_up_questions
from app.rate_limit import limiter, CHAT_LIMIT

router = APIRouter(prefix="/chat", tags=["chat"])

# Fields that count toward "profile completion" — must match whatever
# your frontend uses to calculate the % shown to the user, or the two
# numbers will disagree.
PROFILE_FIELDS = ["name", "state", "age", "occupation", "annual_income", "gender", "category"]


def _profile_completion(profile_dict: dict | None) -> float:
    if not profile_dict:
        return 0.0
    filled = sum(1 for f in PROFILE_FIELDS if profile_dict.get(f) not in (None, ""))
    return round(filled / len(PROFILE_FIELDS) * 100)


@router.post("", response_model=ChatResponse)
@limiter.limit(CHAT_LIMIT)
def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    profile_dict = payload.profile.model_dump(exclude_none=True) if payload.profile else None
    completion = _profile_completion(profile_dict)

    if completion == 0:
        return ChatResponse(
            answer=(
                "Your profile is 0% complete, so I can't check which schemes "
                "actually suit you yet — I'd just be guessing from your question "
                "text. Please complete your profile (state, age, occupation, "
                "income, gender, category) first, and I'll give you accurate, "
                "personalized recommendations."
            ),
            sources=[],
            follow_up_questions=[],
        )

    # 1. Retrieve relevant chunks from ChromaDB (local embeddings, no API key)
    hits = vector_query(payload.question)

    # 2. Generate the final answer (existing RAG answer flow remains unchanged)
    answer = generate_answer(payload.question, hits, profile_dict)

    # 3. Generate optional, context-aware follow-up questions.
    # This function has its own fallback and cannot break the main chat response.
    follow_up_questions = generate_follow_up_questions(
        question=payload.question,
        answer=answer,
        context_chunks=hits,
        language=payload.language,
    )

    # 4. Package sources for transparency / citation in the UI
    sources = [
        SourceChunk(
            scheme_name=h["scheme_name"],
            source_file=h["source_file"],
            text=h["text"],
            score=round(h["score"], 4),
        )
        for h in hits
    ]

    return ChatResponse(
        answer=answer,
        sources=sources,
        follow_up_questions=follow_up_questions,
    )
