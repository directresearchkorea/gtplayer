import os
from dotenv import load_dotenv
from google import genai
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def test():
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("Testing gemini-flash-lite-latest...")
    try:
        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents="Say hi"
        )
        print(f"Success: {response.text}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test()
