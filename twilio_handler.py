import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

def send_whatsapp_message(to: str, message: str):
    try:
        twilio_client.messages.create(
            from_=os.getenv("TWILIO_WHATSAPP_NUMBER"),
            to=to,
            body=message
        )
        print(f"Message sent to {to}")
    except Exception as e:
        print(f"Twilio error: {e}")