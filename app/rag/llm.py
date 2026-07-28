"""
Thin abstraction so the rest of the app doesn't care which LLM provider
generates the final answer. Swap providers by changing LLM_PROVIDER in .env.

While LLM_PROVIDER=none, generate_answer() just formats the retrieved
chunks directly, no API key needed. Once you get a key, set the provider
and this starts calling the real model.
"""
from app.config import settings

SYSTEM_PROMPT = """You are SchemeSathi, an assistant that helps Indian citizens \
understand government schemes. You are given retrieved excerpts from official \
scheme documents and a user's question (and optionally their profile).

Rules:
- Base your answer ONLY on the provided excerpts. Do not invent scheme details, \
amounts, or deadlines that aren't in the excerpts.
- Write in simple, plain language — avoid bureaucratic jargon.
- If the excerpts don't contain enough information to answer, say so clearly \
and suggest the user check the official portal.
- When relevant, structure the answer with: Eligibility, Benefits, Documents \
Required, How to Apply.
- Keep tone warm and helpful, like explaining to a family member.
"""


def _build_user_message(question: str, context_chunks: list[dict], profile: dict | None) -> str:
    context_text = "\n\n".join(
        f"[Source: {c['scheme_name']} — {c['source_file']}]\n{c['text']}"
        for c in context_chunks
    )
    profile_text = f"\nUser profile: {profile}" if profile else ""
    return (
        f"Retrieved excerpts:\n{context_text}\n"
        f"{profile_text}\n\n"
        f"User question: {question}"
    )


def _fallback_answer(question: str, context_chunks: list[dict]) -> str:
    """No LLM key configured yet — return the raw retrieved excerpts so the
    RAG pipeline is still testable end-to-end."""
    if not context_chunks:
        return (
            "No LLM provider is configured yet, and no relevant scheme excerpts "
            "were found for this question. Once you add an OpenAI or Anthropic "
            "API key to .env, this will become a generated natural-language answer."
        )
    lines = [
        "[No LLM configured — showing raw retrieved excerpts. "
        "Add an API key to .env to get a generated natural-language answer.]\n"
    ]
    for c in context_chunks:
        lines.append(f"From {c['scheme_name']} ({c['source_file']}):\n{c['text']}\n")
    return "\n".join(lines)


def _call_openai(question: str, context_chunks: list[dict], profile: dict | None) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(question, context_chunks, profile)},
        ],
        max_tokens=800,
    )
    return response.choices[0].message.content


def _call_anthropic(question: str, context_chunks: list[dict], profile: dict | None) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": _build_user_message(question, context_chunks, profile)},
        ],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _call_gemini(question: str, context_chunks: list[dict], profile: dict | None) -> str:
    # Uses Gemini's REST API directly via `requests` so no extra SDK dependency is needed.
    # NOTE: newer Gemini "Auth keys" (format AQ.Ab...) are sent via the x-goog-api-key
    # header rather than the old ?key= query string.
    import requests

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": settings.GEMINI_API_KEY,
    }
    user_message = _build_user_message(question, context_chunks, profile)
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {"maxOutputTokens": 2048},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if not response.ok:
        # Surface Google's actual error message instead of a generic 500,
        # makes debugging model-name / key issues much faster.
        raise RuntimeError(f"Gemini API error {response.status_code}: {response.text}")
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def generate_answer(question: str, context_chunks: list[dict], profile: dict | None = None) -> str:
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai" and settings.OPENAI_API_KEY:
        return _call_openai(question, context_chunks, profile)
    elif provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        return _call_anthropic(question, context_chunks, profile)
    elif provider == "gemini" and settings.GEMINI_API_KEY:
        return _call_gemini(question, context_chunks, profile)
    else:
        return _fallback_answer(question, context_chunks)

FOLLOW_UP_SYSTEM_PROMPT = """You create helpful follow-up questions for SchemeSathi, an Indian government-scheme assistant.

Return ONLY a JSON array containing exactly 4 short questions.
Rules:
- Base every question only on the user's question, generated answer, and retrieved excerpts.
- Make the questions practical and non-repetitive.
- Prefer topics such as eligibility verification, documents, benefits, official application steps, exclusions, or status tracking when supported.
- Do not invent facts, scheme names, portals, amounts, or deadlines.
- Each question must be understandable on its own and contain at most 14 words.
- Use the requested language where possible.
"""


