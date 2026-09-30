HANDOFF_TRIGGER = "HANDOFF_NEEDED"


def needs_handoff(reply: str) -> bool:
    # Only trigger handoff if the reply is EXACTLY the trigger
    # Prevents the AI from embedding the trigger inside other text
    return reply.strip().upper() == HANDOFF_TRIGGER


def clean_reply(reply: str) -> str:
    """Remove the handoff trigger from the reply if present."""
    return reply.replace(HANDOFF_TRIGGER, "").strip()