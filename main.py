from fastapi import FastAPI
from pydantic import BaseModel
from core.agent import process_message
from admin.router import router as admin_router
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Claribizz Agent API")

app.include_router(admin_router)

# -------------------------------------------------------------------
# Request model
# -------------------------------------------------------------------
class ChatRequest(BaseModel):
    client_id: str
    message: str
    session_id: str  # phone number OR widget session ID


# -------------------------------------------------------------------
# Health check
# -------------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "Claribizz agent is running"}


# -------------------------------------------------------------------
# Core chat endpoint — used by all channels
# -------------------------------------------------------------------
@app.post("/chat")
def chat(request: ChatRequest):
    result = process_message(
        client_id=request.client_id,
        message=request.message,
        session_id=request.session_id
    )

    logger.info(f"Processing chat message for client {result}")

    if not result["client_found"]:
        return {
            "error": f"No client found with id '{request.client_id}'",
            "reply": None,
            "handoff": False
        }

    return result


# -------------------------------------------------------------------
# Channel webhooks plug in here later
# -------------------------------------------------------------------
# from channels.whatsapp import router as whatsapp_router
# from channels.widget import router as widget_router
# app.include_router(whatsapp_router, prefix="/channels/whatsapp")
# app.include_router(widget_router, prefix="/channels/widget")