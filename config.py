# config.py
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# tokens and api keys
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # kept for legacy fallback
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# financial calculation constants
DIET_VALUE = 45.0
NIGHT_COEFF = 0.2

# Shared Gemini client singleton — created ONCE at startup, used everywhere
# Uses Vertex AI with Cloud Run service account (ADC) — no API key needed
gemini_client = genai.Client(vertexai=True, project="kasia-497909", location="us-central1")