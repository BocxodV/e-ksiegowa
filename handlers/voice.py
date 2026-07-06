import json
import logging
from datetime import datetime
import base64
from aiogram import Router, F, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, MenuButtonWebApp

from config import call_vertex_ai
from app.graph import app_graph
from app.state import AgentState
from database import get_user_profile, get_pool, increment_shift_count, save_user_draft, get_user_draft
from texts import TRANSLATIONS, get_random_motivation
from handlers.webapp import build_app_url
from map_service import get_country_by_city
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

class ShiftValidationState(StatesGroup):
    waiting_for_clarification = State()

router = Router()
logger = logging.getLogger(__name__)



async def process_voice_message(message: types.Message, status_msg: types.Message, t: dict) -> str:
    # 1. Download voice message directly into memory
    file_info = await message.bot.get_file(message.voice.file_id)
    downloaded_file = await message.bot.download_file(file_info.file_path)
    audio_bytes = downloaded_file.read()
    b64_audio = base64.b64encode(audio_bytes).decode('utf-8')
    
    # 2. Transcribe voice message using Vertex AI
    today_str = datetime.now().strftime("%Y-%m-%d")
    prompt_text = f"""
    Ты — финансовый AI-ассистент. Твоя единственная задача — прослушать это голосовое сообщение от работника и перевести его в текст (сделать точную транскрипцию). 
    Верни только текст транскрипции без каких-либо комментариев и введений. 
    Сегодняшняя дата: {today_str}.
    """
    
    contents = [{
        "role": "user",
        "parts": [
            {"text": prompt_text},
            {"inlineData": {"mimeType": "audio/ogg", "data": b64_audio}}
        ]
    }]
    
    await status_msg.edit_text(t.get("voice_status_transcribing", "🧠 Расшифровываю аудио..."))
    transcribed_text = await call_vertex_ai(contents)
    return transcribed_text.strip()

