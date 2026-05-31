import json
import logging
import urllib.parse
import asyncio 
import os
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, 
    InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonWebApp,
    LinkPreviewOptions
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ИИ-магия для мотивации
import google.generativeai as genai

from texts import TRANSLATIONS
from keyboards import get_support_keyboard 
from nbp_service import get_eur_rate
from database import (
    get_user_profile, 
    upsert_work_log, update_user_setting,
    get_monthly_net_sum, increment_report_count, get_user_subscription_status,
    activate_user_premium, update_user_language,
    increment_shift_count, delete_work_log, get_work_logs_for_month,
    add_user_savings, get_analytics_by_location,
    get_user_unique_records 
)
from map_service import calculate_driving_hours, get_country_by_city

# ВОТ ЭТА СТРОКА УБЕРЕТ ЖЕЛТОЕ ПОДЧЕРКИВАНИЕ:
from handlers.reports import generate_excel_report

router = Router()
logger = logging.getLogger(__name__)

WEB_APP_URL = "https://e-ksiegowa.vercel.app/"

# === НАСТРОЙКА ИИ GEMINI 3.5 FLASH ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def get_dynamic_motivation(user_lang="RUS"):
    """Асинхронно генерирует уникальную цитату с защитой от таймаута для Cloud Run"""
    fallback_quotes = {
        "RUS": "✨ Отличная работа! Время заслуженного отдыха.",
        "PL": "✨ Świetna robota! Czas na zasłużony odpoczynek.",
        "UKR": "✨ Відмінна робота! Час для заслуженого відпочинку.",
        "EN": "✨ Great job! Time for a well-deserved rest."
    }
    fallback = fallback_quotes.get(user_lang, fallback_quotes["RUS"])

    if not GEMINI_API_KEY:
        return fallback

    try:
        model = genai.GenerativeModel('gemini-3.5-flash')
        
        prompt = (
            "Ты ИИ-ассистент. Сгенерируй одну короткую, универсальную и вдохновляющую "
            "фразу (максимум 1-2 предложения) для человека, завершившего рабочий день. "
            "Фраза должна подходить любому человеку. Без кавычек, без приветствий. "
            "Тон: теплый и поддерживающий. "
        )
        
        if user_lang == "PL": prompt += "Напиши на польском языке."
        elif user_lang == "UKR": prompt += "Напиши на украинском языке."
        else: prompt += "Напиши на русском языке."

        # МАГИЯ CLOUD RUN: Ждем ответ максимум 3 секунды!
        response = await asyncio.wait_for(
            model.generate_content_async(prompt),
            timeout=3.0
        )
        return f"✨ {response.text.strip()}"
        
    except asyncio.TimeoutError:
        logger.warning("Gemini API timeout! Используем резервную цитату.")
        return fallback
    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        return fallback

class SavingsState(StatesGroup):
    waiting_for_amount = State()

