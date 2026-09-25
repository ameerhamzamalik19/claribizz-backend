import os
from ollama import Client
from dotenv import load_dotenv
from core.prompts.system_prompt import build_system_prompt

load_dotenv()

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:cloud")

client = Client(
    host="https://api.ollama.com",
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"}
)


def get_ai_response(message: str, client_data: dict, history: list[dict] = []) -> str:
    try:
        messages = [
            {
                "role": "system",
                "content": build_system_prompt(client_data)
            },
            *history,
            {
                "role": "user",
                "content": message
            }
        ]

        response = client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            options={"temperature": 0.4}
        )

        return response.message.content

    except Exception as e:
        print(f"[AI error]: {e}")
        return "HANDOFF_NEEDED"