def _build_follow_up_message(
    question: str,
    answer: str,
    context_chunks: list[dict],
    language: str,
) -> str:
    excerpts = "\n\n".join(
        f"[Source: {c['scheme_name']} — {c['source_file']}]\n{c['text']}"
        for c in context_chunks[:4]
    )
    return (
        f"Requested language: {language}\n\n"
        f"Original user question: {question}\n\n"
        f"Generated answer: {answer}\n\n"
        f"Retrieved excerpts:\n{excerpts}"
    )


def _parse_follow_up_questions(raw_text: str) -> list[str]:
    """Parse a model response safely and return up to four unique questions."""
    import json
    import re

    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Recover a JSON array if the model added a small amount of surrounding text.
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    if not isinstance(parsed, list):
        return []

    questions: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, str):
            continue
        question_text = " ".join(item.strip().split())
        if not question_text:
            continue
        if not question_text.endswith("?"):
            question_text += "?"
        key = question_text.casefold()
        if key in seen:
            continue
        seen.add(key)
        questions.append(question_text)
        if len(questions) == 4:
            break
    return questions


def _fallback_follow_up_questions(question: str, context_chunks: list[dict]) -> list[str]:
    """Safe contextual questions used if no provider is configured or generation fails."""
    scheme_name = next(
        (c.get("scheme_name", "").strip() for c in context_chunks if c.get("scheme_name")),
        "this scheme",
    )
    lower_context = " ".join(c.get("text", "") for c in context_chunks).lower()

    candidates = [
        f"How can I verify my eligibility for {scheme_name}?",
        f"Which documents are required for {scheme_name}?",
        f"How can I apply for {scheme_name} officially?",
    ]
    if any(word in lower_context for word in ("benefit", "amount", "pension", "loan", "assistance")):
        candidates.append(f"What benefits can I receive under {scheme_name}?")
    else:
        candidates.append(f"Who is not eligible for {scheme_name}?")

    # Keep the response predictable and bounded.
    return candidates[:4]


def _call_openai_follow_ups(
    question: str,
    answer: str,
    context_chunks: list[dict],
    language: str,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": FOLLOW_UP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_follow_up_message(question, answer, context_chunks, language),
            },
        ],
        max_tokens=220,
        temperature=0.2,
    )
    return response.choices[0].message.content or "[]"


def _call_anthropic_follow_ups(
    question: str,
    answer: str,
    context_chunks: list[dict],
    language: str,
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=220,
        temperature=0.2,
        system=FOLLOW_UP_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _build_follow_up_message(question, answer, context_chunks, language),
            }
        ],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _call_gemini_follow_ups(
    question: str,
    answer: str,
    context_chunks: list[dict],
    language: str,
) -> str:
    import requests

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": settings.GEMINI_API_KEY,
    }
    payload = {
        "system_instruction": {"parts": [{"text": FOLLOW_UP_SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": _build_follow_up_message(
                            question, answer, context_chunks, language
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 220,
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if not response.ok:
        raise RuntimeError(f"Gemini API error {response.status_code}: {response.text}")
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def generate_follow_up_questions(
    question: str,
    answer: str,
    context_chunks: list[dict],
    language: str = "en",
) -> list[str]:
    """Generate four grounded follow-up questions without risking the main answer.

    Any provider or parsing failure falls back to deterministic contextual prompts,
    so /chat remains reliable and backward compatible.
    """
    if not context_chunks:
        return []

    provider = settings.LLM_PROVIDER.lower()
    try:
        if provider == "openai" and settings.OPENAI_API_KEY:
            raw = _call_openai_follow_ups(
                question, answer, context_chunks, language
            )
        elif provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            raw = _call_anthropic_follow_ups(
                question, answer, context_chunks, language
            )
        elif provider == "gemini" and settings.GEMINI_API_KEY:
            raw = _call_gemini_follow_ups(
                question, answer, context_chunks, language
            )
        else:
            return _fallback_follow_up_questions(question, context_chunks)

        parsed = _parse_follow_up_questions(raw)
        return parsed if len(parsed) >= 2 else _fallback_follow_up_questions(
            question, context_chunks
        )
    except Exception:
        # Follow-up suggestions are an enhancement; they must never break chat.
        return _fallback_follow_up_questions(question, context_chunks)