async def calculate_forecast(user_id, profile=None):
    if not profile: 
        profile = await get_user_profile(user_id)
    goal_target = profile.get("goal_target", 8000.0)
    current_savings = profile.get("current_savings", 0.0) 
    goal_deadline_str = profile.get("goal_deadline", "")
    
    remaining_money = max(0, goal_target - current_savings)
    
    if current_savings >= goal_target:
        return f"🎉 **ЦЕЛЬ ДОСТИГНУТА!** Ты накопил {current_savings:.2f} zł!"
        
    if not goal_deadline_str:
        return f"Укажи дату цели в настройках, чтобы я рассчитала прогноз! Осталось собрать: {remaining_money:.2f} zł."
        
    try:
        deadline_date = datetime.strptime(goal_deadline_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        days_left = (deadline_date - today).days
        
        if days_left <= 0:
            return f"⏳ Дедлайн прошел. Осталось собрать: {remaining_money:.2f} zł. Давай обновим дату в настройках!"
            
        weeks_left = max(1, days_left / 7)
        required_per_week = remaining_money / weeks_left
        
        return (f"📈 **Прогноз:**\n"
                f"Осталось собрать: **{remaining_money:.2f} zł**\n"
                f"До дедлайна: **{days_left} дней**\n\n"
                f"💡 Чтобы успеть вовремя, нужно откладывать примерно **{required_per_week:.0f} zł в неделю**.")
    except Exception:
        return f"Осталось собрать: {remaining_money:.2f} zł."

async def build_app_url(user_id, profile=None):
    if not profile:
        profile = await get_user_profile(user_id)
    user_lang = profile.get("lang", "RUS")
    current_month = datetime.now().strftime("%m.%Y")
    current_net = await get_monthly_net_sum(user_id, current_month)
    
    base, extra, eur = profile.get("base_rate", 0), profile.get("extra_rate", 0), profile.get("rate_eur", 0)
    drive, drive_eur = profile.get("rate_drive", 0), profile.get("rate_drive_eur", 0)
    default_car = ""
    
    raw_goal = profile.get("goal_name", "Моя цель")
    if len(raw_goal) > 12:
        raw_goal = raw_goal[:11] + "…"
    goal_name = urllib.parse.quote(raw_goal)
    
    goal_target = profile.get("goal_target", 8000.0)
    current_savings = profile.get("current_savings", 0.0)
    goal_deadline = profile.get("goal_deadline", "")
    
    history = await get_user_unique_records(user_id)
    cars_str = urllib.parse.quote(",".join(history.get("cars", [])))
    locs_str = urllib.parse.quote(",".join(history.get("locations", [])))
    
    return f"{WEB_APP_URL}?v=12&base={base:g}&extra={extra:g}&eur={eur:g}&drive={drive:g}&drive_eur={drive_eur:g}&car={default_car}&g_name={goal_name}&g_target={goal_target:g}&c_net={current_net:.1f}&c_sav={current_savings:g}&g_dead={goal_deadline}&lang={user_lang}&cars={cars_str}&locs={locs_str}"

@router.message(Command("app"))
async def summon_web_app(message: types.Message):
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    user_lang = profile.get("lang", "RUS")
    t = TRANSLATIONS.get(user_lang, TRANSLATIONS["RUS"])
    
    dynamic_url = await build_app_url(user_id, profile)
    
    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t["menu_btn"], web_app=WebAppInfo(url=dynamic_url))]],
        resize_keyboard=True
    )
    
    await message.bot.set_chat_menu_button(
        chat_id=user_id,
        menu_button=MenuButtonWebApp(text=t["menu_btn"], web_app=WebAppInfo(url=dynamic_url))
    )
    await message.answer(t["menu_msg"], reply_markup=markup)

