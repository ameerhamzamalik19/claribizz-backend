import os
import re
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

TABLE = "conversation_sessions"

# Max messages to keep in history sent to AI
# Older messages beyond this are stored in Supabase but not sent to AI
MAX_HISTORY_WINDOW = 20


# -------------------------------------------------------------------
# Normalize phone numbers or session IDs into a consistent format
# Phone: +923001234567 → session_id: phone_923001234567
# Widget: abc-123      → session_id: widget_abc-123
# -------------------------------------------------------------------
def normalize_session_id(raw_id: str) -> str:
    # Detect phone number (starts with + or whatsapp: prefix)
    cleaned = raw_id.replace("whatsapp:", "").strip()
    if re.match(r"^\+?\d{10,15}$", cleaned):
        digits = cleaned.lstrip("+")
        return f"phone_{digits}"
    # Otherwise treat as widget session ID
    return f"widget_{raw_id}"


# -------------------------------------------------------------------
# Get or create a session
# -------------------------------------------------------------------
def get_or_create_session(raw_id: str, client_id: str) -> dict:
    session_id = normalize_session_id(raw_id)

    try:
        # Try to fetch existing session
        response = (
            supabase.table(TABLE)
            .select("*")
            .eq("session_id", session_id)
            .single()
            .execute()
        )
        return response.data

    except Exception:
        # Session doesn't exist — create it
        new_session = {
            "session_id": session_id,
            "client_id": client_id,
            "messages": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        supabase.table(TABLE).insert(new_session).execute()
        return new_session


# -------------------------------------------------------------------
# Append a message to session history
# role: "user" or "assistant"
# -------------------------------------------------------------------
def append_message(raw_id: str, role: str, content: str):
    session_id = normalize_session_id(raw_id)

    try:
        # Fetch current messages
        response = (
            supabase.table(TABLE)
            .select("messages")
            .eq("session_id", session_id)
            .single()
            .execute()
        )
        messages = response.data.get("messages", [])

        # Append new message
        messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Save back
        supabase.table(TABLE).update({
            "messages": messages,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("session_id", session_id).execute()

    except Exception as e:
        print(f"[Session error - append_message]: {e}")


# -------------------------------------------------------------------
# Get conversation history formatted for AI
# Returns last MAX_HISTORY_WINDOW messages, timestamps stripped
# -------------------------------------------------------------------
def get_history_for_ai(raw_id: str) -> list[dict]:
    session_id = normalize_session_id(raw_id)

    try:
        response = (
            supabase.table(TABLE)
            .select("messages")
            .eq("session_id", session_id)
            .single()
            .execute()
        )
        messages = response.data.get("messages", [])

        # Keep only last N messages for AI context window
        recent = messages[-MAX_HISTORY_WINDOW:]

        # Strip timestamps — AI only needs role + content
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    except Exception as e:
        print(f"[Session error - get_history]: {e}")
        return []


# -------------------------------------------------------------------
# Clear a session (optional — for testing or reset)
# -------------------------------------------------------------------
def clear_session(raw_id: str):
    session_id = normalize_session_id(raw_id)
    try:
        supabase.table(TABLE).update({
            "messages": [],
            "updated_at": datetime.utcnow().isoformat()
        }).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"[Session error - clear_session]: {e}")