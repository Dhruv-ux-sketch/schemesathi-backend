from fastapi import APIRouter, Request

from app.schemas import ChatRequest, ChatResponse, SourceChunk
from app.rag.vector_store import query as vector_query
from app.rag.llm import generate_answer, generate_follow_up_questions
from app.rag.profile_utils import profile_completion
from app.rate_limit import limiter, CHAT_LIMIT

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit(CHAT_LIMIT)
def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    profile_dict = payload.profile.model_dump(exclude_none=True) if payload.profile else None
    completion = profile_completion(profile_dict)

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