@router.message(F.web_app_data)
async def web_app_handler(message: types.Message):
    try:
        await message.delete()
    except Exception:
        pass
        
    raw_data = message.web_app_data.data
    try:
        data = json.loads(raw_data)
        user_id = message.from_user.id
        profile = await get_user_profile(user_id)
        user_lang = profile.get("lang", "RUS")
        t = TRANSLATIONS.get(user_lang, TRANSLATIONS["RUS"])

        if data.get("action") == "add_shift":
            status_msg = await message.answer(t["saving"])
            
            start_date = datetime.strptime(data.get("date"), "%Y-%m-%d")
            end_date_str = data.get("end_date")
            status = data.get("status", "Work")
            location = data.get("object") or data.get("location") or ""
            car = data.get("car", "") 
            
            country_code = "PL"
            country_flag = "🇵🇱"
            
            if location:
                country_code = await get_country_by_city(location)
                if len(country_code) == 2:
                    country_flag = chr(ord(country_code[0]) + 127397) + chr(ord(country_code[1]) + 127397)
                else:
                    country_flag = "🌍"
            
            is_abroad_actual = data.get("is_abroad") or (country_code != "PL")
            history = await get_user_unique_records(user_id)
            
            if location and location not in history.get("locations", []):
                from aiogram.types import FSInputFile
                try:
                    await message.answer_photo(
                        photo=FSInputFile("assets/kasia_new_object.png"),
                        caption=f"📂 Ого! У нас новый объект: **{location} {country_flag}**!\nЗавожу под него папку.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить фото нового объекта: {e}")

            if car and car not in history.get("cars", []):
                from aiogram.types import FSInputFile
                try:
                    await message.answer_photo(
                        photo=FSInputFile("assets/kasia_garage_add.png"),
                        caption=f"🚙 Загоняю **{car}** в наш Виртуальный Гараж! Мотор шепчет, к поездкам готова.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить фото гаража: {e}")
            
            dates_to_process = [start_date]
            if status in ["L4", "Urlop"] and end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                if end_date > start_date:
                    curr = start_date
                    while curr < end_date:
                        curr += timedelta(days=1)
                        dates_to_process.append(curr)
            
            work_hours = float(data.get("hours") or 0)
            driving_hours = float(data.get("drive") or 0)
            route = data.get("route") or ""
            log_text = "Логістика" if user_lang == "UKR" else "Logistyka" if user_lang == "PL" else "Логистика"

            if route and "-" in route and driving_hours <= 0:
                calc_task = asyncio.create_task(calculate_driving_hours(route))
                frames = [f"🏢 ⠤⠤⠤⠤⠤⠤⠤ 🚗", f"🏢 ⠤⠤⠤⠤⠤ 🚗 ⠤⠤", f"🏢 ⠤⠤⠤ 🚗 ⠤⠤⠤⠤", f"🏢 ⠤ 🚗 ⠤⠤⠤⠤⠤⠤", f"🏢 🚗 ⠤⠤⠤⠤⠤⠤⠤"]
                for frame in frames:
                    try:
                        await status_msg.edit_text(f"🛣 {log_text}: {route}\n{frame}")
                        await asyncio.sleep(0.3)
                    except: pass
                driving_hours = await calc_task

            total_net, total_gross, total_loss, total_cash_diff = 0, 0, 0, 0
            ai_advice = ""
            
            # === СТРОГО ТВОЯ МАТЕМАТИКА (ВОЗВРАЩЕНО ИЗ webapp_2.py) ===
            applied_nbp_rate = await get_eur_rate(data.get("date")) if is_abroad_actual else None
            is_trip_int = 1 if data.get("is_trip") else 0
            eff_rate = profile.get("extra_rate", 0)
            eff_drive = profile.get("rate_drive", 20.0)
            
            if is_abroad_actual and applied_nbp_rate:
                if profile.get("rate_eur", 0) > 0:
                    eff_rate = profile["rate_eur"] * applied_nbp_rate
                if profile.get("rate_drive_eur", 0) > 0:
                    eff_drive = profile["rate_drive_eur"] * applied_nbp_rate

            for d in dates_to_process:
                f_date, month_y = d.strftime("%d.%m.%Y"), d.strftime("%m.%Y")
                
                days_map = {
                    'RUS': ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
                    'UKR': ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"],
                    'PL': ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
                }
                day_w = days_map.get(user_lang, days_map['PL'])[d.weekday()]

                cash_part, bonuses, hours_50, hours_100 = 0, 0, 0, 0

                if status == "L4":
                    gross = 8 * profile.get("base_rate", 32.0) * 0.8
                    net = gross * profile.get("tax_coeff", 0.71)
                    total_loss += (8 * profile.get("base_rate", 32.0) * profile.get("tax_coeff", 0.71)) - net
                    is_trip_for_db = 0
                elif status == "Urlop":
                    gross = 8 * profile.get("base_rate", 32.0)
                    net = gross * profile.get("tax_coeff", 0.71)
                    is_trip_for_db = 0
                else:
                    is_trip_for_db = is_trip_int
                    weekday_num = d.weekday()
                    
                    if weekday_num == 5: hours_50, hours_100, normal_hours = work_hours, 0, 0 
                    elif weekday_num == 6: hours_50, hours_100, normal_hours = 0, work_hours, 0 
                    else: 
                        hours_50 = max(0, work_hours - 8)
                        normal_hours = min(8, work_hours)
                        hours_100 = 0
                        
                    base_rate = profile.get("base_rate", 32.0)
                    tax_coeff = profile.get("tax_coeff", 0.71)
                    
                    gross = (normal_hours * base_rate) + (hours_50 * base_rate * 1.5) + (hours_100 * base_rate * 2.0)
                    official_net = gross * tax_coeff
                    
                    real_total = (normal_hours * eff_rate) + (hours_50 * eff_rate * 1.5) + (hours_100 * eff_rate * 2.0) + (driving_hours * eff_drive)
                    
                    if is_trip_for_db: 
                        real_total += profile.get("diet_value", 45.0)
                        
                    net = real_total
                    bonuses = max(0, net - official_net)
                    cash_part = bonuses 
                
                await upsert_work_log(
                    user_id, f_date, month_y, day_w, status, 
                    location, data.get("car",""), route, 
                    work_hours, driving_hours, hours_50, hours_100, 
                    is_trip_for_db, bonuses, gross, net
                )
                
                total_net += net
                total_gross += gross
                total_cash_diff += cash_part
            
            status_labels = {
                "Work": {"PL": "💼 Praca", "UKR": "💼 Робота", "RUS": "💼 Работа"},
                "L4": {"PL": "💊 Zwolnienie (L4)", "UKR": "💊 Лікарняний (L4)", "RUS": "💊 Больничный (L4)"},
                "Urlop": {"PL": "🌴 Urlop", "UKR": "🌴 Відпустка", "RUS": "🌴 Отпуск"}
            }
            status_icon = status_labels.get(status, status_labels["Work"]).get(user_lang, status_labels["Work"]["RUS"])
            
            if status == "Work" and (work_hours + driving_hours) >= 12:
                ai_advice = f"\n\n🤖 {t['overwork_msg'].format(hours=(work_hours + driving_hours))}"
            
            dyn_url = await build_app_url(user_id) 
            total_shifts = await increment_shift_count(user_id)
            
            # Ссылка на кофе теперь отображается в каждом чеке, показывая прогресс смен
            coffee_msg = f"\n\n☕️ <i>Всего смен: {total_shifts} | <a href='https://www.buymeacoffee.com/bocxodv'>Угостить Касю кофе</a></i>"
            
            day_idx = start_date.weekday() 
            day_name = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][day_idx]
            if user_lang == "PL": day_name = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"][day_idx]
            elif user_lang == "UKR": day_name = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"][day_idx]

            # Получаем уникальную цитату от Gemini 3.5 Flash
            motivation_text = await get_dynamic_motivation(user_lang)

            # Эстетичный финальный чек
            tax_coeff_val = profile.get("tax_coeff", 0.71)
            card_money = total_gross * tax_coeff_val
            
            final_text = (
                "🧾 <b>СМЕНА ЗАКРЫТА</b> 🧾\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 <b>Дата:</b> {start_date.strftime('%d.%m.%Y')} ({day_name})\n"
                f"🛠 <b>Статус:</b> {status_icon}\n"
                f"📍 <b>Объект:</b> {location} {country_flag}\n"
                "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"⏱ На объекте: <code>{work_hours:.1f} ч.</code>\n"
                f"🚗 За рулем:   <code>{driving_hours:.1f} ч.</code>\n"
                "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                "💰 <b>ИТОГИ ДНЯ:</b>\n"
                f"💵 На руки:   <code>{total_net:.2f} zł</code>\n"
                f"📄 Брутто:    <code>{total_gross:.2f} zł</code>\n"
                f"💳 На карту:  <code>{card_money:.2f} zł</code>\n"
                f"✉️ В конверте: <code>{total_cash_diff:.2f} zł</code>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>{motivation_text}</i>\n"
                f"{ai_advice}"
                f"{coffee_msg}"
            )
            
            await message.bot.set_chat_menu_button(
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
                
            await message.answer(
                text=final_text, 
                reply_markup=markup, 
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True) # <--- Отключаем огромный баннер
                )
            
        elif data.get("action") == "update_settings":
            for field in ["base_rate", "extra_rate", "rate_eur", "rate_drive", "rate_drive_eur", "goal_target"]:
                val = data.get(field)
                if val is not None and str(val).strip() != "":
                    try:
                        clean_val = str(val).replace(",", ".").strip()
                        if clean_val: await update_user_setting(user_id, field, float(clean_val))
                    except ValueError: pass
            if "goal_name" in data: await update_user_setting(user_id, "goal_name", str(data["goal_name"]))
            if "goal_deadline" in data: await update_user_setting(user_id, "goal_deadline", str(data["goal_deadline"]))
            if data.get("lang"): await update_user_language(user_id, str(data["lang"]))
            
            dyn_url = await build_app_url(user_id)
            await message.bot.set_chat_menu_button(chat_id=user_id, menu_button=MenuButtonWebApp(text=t["menu_btn"], web_app=WebAppInfo(url=dyn_url)))
            
            markup = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=t["menu_btn"], web_app=WebAppInfo(url=dyn_url))]],
                resize_keyboard=True
            )
            await message.answer(t["set_ok"], parse_mode="HTML", reply_markup=markup)

        elif data.get("action") == "get_report":
            target_month = data.get("month") or datetime.now().strftime("%m.%Y")
            status_msg = await message.answer(t["report_wait"].format(month=target_month))
            await generate_excel_report(callback=None, target_user_id=user_id, target_month=target_month, bot=message.bot)
            try:
                await status_msg.delete()
            except Exception: pass
            await increment_report_count(user_id)
            reports_count, is_premium = await get_user_subscription_status(user_id)
            if not is_premium and reports_count > 0 and reports_count % 5 == 0:
                await message.answer(t["freemium"].format(count=reports_count), parse_mode="Markdown", reply_markup=get_support_keyboard(user_lang))

        elif data.get("action") == "audit":
            target_month = data.get("month")
            card_amount = float(data.get("card", 0))
            total_net = await get_monthly_net_sum(user_id, target_month)
            if total_net > 0:
                envelope = total_net - card_amount
                ten_percent = round(total_net * 0.10, 2)
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"💰 Закинуть 10% ({ten_percent} zł)", callback_data=f"add_savings_{ten_percent}")],
                    [InlineKeyboardButton(text="✍️ Ввести свою сумму", callback_data="custom_savings")]
                ])
                
                msg_text = (t["audit_ok"].format(month=target_month, card=card_amount, total=f"{total_net:.2f}", env=f"{max(0, envelope):.2f}") +
                            f"\n\n💡 *Совет от Каси:*\nОтличный месяц! Рекомендую отложить 10% от заработанного ({ten_percent} zł) в копилку на твою цель.")
                
                await message.answer(msg_text, parse_mode="Markdown", reply_markup=keyboard)
            else:
                await message.answer(t["audit_err"].format(month=target_month))

        elif data.get("action") == "analytics":
            target_month = data.get("month")
            analytics_data = await get_analytics_by_location(user_id, target_month)
            
            if not analytics_data:
                await message.answer(t["hist_err"].format(month=target_month))
                return
            
            labels = [row[0] for row in analytics_data]
            values = [row[3] for row in analytics_data]
            
            chart_config = {
                "type": "pie",
                "data": {
                    "labels": labels,
                    "datasets": [{
                        "data": values,
                        "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF"]
                    }]
                },
                "options": {
                    "title": { "display": True, "text": f"Доходы по объектам ({target_month})", "fontSize": 20 },
                    "plugins": { "datalabels": { "color": "white", "font": { "weight": "bold" } } }
                }
            }
            
            encoded_config = urllib.parse.quote(json.dumps(chart_config))
            chart_url = f"https://quickchart.io/chart?c={encoded_config}&width=500&height=300&bkg=white"

            msg_text = f"📊 **Аналитика по объектам за {target_month}**\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, row in enumerate(analytics_data):
                loc, t_work, t_drive, t_net = row[0], row[1], row[2], row[3]
                medal = medals[i] if i < 3 else "🔸"
                msg_text += f"{medal} **{loc}**: {t_net:.2f} zł\n"

            await message.answer_photo(
                photo=chart_url,
                caption=msg_text,
                parse_mode="Markdown"
            )

        elif data.get("action") == "history":
            target_month = data.get("month")
            logs = await get_work_logs_for_month(user_id, target_month)
            if not logs:
                await message.answer(t["hist_err"].format(month=target_month))
                return
            text = t["hist_ok"].format(month=target_month)
            keyboard = []
            for log in logs:
                date_str, status, net = log[0], log[2], log[13]     
                icon = "💼" if status == "Work" else "💊" if status == "L4" else "🌴"
                btn_text = f"❌ {date_str} ({icon} {net:.2f} zł)"
                keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"del_log_{date_str}")])
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"WebApp Error: {e}")
        t = TRANSLATIONS.get("RUS", TRANSLATIONS["RUS"])
        await message.answer(t["err"])

