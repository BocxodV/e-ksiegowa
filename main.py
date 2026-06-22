import asyncio
import logging
import os
import traceback
import hashlib
import hmac
import urllib.parse
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    FSInputFile, MenuButtonWebApp, WebAppInfo, 
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === WEBHOOK IMPORTS ===
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# === LOGGING CONFIGURATION ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

from texts import TRANSLATIONS
from keyboards import get_main_keyboard

# Import asynchronous database functions
from database import (
    init_db, get_user_profile, update_user_language, 
    update_last_location, get_users_for_audit, get_all_users, update_user_setting
)

from handlers import admin, webapp, reports, vision, voice, feedback
from handlers.webapp import build_app_url
from handlers.vision import process_image_bytes # Import image parsing capability

from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === WEBHOOK CONFIGURATION ===
WEBHOOK_PATH = "/webhook"
webhook_base = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_URL = f"{webhook_base}{WEBHOOK_PATH}" if webhook_base else ""

def verify_telegram_web_app_data(init_data: str, bot_token: str) -> bool:
    try:
        parsed_data = urllib.parse.parse_qsl(init_data)
        data_dict = {k: v for k, v in parsed_data}
        if "hash" not in data_dict:
            return False
        received_hash = data_dict.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return calculated_hash == received_hash
    except Exception:
        return False


# === 1. BASE HANDLERS ===

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    
    # Detect language from user profile or client settings
    tg_lang = message.from_user.language_code 
    if tg_lang:
        if tg_lang.startswith('pl'): user_lang = "PL"
        elif tg_lang.startswith('uk'): user_lang = "UKR"
        elif tg_lang.startswith('en'): user_lang = "ENG"
        else: user_lang = "RUS" 
    else:
        user_lang = profile.get("lang", "RUS")
        
    await update_user_language(user_id, user_lang)
    profile["lang"] = user_lang 
    
    t = TRANSLATIONS.get(user_lang, TRANSLATIONS["RUS"])
    dyn_url = await build_app_url(user_id, profile)
    
    await message.bot.set_chat_menu_button(
        chat_id=user_id,
        menu_button=MenuButtonWebApp(text=t["menu_btn"], web_app=WebAppInfo(url=dyn_url))
    )
    
    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t["menu_btn"], web_app=WebAppInfo(url=dyn_url))]],
        resize_keyboard=True 
    )
    
    # Create Inline buttons for language selection
    lang_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇵🇱 PL", callback_data="lang_PL"),
                InlineKeyboardButton(text="🇷🇺 RU", callback_data="lang_RUS"),
                InlineKeyboardButton(text="🇺🇦 UK", callback_data="lang_UKR"),
                InlineKeyboardButton(text="🇬🇧 EN", callback_data="lang_ENG")
            ]
        ]
    )
    
    photo_file = FSInputFile("web/arts/kasia_welcome.png")
    await message.answer_photo(
        photo=photo_file,
        caption="Wybierz język / Выберите язык / Choose language:",
        parse_mode="Markdown",
        reply_markup=lang_kb
    )
    
    await message.answer(
        text=t["welcome_text"],
        parse_mode="Markdown",
        reply_markup=markup
    )

@dp.callback_query(F.data.startswith("lang_"))
async def process_lang_selection(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[1]
    
    await update_user_language(user_id, lang_code)
    t = TRANSLATIONS.get(lang_code, TRANSLATIONS["RUS"])
    
    profile = await get_user_profile(user_id)
    profile["lang"] = lang_code
    dyn_url = await build_app_url(user_id, profile)
    
    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t["menu_btn"], web_app=WebAppInfo(url=dyn_url))]],
        resize_keyboard=True 
    )
    
    await callback.bot.set_chat_menu_button(
        chat_id=user_id,
        menu_button=MenuButtonWebApp(text=t["menu_btn"], web_app=WebAppInfo(url=dyn_url))
    )
    
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        text=t["set_ok"],
        parse_mode="Markdown",
        reply_markup=markup
    )
    await callback.answer()

@dp.my_chat_member()
async def silent_chat_member_update(update: types.ChatMemberUpdated):
    pass


# === 2. INCLUDE ROUTERS FROM MODULES ===
dp.include_router(admin.router)
dp.include_router(reports.router)
dp.include_router(vision.router)
dp.include_router(voice.router)
dp.include_router(feedback.router)
dp.include_router(webapp.router) 


# === 3. APPLICATION LIFECYCLE & API GATEWAY ===

async def on_startup(bot: Bot):
    logger.info("⏳ [STEP 1] Starting on_startup. Connecting to database...")
    try:
        await init_db() 
        logger.info("✅ [STEP 2] Database successfully initialized!")
    except Exception as e:
        logger.error(f"❌ Error connecting to database: {e}")
    
    logger.info("⏳ [STEP 3] Starting task scheduler...")
    scheduler = AsyncIOScheduler(timezone="Europe/Warsaw")
    scheduler.start()
    logger.info("✅ [STEP 4] Scheduler started!")
    
    if WEBHOOK_URL:
        logger.info(f"⏳ [STEP 5] Setting webhook URL: {WEBHOOK_URL}")
        try:
            await bot.set_webhook(WEBHOOK_URL)
            logger.info("✅ [STEP 6] Webhook successfully set!")
        except Exception as e:
            logger.error(f"❌ Error setting webhook: {e}")
    else:
        logger.warning("⚠️ WEBHOOK_URL is not configured!")

async def on_shutdown(bot: Bot):
    logger.info("💤 Web server shutting down. Webhook active, awaiting requests...")

# === FRONTEND API GATEWAY BRIDGE ===
async def api_scan_car(request):
    # Allow Vercel frontend origin
    headers = {
        'Access-Control-Allow-Origin': 'https://e-ksiegowa.vercel.app',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }
    if request.method == 'OPTIONS':
        return web.Response(headers=headers)

    try:
        data = await request.post()
        photo = data.get('photo')
        user_id = data.get('user_id')
        init_data = data.get('initData')

        if not init_data or not verify_telegram_web_app_data(init_data, BOT_TOKEN):
            return web.json_response({"error": "Unauthorized"}, status=403, headers=headers)

        if not photo:
            return web.json_response({"error": "No photo"}, status=400, headers=headers)
        
        # Parse image bytes
        result = await process_image_bytes(photo.file.read())
        
        # Save parsed default vehicle to user profile
        car_str, plate_str = result.get("car", "").strip(), result.get("plate", "").strip()
        if user_id and str(user_id) != "unknown" and (car_str or plate_str):
            final_car_string = f"{car_str} {plate_str}".strip()
            await update_user_setting(int(user_id), "default_car", final_car_string)

        return web.json_response(result, headers=headers)
        
    except Exception as e:
        logger.error(f"API Scan Error: {e}\n{traceback.format_exc()}")
        return web.json_response({"error": str(e)}, status=500, headers=headers)


def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()

    # Register route for garage scanner
    app.router.add_route('OPTIONS', '/api/scan-car', api_scan_car)
    app.router.add_post('/api/scan-car', api_scan_car)

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 Launching web server on port {port}...")
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()