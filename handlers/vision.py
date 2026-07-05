import json
import logging
from google.genai import types as genai_types
from aiogram import Router, F, types

from config import gemini_client
from database import update_user_setting, get_user_profile
from texts import TRANSLATIONS

router = Router()
logger = logging.getLogger(__name__)

# Core image processing helper function (available for WebApp integration)
async def process_image_bytes(image_bytes: bytes) -> dict:
    prompt = """
    Ты - умный парсер автомобильных данных. Посмотри на это фото.
    Определи марку и модель автомобиля. Если видно номерной знак, прочитай его.
    Верни ТОЛЬКО валидный JSON.
    Формат: {"car": "Марка и Модель", "plate": "НОМЕР"}
    Если чего-то нет на фото, оставь значение пустым.
    """
    response = await gemini_client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            prompt,
            genai_types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg')
        ],
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    return json.loads(response.text)

# Telegram message handler for photo messages
@router.message(F.photo)
async def handle_car_photo(message: types.Message):
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    user_lang = profile.get("lang", "RUS")
    t = TRANSLATIONS.get(user_lang, TRANSLATIONS["RUS"])

    status_msg = await message.answer(t["vision_analyzing"])
    try:
        photo = message.photo[-1]
        file_info = await message.bot.get_file(photo.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
        
        data = await process_image_bytes(downloaded_file.read())
        
        car, plate = data.get("car", "").strip(), data.get("plate", "").strip()
        
        if not car and not plate:
            await status_msg.edit_text(t["vision_not_recognized"])
            return
            
        final_car_string = f"{car} {plate}".strip()
        await update_user_setting(user_id, "default_car", final_car_string)

        await status_msg.delete()
        await message.answer(
            t["vision_recognized"].format(car=car, plate=plate), 
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Vision Error: {e}")
        await status_msg.edit_text(t["vision_error"].format(err=str(e)))