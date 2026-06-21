import json
import logging
from datetime import datetime
from google import genai
from google.genai import types as genai_types
from aiogram import Router, F, types

from config import GEMINI_API_KEY
from app.graph import app_graph
from app.state import AgentState

router = Router()
logger = logging.getLogger(__name__)

# Initialize GenAI client using our API key
client = genai.Client(api_key=GEMINI_API_KEY)

@router.message(F.voice)
async def handle_voice_shift(message: types.Message):
    status_msg = await message.answer("🎧 Слушаю и анализирую...")
    
    try:
        # 1. Download voice message directly into memory
        file_info = await message.bot.get_file(message.voice.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
        audio_bytes = downloaded_file.read()
        audio_part = genai_types.Part.from_bytes(data=audio_bytes, mime_type='audio/ogg')
        
        # 2. Transcribe voice message using Gemini
        today_str = datetime.now().strftime("%Y-%m-%d")
        prompt_text = f"""
        Ты — финансовый AI-ассистент. Твоя единственная задача — прослушать это голосовое сообщение от работника и перевести его в текст (сделать точную транскрипцию). 
        Верни только текст транскрипции без каких-либо комментариев и введений. 
        Сегодняшняя дата: {today_str}.
        """
        
        await status_msg.edit_text("🧠 Расшифровываю аудио...")
        response = await client.aio.models.generate_content(
            model='gemini-3.5-flash',
            contents=[prompt_text, audio_part],
            config=genai_types.GenerateContentConfig(temperature=0.1)
        )
        transcribed_text = response.text.strip()
        logger.info(f"Transcribed voice: '{transcribed_text}'")
        
        # 3. Setup initial state for LangGraph Agent
        initial_state = AgentState(
            user_id=message.from_user.id,
            raw_input=transcribed_text,
            parsed_data=None,
            validation_errors=[],
            is_confirmed=False
        )
        
        # 4. Setup thread config for MemorySaver persistence (unique thread per message)
        config = {"configurable": {"thread_id": f"{message.from_user.id}_{message.message_id}"}}
        
        # 5. Run the graph until the human_review interrupt point
        await status_msg.edit_text("🤖 Анализирую смену с помощью ИИ...")
        user_id = message.from_user.id
        raw_text = transcribed_text
        logger.info(f"🚀 Запуск графа для пользователя {user_id}. Входной текст: '{raw_text}'")
        async for event in app_graph.astream(initial_state, config=config):
            logger.debug(f"⚙️ Шаг графа: {event}")
            
        # 6. Retrieve state after interrupt
        state_snapshot = await app_graph.aget_state(config)
        current_state = state_snapshot.values
        logger.info(f"⏸️ Граф приостановлен/завершен. Текущее состояние: {current_state}")
        
        # 7. Check for validation errors
        errors = current_state.get("validation_errors", [])
        if errors:
            error_list = "\n".join(f"• {err}" for err in errors)
            await status_msg.delete()
            await message.answer(f"⚠️ **Ошибка валидации данных:**\n\n{error_list}", parse_mode="Markdown")
            return
            
        # 8. Save shift draft to PostgreSQL and send for user confirmation
        parsed_data = current_state.get("parsed_data") or {}
        from database import save_user_draft
        await save_user_draft(message.from_user.id, message.message_id, parsed_data, transcribed_text)
        
        draft_msg = (
            f"📝 **Черновик смены:**\n\n"
            f"📅 Дата: `{parsed_data.get('date') or 'Не указана'}`\n"
            f"📍 Локация: `{parsed_data.get('location') or 'Не указана'}`\n"
            f"🕒 Работа: `{parsed_data.get('work_hours') or 0.0} ч.`\n"
            f"🚗 Вождение: `{parsed_data.get('driving_hours') or 0.0} ч.`\n"
            f"📋 Статус: `{parsed_data.get('status') or 'Не указан'}`\n\n"
            f"**Сохранить эту смену в базу данных?**"
        )
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="Да ✅", callback_data=f"confirm_shift_yes:{message.message_id}"),
                types.InlineKeyboardButton(text="Нет ❌", callback_data=f"confirm_shift_no:{message.message_id}")
            ]
        ])
        
        await status_msg.delete()
        await message.answer(draft_msg, reply_markup=kb, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Voice Error: {e}", exc_info=True)
        await status_msg.edit_text(f"⚠️ Ошибка расшифровки: {str(e)}")

@router.callback_query(F.data.startswith("confirm_shift_yes"))
async def handle_confirm_yes(callback: types.CallbackQuery):
    await callback.answer()
    status_msg = await callback.message.edit_text("💾 Сохраняю смену в базу данных...")
    
    try:
        user_id = callback.from_user.id
        parts = callback.data.split(":")
        msg_id = parts[1] if len(parts) > 1 else ""
        
        if msg_id:
            config = {"configurable": {"thread_id": f"{user_id}_{msg_id}"}}
        else:
            # Fallback for backward compatibility
            config = {"configurable": {"thread_id": str(user_id)}}
        
        # 1. Attempt to update state in-memory
        try:
            await app_graph.aupdate_state(config, {"is_confirmed": True})
            state_snapshot = await app_graph.aget_state(config)
            raw_text = state_snapshot.values.get("raw_input", "")
        except Exception:
            state_snapshot = None
            raw_text = ""
            
        # 2. Check if checkpointer state was lost (scale-down/restart recovery)
        if not state_snapshot or not state_snapshot.values.get("parsed_data"):
            logger.warning(f"State checkpointer lost for thread {user_id}_{msg_id}. Activating DB fallback...")
            from database import get_user_draft
            parsed_data, raw_text = await get_user_draft(user_id, msg_id)
            if not parsed_data:
                logger.error("No draft found in DB fallback.")
                await status_msg.edit_text("⚠️ Ошибка: черновик смены устарел или не найден. Пожалуйста, отправьте голосовое сообщение заново.")
                return
            
            # Reconstruct state dictionary and save directly
            fallback_state = {
                "user_id": user_id,
                "raw_input": raw_text,
                "parsed_data": parsed_data,
                "validation_errors": [],
                "is_confirmed": True
            }
            from app.tools.db_tool import save_shift_to_db
            await save_shift_to_db(fallback_state)
            current_state = fallback_state
        else:
            # Checkpointer is alive, proceed normal graph execution
            logger.info(f"🚀 Запуск графа для пользователя {user_id}. Входной текст: '{raw_text}'")
            # Resume graph to run human_review and database saver node
            async for event in app_graph.astream(None, config=config):
                logger.debug(f"⚙️ Шаг графа: {event}")
                
            # Retrieve final state values
            state_snapshot = await app_graph.aget_state(config)
            current_state = state_snapshot.values
        logger.info(f"⏸️ Граф приостановлен/завершен. Текущее состояние: {current_state}")
        parsed_data = current_state.get("parsed_data") or {}
        
        date_str = parsed_data.get("date")
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d.%m.%Y")
        
        # Fetch profile and localization
        from database import get_user_profile, get_pool, increment_shift_count
        from texts import TRANSLATIONS, get_random_motivation
        from handlers.webapp import build_app_url
        from map_service import get_country_by_city
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, MenuButtonWebApp
        
        profile = await get_user_profile(user_id)
        user_lang = profile.get("lang", "RUS")
        t = TRANSLATIONS.get(user_lang, TRANSLATIONS["RUS"])
        
        # Retrieve the saved log from DB
        pool = await get_pool()
        async with pool.acquire() as db:
            row = await db.fetchrow('''
                SELECT day_of_week, status, location, work_hours, driving_hours, bonuses, gross, net, is_abroad, is_trip
                FROM work_logs
                WHERE user_id = $1 AND log_date = $2
            ''', user_id, formatted_date)
            
        if not row:
            # Fallback if record was not found
            await status_msg.edit_text("✅ **Смена успешно сохранена в базу данных!**", parse_mode="Markdown")
            return
            
        day_name = row['day_of_week']
        status = row['status']
        location = row['location']
        work_hours = float(row['work_hours'] or 0)
        driving_hours = float(row['driving_hours'] or 0)
        bonuses = float(row['bonuses'] or 0)
        gross = float(row['gross'] or 0)
        net = float(row['net'] or 0)
        
        # Country flag
        country_flag = "🇵🇱"
        if location:
            country_code = await get_country_by_city(location)
            if len(country_code) == 2:
                country_flag = chr(ord(country_code[0]) + 127397) + chr(ord(country_code[1]) + 127397)
            else:
                country_flag = "🌍"
                
        # Status icon
        status_labels = {
            "Work": {"PL": "💼 Praca", "UKR": "💼 Робота", "RUS": "💼 Работа"},
            "L4": {"PL": "💊 Zwolnienie (L4)", "UKR": "💊 Лікарняний (L4)", "RUS": "💊 Больничный (L4)"},
            "Urlop": {"PL": "🌴 Urlop", "UKR": "🌴 Відпустка", "RUS": "🌴 Отпуск"}
        }
        status_icon = status_labels.get(status, status_labels["Work"]).get(user_lang, status_labels["Work"]["RUS"])
        
        # Overwork advice
        ai_advice = ""
        if status == "Work" and (work_hours + driving_hours) >= 12:
            ai_advice = f"\n\n🤖 {t['overwork_msg'].format(hours=(work_hours + driving_hours))}"
            
        # WebApp integration and shift count
        dyn_url = await build_app_url(user_id, profile)
        total_shifts = await increment_shift_count(user_id)
        coffee_msg = f"\n\n☕️ <i>Всего смен: {total_shifts} | <a href='https://www.buymeacoffee.com/bocxodv'>Угостить Касю кофе</a></i>"
        
        # Motivation text
        motivation_text = get_random_motivation(user_lang)
        
        tax_coeff_val = profile.get("tax_coeff", 0.71)
        card_money = gross * tax_coeff_val
        
        final_text = (
            "🧾 <b>СМЕНА ЗАКРЫТА</b> 🧾\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 <b>Дата:</b> {date_obj.strftime('%d.%m.%Y')} ({day_name})\n"
            f"🛠 <b>Статус:</b> {status_icon}\n"
            f"📍 <b>Объект:</b> {location} {country_flag}\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"⏱ На объекте: <code>{work_hours:.1f} ч.</code>\n"
            f"🚗 За рулем:   <code>{driving_hours:.1f} ч.</code>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "💰 <b>ИТОГИ ДНЯ:</b>\n"
            f"💵 На руки:   <code>{net:.2f} zł</code>\n"
            f"📄 Брутто:    <code>{gross:.2f} zł</code>\n"
            f"💳 На карту:  <code>{card_money:.2f} zł</code>\n"
            f"⚖️ Nierozliczone saldo: <code>{bonuses:.2f} zł</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>{motivation_text}</i>\n"
            f"{ai_advice}"
            f"{coffee_msg}"
        )
        
        # Set chat menu button
        await callback.message.bot.set_chat_menu_button(
            chat_id=user_id,
            menu_button=MenuButtonWebApp(text=t["menu_btn"], web_app=WebAppInfo(url=dyn_url))
        )
        
        markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=t["menu_btn"], web_app=WebAppInfo(url=dyn_url))]],
            resize_keyboard=True
        )
        
        try:
            await status_msg.delete()
        except Exception:
            pass
            
        await callback.message.answer(final_text, reply_markup=markup, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error saving shift via callback: {e}", exc_info=True)
        try:
            await status_msg.edit_text("⚠️ Ошибка при сохранении смены в базу данных.")
        except Exception:
            pass

@router.callback_query(F.data.startswith("confirm_shift_no"))
async def handle_confirm_no(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("❌ **Ввод смены отменен.**", parse_mode="Markdown")