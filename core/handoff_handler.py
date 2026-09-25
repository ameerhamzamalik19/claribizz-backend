HANDOFF_TRIGGER = "HANDOFF_NEEDED"


def needs_handoff(reply: str) -> bool:
    return HANDOFF_TRIGGER in reply.strip().upper()


def clean_reply(reply: str) -> str:
    """Remove the handoff trigger from the reply if present."""
    return reply.replace(HANDOFF_TRIGGER, "").strip()