@router.message(F.voice)
async def handle_voice_shift(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    t = TRANSLATIONS.get(profile.get("lang", "RUS"), TRANSLATIONS["RUS"])

    status_msg = await message.answer(t.get("voice_status_listening", "🎧 Слушаю и анализирую..."))
    
    try:
        transcribed_text = await process_voice_message(message, status_msg, t)
        logger.info(f"Transcribed voice: '{transcribed_text}'")
        await run_shift_graph(message, transcribed_text, status_msg, t, state)
        
    except Exception as e:
        logger.error(f"Voice Error: {e}", exc_info=True)
        await status_msg.edit_text(f"⚠️ Ошибка расшифровки: {str(e)}")

@router.message(ShiftValidationState.waiting_for_clarification, F.text | F.voice)
async def handle_clarification_reply(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    t = TRANSLATIONS.get(profile.get("lang", "RUS"), TRANSLATIONS["RUS"])
    
    status_msg = await message.answer(t.get("voice_status_listening", "🎧 Анализирую дополнение..."))
    
    try:
        if message.voice:
            new_text = await process_voice_message(message, status_msg, t)
        else:
            await status_msg.delete()
            new_text = message.text
            status_msg = await message.answer("🤖 Обрабатываю...")
            
        data = await state.get_data()
        stored_parsed = data.get("parsed_data", {})
        last_question = data.get("last_question", "")
        
        # Context-aware update: LLM sees the current draft AND the question that was asked
        await status_msg.edit_text("🤖 Анализирую ответ...")
        import json as _json
        context_prompt = f"""You are updating a work shift record. Here is the current (partially filled) shift data:
{_json.dumps(stored_parsed, ensure_ascii=False)}

The user was asked: "{last_question}"
The user's answer: "{new_text}"

Update ONLY the fields that the user answered. Do NOT change fields that were already filled unless the user explicitly changed them.
Do NOT reset any field to null or 0 unless the user explicitly said so.
Return the complete updated JSON with all fields: date, work_hours, driving_hours, location, status, is_abroad."""
        
        contents = [{"role": "user", "parts": [{"text": context_prompt}]}]
        from config import call_vertex_ai
        response_text = await call_vertex_ai(contents, response_mime_type="application/json")
        merged = _json.loads(response_text)
        
        logger.info(f"🔀 Контекстный мерж: {stored_parsed} + '{new_text}' = {merged}")
        
        # Validate merged data
        from app.skills.guardrails import validate_shift_data
        errors = validate_shift_data(merged)
        
        if errors:
            # Still missing something — ask only the FIRST remaining question
            next_question = errors[0]
            question_msg = f"⚠️ **Уточните данные смены:**\n• {next_question}"
            await status_msg.delete()
            await message.answer(question_msg, parse_mode="Markdown")
            await state.update_data(parsed_data=merged, last_question=next_question)
            return
        
        # All good — show draft
        await state.clear()
        await show_draft(message, merged, status_msg, t)
        
    except Exception as e:
        logger.error(f"Clarification Error: {e}", exc_info=True)
        await status_msg.edit_text(f"⚠️ Ошибка: {str(e)}")

async def run_shift_graph(message: types.Message, raw_text: str, status_msg: types.Message, t: dict, state: FSMContext):
    user_id = message.from_user.id
    try:
        # 3. Setup initial state for LangGraph Agent
        initial_state = AgentState(
            user_id=user_id,
            raw_input=raw_text,
            parsed_data=None,
            validation_errors=[],
            clarification_question=None,
            is_confirmed=False
        )
        
        # 4. Setup thread config for MemorySaver persistence
        config = {"configurable": {"thread_id": f"{message.from_user.id}_{message.message_id}"}}
        
        # 5. Run the graph until the human_review interrupt point
        await status_msg.edit_text(t.get("voice_status_analyzing", "🤖 Анализирую смену с помощью ИИ..."))
        logger.info(f"🚀 Запуск графа для пользователя {user_id}. Входной текст: '{raw_text}'")
        async for event in app_graph.astream(initial_state, config=config):
            logger.debug(f"⚙️ Шаг графа: {event}")
            
        # 6. Retrieve state after interrupt
        state_snapshot = await app_graph.aget_state(config)
        current_state = state_snapshot.values
        logger.info(f"⏸️ Граф приостановлен/завершен. Текущее состояние: {current_state}")
        
        # 7. Check for validation errors / Clarification needed
        clarification = current_state.get("clarification_question")
        if clarification:
            parsed_data = current_state.get("parsed_data") or {}
            errors = current_state.get("validation_errors", [])
            first_question = errors[0] if errors else "Уточните данные смены"
            await status_msg.delete()
            await message.answer(f"⚠️ **Уточните данные смены:**\n• {first_question}", parse_mode="Markdown")
            await state.set_state(ShiftValidationState.waiting_for_clarification)
            await state.update_data(parsed_data=parsed_data, last_question=first_question)
            return
            
        # 8. All data is valid - show draft
        parsed_data = current_state.get("parsed_data") or {}
        await show_draft(message, parsed_data, status_msg, t)
        
    except Exception as e:
        logger.error(f"Graph execution Error: {e}", exc_info=True)
        await status_msg.edit_text(f"⚠️ Системная ошибка: {str(e)}")

async def show_draft(message: types.Message, parsed_data: dict, status_msg: types.Message, t: dict):
    """Saves draft to DB and shows confirmation card to user."""
    await save_user_draft(message.from_user.id, message.message_id, parsed_data, parsed_data.get("raw_input", ""))
    unk = t["draft_unknown"]
    draft_msg = (
        f"{t['draft_title']}\n\n"
        f"{t['draft_date']}: `{parsed_data.get('date') or unk}`\n"
        f"{t['draft_location']}: `{parsed_data.get('location') or unk}`\n"
        f"{t['draft_work']}: `{parsed_data.get('work_hours') or 0.0} h`\n"
        f"{t['draft_drive']}: `{parsed_data.get('driving_hours') or 0.0} h`\n"
        f"{t['draft_status_label']}: `{parsed_data.get('status') or unk}`\n\n"
        f"{t['draft_confirm']}"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text=t["btn_yes"], callback_data=f"confirm_shift_yes:{message.message_id}"),
        types.InlineKeyboardButton(text=t["btn_no"], callback_data=f"confirm_shift_no:{message.message_id}")
    ]])
    await status_msg.delete()
    await message.answer(draft_msg, reply_markup=kb, parse_mode="Markdown")

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
            await status_msg.edit_text(t["shift_saved_fallback"], parse_mode="Markdown")
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
            "Work": {"PL": "💼 Praca", "UKR": "💼 Робота", "RUS": "💼 Работа", "ENG": "💼 Work"},
            "L4": {"PL": "💊 Zwolnienie (L4)", "UKR": "💊 Лікарняний (L4)", "RUS": "💊 Больничный (L4)", "ENG": "💊 Sick Leave (L4)"},
            "Urlop": {"PL": "🌴 Urlop", "UKR": "🌴 Відпустка", "RUS": "🌴 Отпуск", "ENG": "🌴 Vacation"}
        }
        status_icon = status_labels.get(status, status_labels["Work"]).get(user_lang, status_labels["Work"]["RUS"])
        
        # Overwork advice
        ai_advice = ""
        if status == "Work" and (work_hours + driving_hours) >= 12:
            ai_advice = f"\n\n🤖 {t['overwork_msg'].format(hours=(work_hours + driving_hours))}"
            
        # WebApp integration and shift count
        dyn_url = await build_app_url(user_id, profile)
        total_shifts = await increment_shift_count(user_id)
        coffee_msg = f"\n\n☕️ <i>{t['shift_total_count'].format(total=total_shifts)} | <a href='https://www.buymeacoffee.com/bocxodv'>{t['coffee_invite']}</a></i>"
        
        # Motivation text
        motivation_text = get_random_motivation(user_lang)
        
        tax_coeff_val = profile.get("tax_coeff", 0.71)
        card_money = gross * tax_coeff_val
        
        final_text = (
            f"{t['shift_closed']}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{t['shift_date']} {date_obj.strftime('%d.%m.%Y')} ({day_name})\n"
            f"{t['shift_status_label']} {status_icon}\n"
            f"{t['shift_object']} {location} {country_flag}\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"{t['shift_onsite']} <code>{work_hours:.1f} h</code>\n"
            f"{t['shift_driving']}   <code>{driving_hours:.1f} h</code>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            f"{t['shift_daily_total']}\n"
            f"{t['shift_net']}   <code>{net:.2f} zł</code>\n"
            f"{t['shift_gross']}    <code>{gross:.2f} zł</code>\n"
            f"{t['shift_card']}  <code>{card_money:.2f} zł</code>\n"
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
            await status_msg.edit_text(t.get("shift_error_save", "⚠️ Error saving shift."))
        except Exception:
            pass

@router.callback_query(F.data.startswith("confirm_shift_no"))
async def handle_confirm_no(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    profile = await get_user_profile(user_id)
    t = TRANSLATIONS.get(profile.get("lang", "RUS"), TRANSLATIONS["RUS"])
    await callback.message.edit_text(t["shift_cancelled"], parse_mode="Markdown")