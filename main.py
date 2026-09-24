from fastapi import FastAPI, Request
from twilio_handler import send_whatsapp_message
from claude_handler import get_claude_response
from knowledge_base import get_client_knowledge
from handoff_handler import should_handoff

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Claribizz backend is running"}

@app.post("/webhook")
async def webhook(request: Request):
    form_data = await request.form()
    
    incoming_msg = form_data.get("Body", "").strip()
    from_number = form_data.get("From", "").strip()
    to_number = form_data.get("To", "").strip()

    print(f"Message from {from_number}: {incoming_msg}")

    # Get client knowledge base using their WhatsApp number
    client = get_client_knowledge(to_number)

    if not client:
        send_whatsapp_message(from_number, "Sorry, this service is not configured yet.")
        return {"status": "no client found"}

    # Get Claude's response
    reply = get_claude_response(incoming_msg, client)

    # Check if we need human handoff
    if should_handoff(reply):
        send_whatsapp_message(from_number, client["handoff_message"])
        # TODO: notify client via their number
        return {"status": "handoff triggered"}

    send_whatsapp_message(from_number, reply)
    return {"status": "reply sent"}