# Put this file at: app/rag/profile_utils.py (or any shared location both
# chat.py and chats.py can import from).
#
# Both /chat and /chats/{chat_id}/messages must use this SAME list and SAME
# function. Two independent copies is exactly what caused the bug where
# editing chat.py did nothing, because chats.py is the route the frontend
# actually calls.

PROFILE_FIELDS = ["name", "state", "age", "occupation", "annual_income", "gender", "category"]


def profile_completion(profile_dict: dict | None) -> float:
    if not profile_dict:
        return 0.0
    filled = sum(1 for f in PROFILE_FIELDS if profile_dict.get(f) not in (None, ""))
    return round(filled / len(PROFILE_FIELDS) * 100)
