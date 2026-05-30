import asyncio
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, MenuButtonWebApp, WebAppInfo, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === НОВЫЕ ИМПОРТЫ ДЛЯ WEBHOOK ===
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

from texts import TRANSLATIONS
from keyboards import get_main_keyboard

# Импорт асинхронных функций БД
from database import (
    init_db, get_user_profile, update_user_language, 
    update_last_location, get_users_for_audit, get_all_users
)

from handlers import reports, webapp, vision, voice
from handlers.reports import generate_excel_report
from handlers.webapp import build_app_url # Подтягиваем наш генератор
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Регистрация всех модулей
dp.include_router(reports.router)
dp.include_router(vision.router) 
dp.include_router(voice.router) 
dp.include_router(webapp.router) 

# === НАСТРОЙКИ WEBHOOK ===
WEBHOOK_PATH = "/webhook"
# Сюда попадет ссылка от Google Cloud Run (настроим на сервере)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "") 

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    
    # Авто-перехват 
    tg_lang = message.from_user.language_code 
    if tg_lang:
        if tg_lang.startswith('pl'): user_lang = "PL"
        elif tg_lang.startswith('uk'): user_lang = "UK"
        elif tg_lang.startswith('en'): user_lang = "EN"
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
    
    # Создаем Inline-кнопки для выбора языка
    lang_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇵🇱 PL", callback_data="lang_PL"),
                InlineKeyboardButton(text="🇷🇺 RU", callback_data="lang_RUS"),
                InlineKeyboardButton(text="🇺🇦 UK", callback_data="lang_UK")
            ]
        ]
    )
    
    # Меняем имя файла на kasia_welcome.png с точным локальным путем
    photo_file = FSInputFile("web/arts/kasia_welcome.png")
    await message.answer_photo(
        photo=photo_file,
        caption="Wybierz język / Выберите язык / Choose language:",
        parse_mode="Markdown",
        reply_markup=lang_kb
        
    )
    
    # Отправляем приветствие с Reply-кнопкой WebApp следующим сообщением
    await message.answer(
        text=t["welcome_text"],
        parse_mode="Markdown",
        reply_markup=markup
    )

# === ЖИЗНЕННЫЙ ЦИКЛ БОТА ===
async def on_startup(bot: Bot):
    """Функция выполняется при запуске веб-сервера."""
    logger.info("⏳ [ШАГ 1] Запуск on_startup. Подключаемся к базе Neon...")
    
    try:
        await init_db() 
        logger.info("✅ [ШАГ 2] База данных успешно подключена и инициализирована!")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
    
    logger.info("⏳ [ШАГ 3] Запуск планировщика задач...")
    scheduler = AsyncIOScheduler(timezone="Europe/Warsaw")
    scheduler.start()
    logger.info("✅ [ШАГ 4] Планировщик запущен!")
    
    if WEBHOOK_URL:
        logger.info(f"⏳ [ШАГ 5] Отправляем запрос в Telegram: {WEBHOOK_URL}{WEBHOOK_PATH}")
        try:
            await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
            logger.info("✅ [ШАГ 6] Webhook успешно привязан!")
        except Exception as e:
            logger.error(f"❌ Ошибка установки Webhook: {e}")
    else:
        logger.warning("⚠️ WEBHOOK_URL не задан! Бот запущен, но не будет получать сообщения.")

async def on_shutdown(bot: Bot):
    """Функция выполняется при выключении веб-сервера."""
    logger.info("Выключаем бота...")
    await bot.delete_webhook()

def main():
    # 1. Регистрируем события старта и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # 2. Создаем веб-сервер aiohttp
    app = web.Application()

    # 3. Настраиваем обработчик запросов от Telegram
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    # Слушаем запросы по пути /webhook
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # 4. Привязываем наше приложение к диспетчеру
    setup_application(app, dp, bot=bot)

    # 5. Получаем порт от Google Cloud (по умолчанию 8080)
    port = int(os.getenv("PORT", 8080))

    # 6. Запускаем сервер
    logger.info(f"🚀 Запускаем веб-сервер на порту {port}...")
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()