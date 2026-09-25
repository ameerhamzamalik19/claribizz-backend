import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ENABLED = os.getenv("TWILIO_ENABLED", "false").lower() == "true"

def send_whatsapp_message(to: str, message: str):
    if TWILIO_ENABLED:
        from twilio.rest import Client
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )
        client.messages.create(
            from_=os.getenv("TWILIO_WHATSAPP_NUMBER"),
            to=to,
            body=message
        )
        print(f"[TWILIO] Message sent to {to}")
    else:
        # Development mode — just print
        print(f"\n{'='*50}")
        print(f"[MOCK TWILIO] To: {to}")
        print(f"[MOCK TWILIO] Message: {message}")
        print(f"{'='*50}\n")