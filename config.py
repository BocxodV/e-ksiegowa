# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Токены и ключи
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL") 

# Константы расчетов
DIET_VALUE = 45.0
NIGHT_COEFF = 0.2