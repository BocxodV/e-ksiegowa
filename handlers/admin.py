import os
import json
import asyncio
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from database import get_system_stats, get_all_users, get_user_profile

router = Router()

# Retrieve the admin's Telegram ID from environment variables
# Fallback to 0 if not configured (denies access by default)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

@router.message(Command("admin", "boss", "stat"))
async def commander_panel(message: types.Message):
    # Restrict access to the verified admin user ID
    if message.from_user.id != ADMIN_ID:
        return 
        
    # Fetch system statistics from the database
    stats = await get_system_stats()
    
    text = (
        "👑 <b>ПАНЕЛЬ КОМАНДИРА</b> 👑\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Пользователей в БД: <b>{stats.get('users_count', 0)}</b>\n"
        f"📝 Сохранено смен: <b>{stats.get('shifts_count', 0)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📢 <b>Рассылка:</b>\n"
        "• <code>/broadcast &lt;текст&gt;</code> — отправить всем\n"
        "• По тегам (мультиязычная):\n"
        "<code>/broadcast</code>\n"
        "<code>[RUS] Текст...</code>\n"
        "<code>[PL] Tekst...</code>\n"
        "<code>[UKR] Текст...</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Все системы в облаке функционируют в штатном режиме.</i> 🚀"
    )
    
    await message.answer(text, parse_mode="HTML")

@router.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer(
            "⚠️ **Использование:**\n"
            "1️⃣ Простая рассылка: `/broadcast Всем привет!`\n"
            "2️⃣ Мультиязычная по тегам:\n"
            "`/broadcast`\n"
            "`[RUS] Привет!`\n"
            "`[PL] Cześć!`\n"
            "`[UKR] Привіт!`\n"
            "3️⃣ JSON-формат: `{\"RUS\": \"Привет\", \"PL\": \"Cześć\"}`",
            parse_mode="Markdown"
        )
        return
        
    is_json = False
    json_data = {}
    try:
        json_data = json.loads(text)
        if isinstance(json_data, dict):
            is_json = True
    except:
        pass

    # Parse tag-based multilingual messages: [RUS], [PL], [UKR]
    parsed_data = {}
    if not is_json:
        current_lang = None
        lines = text.split("\n")
        for line in lines:
            line_strip = line.strip()
            if line_strip.startswith("[") and line_strip.endswith("]"):
                tag = line_strip[1:-1].upper()
                if tag in ["RUS", "PL", "UKR", "ENG"]:
                    current_lang = tag
                    parsed_data[current_lang] = []
                    continue
            if current_lang is not None:
                parsed_data[current_lang].append(line)
        
        # Combine lines for each parsed language
        for k in parsed_data:
            parsed_data[k] = "\n".join(parsed_data[k]).strip()

    users = await get_all_users()
    count = 0
    blocked_count = 0
    await message.answer("⏳ Начинаю рассылку...")
    
    for u in users:
        user_id = u[0]
        try:
            profile = await get_user_profile(user_id)
            lang = profile.get("lang", "RUS")
            
            if is_json:
                msg_text = json_data.get(lang, json_data.get("RUS", text))
            elif parsed_data:
                msg_text = parsed_data.get(lang, parsed_data.get("RUS", text))
            else:
                msg_text = text
                
            if msg_text:
                await message.bot.send_message(user_id, msg_text)
                count += 1
                await asyncio.sleep(0.05) # Prevent triggering Telegram rate limits (max 30 messages per second)
        except (TelegramForbiddenError, TelegramAPIError) as e:
            blocked_count += 1
        except Exception:
            pass
            
    await message.answer(f"✅ Рассылка завершена!\nДоставлено: <b>{count}</b>\nЗаблокировали бота: <b>{blocked_count}</b>", parse_mode="HTML")