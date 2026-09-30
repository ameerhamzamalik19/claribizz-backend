from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core.agent import process_message
from admin.router import router as admin_router
from channels.widget import router as widget_router

app = FastAPI(title="Claribizz Agent API")

# CORS — required so widget on client's website can call your API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"]
)

# Routers
app.include_router(admin_router)
app.include_router(widget_router)


# -------------------------------------------------------------------
# Request model
# -------------------------------------------------------------------
class ChatRequest(BaseModel):
    client_id: str
    message: str
    session_id: str


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

    if not result["client_found"]:
        return {
            "error": f"No client found with id '{request.client_id}'",
            "reply": None,
            "handoff": False
        }

    if result.get("debounced"):
        return {
            "reply": None,
            "handoff": False,
            "debounced": True
        }

    return result