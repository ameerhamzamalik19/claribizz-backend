from core.knowledge_base import get_client
from core.ai_handler import get_ai_response
from core.handoff_handler import needs_handoff, clean_reply
from core.session_manager import (
    get_or_create_session,
    get_history_for_ai,
    append_message
)

def process_message(client_id: str, message: str, session_id: str) -> dict:
    """
    Core agent — takes a message, client_id, and session_id.
    Returns a response. Completely channel agnostic.

    session_id can be:
    - A phone number: +923001234567 or whatsapp:+923001234567
    - A widget session ID: abc-xyz-123

    Returns:
    {
        "reply": str,
        "handoff": bool,
        "handoff_message": str | None,
        "owner_contact": str | None,
        "client_found": bool,
        "session_id": str
    }
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

    # 2. Get or create session
    session = get_or_create_session(session_id, client_id)

    # 3. Load conversation history
    history = get_history_for_ai(session_id)

    # 4. Save user message to history
    append_message(session_id, "user", message)

    # 5. Get AI response with full history
    raw_reply = get_ai_response(message, client, history)

    # 6. Check if handoff is needed
    if needs_handoff(raw_reply):
        handoff_msg = client["handoff_message"]
        append_message(session_id, "assistant", handoff_msg)
        return {
            "reply": handoff_msg,
            "handoff": True,
            "handoff_message": handoff_msg,
            "owner_contact": client.get("owner_contact"),
            "client_found": True,
            "session_id": session["session_id"]
        }

    # 7. Save assistant reply to history
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