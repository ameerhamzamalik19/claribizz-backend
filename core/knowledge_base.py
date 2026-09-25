import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_ENABLED = os.getenv("SUPABASE_ENABLED", "false").lower() == "true"

# -------------------------------------------------------------------
# Mock clients for development
# -------------------------------------------------------------------
MOCK_CLIENTS = {
    "test-client": {
        "client_id": "test-client",
        "business_name": "Karachi Bakers",
        "business_description": (
            "A home bakery based in Karachi selling custom cakes, "
            "cupcakes, and dessert boxes. We take orders 3 days in advance."
        ),
        "timings": "Monday to Saturday, 10am to 8pm. Closed on Sundays.",
        "location": "We deliver within Karachi only. Areas: DHA, Clifton, Gulshan, PECHS, Nazimabad.",
        "pricing": (
            "Custom cakes start from Rs. 2,500. "
            "Cupcakes Rs. 150 each, minimum order 6. "
            "Dessert boxes start from Rs. 1,200."
        ),
        "faqs": [
            {
                "question": "How do I place an order?",
                "answer": "Send us your order details and date on WhatsApp. We confirm within 2 hours."
            },
            {
                "question": "Do you do same day orders?",
                "answer": "No, we need at least 3 days notice for all orders."
            },
            {
                "question": "Can I customize the design?",
                "answer": "Yes, share a reference image and we will do our best to match it."
            },
            {
                "question": "What payment methods do you accept?",
                "answer": "Easypaisa, JazzCash, and bank transfer. Payment in advance required."
            }
        ],
        "tone": (
            "Warm, friendly, and helpful. "
            "Speak like a friendly small business owner, not a corporate rep."
        ),
        "handoff_message": (
            "Let me connect you with our team — "
            "they will get back to you shortly!"
        ),
        "owner_contact": "+923001234567",
        "whatsapp_number": ""
    }
}


def get_client(client_id: str) -> dict | None:
    if SUPABASE_ENABLED:
        return _get_from_supabase(client_id)
    return MOCK_CLIENTS.get(client_id)


def _get_from_supabase(client_id: str) -> dict | None:
    try:
        from supabase import create_client
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

        # Fetch client
        client_response = (
            supabase.table("clients")
            .select("*")
            .eq("client_id", client_id)
            .single()
            .execute()
        )

        if not client_response.data:
            return None

        client = client_response.data

        # Fetch FAQs separately
        faqs_response = (
            supabase.table("client_faqs")
            .select("question, answer")
            .eq("client_id", client_id)
            .order("order_index")
            .execute()
        )

        client["faqs"] = faqs_response.data or []

        return client

    except Exception as e:
        print(f"[Supabase error]: {e}")
        return None