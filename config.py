# config.py
import os
from dotenv import load_dotenv
import google.auth

load_dotenv()

# tokens and api keys
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # kept for legacy fallback
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# financial calculation constants
DIET_VALUE = 45.0
NIGHT_COEFF = 0.2

# Removed google-genai client initialization to use stable raw REST API
import aiohttp
from google.auth.transport.requests import Request

# Helper to get the access token for Vertex AI
async def get_vertex_token():
    try:
        credentials, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        credentials.refresh(Request())
        return credentials.token
    except Exception as e:
        import logging
        logging.error(f"Failed to get ADC token: {e}")
        return None

# Direct call to Vertex AI REST API
async def call_vertex_ai(contents, system_instruction=None, response_mime_type="text/plain"):
    token = await get_vertex_token()
    if not token:
        raise Exception("No GCP credentials available")

    # Hardcoded to kasia-497909 to avoid any project resolution issues
    url = "https://us-central1-aiplatform.googleapis.com/v1/projects/kasia-497909/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "responseMimeType": response_mime_type,
            "temperature": 0.1
        }
    }
    
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise Exception(f"Vertex API Error {resp.status}: {data}")
            
            # Parse response
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except KeyError:
                import logging
                logging.error(f"Unexpected Vertex response structure: {data}")
                return ""