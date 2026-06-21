import json
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# Import config to ensure environment variables (like GEMINI_API_KEY) are loaded
import config

class ShiftInfo(BaseModel):
    date: Optional[str] = Field(
        None, 
        description="The date of the shift in YYYY-MM-DD format, or null if not found"
    )
    work_hours: Optional[float] = Field(
        None, 
        description="The total number of work hours, or null if not found"
    )
    driving_hours: Optional[float] = Field(
        None, 
        description="The total number of driving hours, or null if not found"
    )
    location: Optional[str] = Field(
        None, 
        description="The location of the shift (e.g. city, country), or null if not found"
    )
    status: Optional[Literal["Work", "L4", "Urlop"]] = Field(
        None, 
        description="The status of the shift: 'Work' (working day), 'L4' (sick leave), 'Urlop' (vacation/holiday), or null"
    )
    is_abroad: Optional[bool] = Field(
        False,
        description="True if the user mentions working abroad, False otherwise"
    )

async def parse_shift_text(raw_text: str) -> dict:
    """
    Parses unstructured text about a work shift and returns a structured dictionary
    matching the ShiftInfo schema using Gemini 3.5 Flash.
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    client = genai.Client()
    
    prompt = f"""Ты — высокоточный парсер данных для бухгалтерского учета. Твоя задача — извлекать факты из неструктурированного текста пользователя и возвращать их СТРОГО в формате JSON.

ТЕКУЩАЯ ДАТА: {current_date}. Используй ее для вычисления относительных дат (сегодня, вчера, позавчера).

Правила извлечения:

date: Дата смены в формате YYYY-MM-DD. Вычисли ее на основе текущей даты, если юзер говорит 'вчера' или 'сегодня'. Если даты нет вообще — верни null.

work_hours: Количество рабочих часов (число).

driving_hours: Количество часов за рулем (число). Если не указано — 0.

location: Название объекта, компании или города (строка). КРИТИЧЕСКИ ВАЖНО: НИКОГДА не переводи и не транслитерируй названия компаний или городов. Оставляй их в оригинальном виде (например, 'SWISS KRONO', а не 'свис кроно' или 'Шары' вместо 'Żary').

status: Строго одно из значений: 'Work', 'L4', 'Urlop'. Если не указано, по умолчанию 'Work'.

is_abroad: true, если юзер упоминает работу за границей, иначе false.

Никакого лишнего текста, только валидный JSON.

Текст пользователя для анализа:
{raw_text}"""
    
    response = await client.aio.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ShiftInfo,
            temperature=0.1,
        )
    )
    
    if response.parsed:
        return response.parsed.model_dump()
    
    return json.loads(response.text)
