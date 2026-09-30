from core.knowledge_base import get_client
from core.ai_handler import get_ai_response
from core.handoff_handler import needs_handoff, clean_reply
from core.rate_limiter import check_limits
from core.session_manager import (
    get_or_create_session,
    get_history_for_ai,
    append_message,
    is_too_fast,
    mark_handoff
)


def process_message(client_id: str, message: str, session_id: str) -> dict:
    """
    Core agent — takes a message, client_id, and session_id.
    Returns a response. Completely channel agnostic.
    """

    # 1. Load client knowledge base
    client = get_client(client_id)

    if not client:
        return {
            "reply": None,
            "handoff": False,
            "handoff_message": None,
            "owner_contact": None,
            "client_found": False,
            "session_id": session_id
        }

    # 2. Debounce — ignore if same session messages too fast
    if is_too_fast(session_id):
        return {
            "reply": "Kindly wait between messages",
            "handoff": False,
            "handoff_message": None,
            "owner_contact": None,
            "client_found": True,
            "session_id": session_id,
            "debounced": True
        }

    # 3. Rate limiting and quota checks
    limit_check = check_limits(client_id, session_id)
    if not limit_check["allowed"]:
        return {
            "reply": limit_check["message"],
            "handoff": False,
            "handoff_message": None,
            "owner_contact": None,
            "client_found": True,
            "session_id": session_id,
            "rate_limited": True,
            "limit_reason": limit_check["reason"]
        }

    # 4. Get or create session
    session = get_or_create_session(session_id, client_id)

    # 5. Load conversation history
    history = get_history_for_ai(session_id)

    # 6. Save user message to history
    append_message(session_id, "user", message)

    # 7. Get AI response with full history
    raw_reply = get_ai_response(message, client, history)

    # 8. Check if handoff is needed
    if needs_handoff(raw_reply):
        handoff_msg = client["handoff_message"]
        append_message(session_id, "assistant", handoff_msg)
        mark_handoff(session_id)
        return {
            "reply": handoff_msg,
            "handoff": True,
            "handoff_message": handoff_msg,
            "owner_contact": client.get("owner_contact"),
            "client_found": True,
            "session_id": session["session_id"]
        }

    # 9. Save assistant reply to history
    reply = clean_reply(raw_reply)
    append_message(session_id, "assistant", reply)

    return {
        "reply": reply,
        "handoff": False,
        "handoff_message": None,
        "owner_contact": None,
        "client_found": True,
        "session_id": session["session_id"]
    }