@router.callback_query(F.data.startswith("add_savings_"))
async def add_savings_fast(callback: types.CallbackQuery):
    amount = float(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    await add_user_savings(user_id, amount)
    profile = await get_user_profile(user_id)
    forecast = await calculate_forecast(user_id, profile)
    
    await callback.message.edit_text(
        f"✅ **Отложено {amount} zł в копилку!**\n\n{forecast}", 
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "custom_savings")
async def ask_custom_savings(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Напиши сумму, которую хочешь отложить (в злотых):")
    await state.set_state(SavingsState.waiting_for_amount)
    await callback.answer()

@router.message(SavingsState.waiting_for_amount)
async def process_custom_savings(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").strip())
        user_id = message.from_user.id
        
        await add_user_savings(user_id, amount)
        profile = await get_user_profile(user_id)
        forecast = await calculate_forecast(user_id, profile)
        
        await message.answer(f"✅ **Отложено {amount} zł в копилку!**\n\n{forecast}", parse_mode="Markdown")
        await state.clear()
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введи только число (например, 150 или 150.5):")

@router.callback_query(F.data.startswith("del_log_"))
async def delete_log_handler(callback: types.CallbackQuery):
    date_to_delete = callback.data.replace("del_log_", "")
    user_id = callback.from_user.id 
    profile = await get_user_profile(user_id)
    user_lang = profile.get("lang", "RUS")
    t = TRANSLATIONS.get(user_lang, TRANSLATIONS["RUS"])
    deleted_count = await delete_work_log(user_id, date_to_delete)
    if deleted_count > 0:
        await callback.answer(t["del_ok_alert"].format(date=date_to_delete), show_alert=True)
        await callback.message.answer(t["del_ok_msg"].format(date=date_to_delete), parse_mode="Markdown")
        await callback.message.delete() 
    else:
        await callback.answer(t["del_err"], show_alert=True)

@router.callback_query(F.data == "activate_premium")
async def process_premium_activation(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await activate_user_premium(user_id)
    profile = await get_user_profile(user_id)
    user_lang = profile.get("lang", "RUS")
    t = TRANSLATIONS.get(user_lang, TRANSLATIONS["RUS"])
    await callback.answer(t["pro_alert"], show_alert=True)
    await callback.message.edit_text(t["pro_msg"], parse_mode="Markdown")