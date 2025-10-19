import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found in environment variables")

# ✅ FIX: remove the extra “models/” 
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent?key={API_KEY}"

prompt = "Say: Gemini 2.5 Flash API connection successful "

payload = {
    "contents": [
        {"role": "user", "parts": [{"text": prompt}]}
    ]
}

try:
    response = requests.post(API_URL, json=payload)
    response.raise_for_status()
    data = response.json()

    print("✅ Gemini API is working!")
    print("Model:", MODEL)
    print("Response:")
    print(data["candidates"][0]["content"]["parts"][0]["text"])

except requests.exceptions.RequestException as e:
    print("❌ Error connecting to Gemini API:")
    print(e)
    if 'response' in locals() and response is not None:
        print("Response text:", response.text)
