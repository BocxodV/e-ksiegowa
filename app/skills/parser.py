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

date: Дата смены в формате YYYY-MM-DD. Вычисли ее на основе текущей даты, если юзер говорит 'вчера' или 'сегодня'. Если даты нет вообще — верни null.

work_hours: Количество рабочих часов (число).

driving_hours: Количество часов за рулем (число). Если не указано — 0.

location: Название объекта, компании или города (строка). КРИТИЧЕСКИ ВАЖНО: Возвращай названия компаний, городов и объектов строго на языке оригинала той страны, где они физически находятся. Если пользователь произносит или пишет их на русском или украинском (например, 'Варшава', 'Жары', 'Берлин', 'Мюнхен'), ты обязан перевести их на язык оригинала страны нахождения (например, 'Warszawa' для Польши, 'Żary' для Польши, 'Berlin' для Германии, 'München' для Германии). Названия компаний также должны быть в оригинальном виде (например, 'SWISS KRONO', а не 'Свис Кроно').

status: Строго одно из значений: 'Work', 'L4', 'Urlop'. Всегда возвращай 'Work', если пользователь явно не просит больничный ('L4') или отпуск ('Urlop'). Если не указано, по умолчанию 'Work'.

is_abroad: true, если юзер упоминает работу за границей, иначе false.

Никакого лишнего текста, только валидный JSON.

Текст пользователя для анализа:
{raw_text}"""
    
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    
    response_text = await call_vertex_ai(contents, response_mime_type="application/json")
    return json.loads(response_text)
