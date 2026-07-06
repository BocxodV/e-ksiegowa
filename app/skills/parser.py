import json
from datetime import datetime

from config import call_vertex_ai

async def parse_shift_text(raw_text: str) -> dict:
    """
    Parses unstructured text about a work shift and returns a structured dictionary
    matching the ShiftInfo schema using Gemini 2.5 Flash via Vertex AI.
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""Ты — высокоточный парсер данных для бухгалтерского учета. Твоя задача — извлекать факты из неструктурированного текста пользователя и возвращать их СТРОГО в формате JSON.

ТЕКУЩАЯ ДАТА: {current_date}. Используй ее для вычисления относительных дат (сегодня, вчера, позавчера).

Правила извлечения:

date: Дата смены в формате YYYY-MM-DD. Если даты нет вообще — верни null.
work_hours: Количество рабочих часов (число). Если в тексте не указаны часы, ОБЯЗАТЕЛЬНО верни null (не придумывай 0).
driving_hours: Количество часов за рулем (число). Если в тексте не указано вождение, ОБЯЗАТЕЛЬНО верни null.
location: Название объекта, компании или города (строка). Если не указано, верни null. Если произнесено на русском/украинском, переведи на язык оригинала страны (например, 'Варшава' -> 'Warszawa').
status: Строго одно из значений: 'Work', 'L4', 'Urlop'. По умолчанию 'Work', если нет других указаний.
is_abroad: true, если юзер упоминает работу за границей, иначе false.

Никакого лишнего текста, только валидный JSON. Убедись, что ключи в JSON именно такие: date, work_hours, driving_hours, location, status, is_abroad.

Текст пользователя для анализа:
{raw_text}"""
    
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    
    response_text = await call_vertex_ai(contents, response_mime_type="application/json")
    return json.loads(response_text)
