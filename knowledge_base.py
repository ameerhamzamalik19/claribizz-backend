import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def get_client_knowledge(whatsapp_number: str) -> dict | None:
    try:
        response = supabase.table("clients").select("*").eq("whatsapp_number", whatsapp_number).single().execute()
        return response.data
    except Exception as e:
        print(f"Supabase error: {e}")
        return None