import os
from anthropic import Anthropic
from prompts.system_prompt import build_system_prompt
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def get_claude_response(message: str, client_data: dict) -> str:
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=build_system_prompt(client_data),
            messages=[
                {"role": "user", "content": message}
            ]
        )
        return response.content[0].text
    except Exception as e:
        print(f"Claude error: {e}")
        return "HANDOFF_NEEDED"