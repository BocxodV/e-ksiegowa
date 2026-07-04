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

# Import local motivational content instead of calling external models
from texts import TRANSLATIONS, get_random_motivation
from keyboards import get_support_keyboard 
from nbp_service import get_eur_rate
from database import (
    get_user_profile, 
    upsert_work_log, update_user_setting,
    get_monthly_net_sum, increment_report_count, get_user_subscription_status,
    activate_user_premium, update_user_language,
    increment_shift_count, delete_work_log, get_work_logs_for_month, get_work_logs_for_date,
    add_user_savings, get_analytics_by_location,
    get_user_unique_records, get_work_log_id, get_user_vacations
)
from map_service import calculate_driving_hours, get_country_by_city

# Import report functions
from handlers.reports import generate_excel_report

router = Router()
logger = logging.getLogger(__name__)

WEB_APP_URL = "https://e-ksiegowa.vercel.app/"

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
    _ALLOWED_LANGS = {"RUS", "UKR", "PL", "ENG"}
    user_lang = profile.get("lang", "RUS")
    if user_lang not in _ALLOWED_LANGS:
        user_lang = "RUS"
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
    
    total_vacation_days = profile.get("total_vacation_days", 26)
    
    return f"{WEB_APP_URL}?v=15&base={base:g}&extra={extra:g}&eur={eur:g}&drive={drive:g}&drive_eur={drive_eur:g}&car={default_car}&g_name={goal_name}&g_target={goal_target:g}&c_net={current_net:.1f}&c_sav={current_savings:g}&g_dead={goal_deadline}&lang={user_lang}&cars={cars_str}&locs={locs_str}&vacation={total_vacation_days}"

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
                    logger.error(f"Failed to send new object notification photo: {e}")

            if car and car not in history.get("cars", []):
                from aiogram.types import FSInputFile
                try:
                    await message.answer_photo(
                        photo=FSInputFile("assets/kasia_garage_add.png"),
                        caption=f"🚙 Загоняю **{car}** в наш Виртуальный Гараж! Мотор шепчет, к поездкам готова.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to send garage registration photo: {e}")
            
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
            
            # === DETAILED WAGE AND TAX COMPUTATIONS ===
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
                    'PL': ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"],
                    'ENG': ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
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
                
                record = await get_work_log_id(user_id, f_date)
                record_id = record[0] if record else None
                is_abroad_int = 1 if is_abroad_actual else 0
                await upsert_work_log(
                    user_id, f_date, month_y, day_w, status, 
                    location, data.get("car",""), route, 
                    work_hours, driving_hours, hours_50, hours_100, 
                    is_trip_for_db, bonuses, gross, net, is_abroad_int=is_abroad_int, record_id=record_id
                )
                
                total_net += net
                total_gross += gross
                total_cash_diff += cash_part
            
            status_labels = {
                "Work": {"PL": "💼 Praca", "UKR": "💼 Робота", "RUS": "💼 Работа", "ENG": "💼 Work"},
                "L4": {"PL": "💊 Zwolnienie (L4)", "UKR": "💊 Лікарняний (L4)", "RUS": "💊 Больничный (L4)", "ENG": "💊 Sick Leave (L4)"},
                "Urlop": {"PL": "🌴 Urlop", "UKR": "🌴 Відпустка", "RUS": "🌴 Отпуск", "ENG": "🌴 Vacation"}
            }
            status_icon = status_labels.get(status, status_labels["Work"]).get(user_lang, status_labels["Work"]["RUS"])
            
            if status == "Work" and (work_hours + driving_hours) >= 12:
                ai_advice = f"\n\n🤖 {t['overwork_msg'].format(hours=(work_hours + driving_hours))}"
            
            dyn_url = await build_app_url(user_id) 
            total_shifts = await increment_shift_count(user_id)
            
            total_shifts_label = {"ENG": "Total shifts", "PL": "Suma zmian", "UKR": "Всього змін", "RUS": "Всего смен"}.get(user_lang, "Всего смен")
            coffee_label = {"ENG": "Buy Kasia a coffee", "PL": "Postaw Kasi kawę", "UKR": "Пригостити Касю кавою", "RUS": "Угостить Касю кофе"}.get(user_lang, "Угостить Касю кофе")
            coffee_msg = f"\n\n☕️ <i>{total_shifts_label}: {total_shifts} | <a href='https://www.buymeacoffee.com/bocxodv'>{coffee_label}</a></i>"
            
            day_idx = start_date.weekday() 
            day_name = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][day_idx]
            if user_lang == "PL": day_name = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"][day_idx]
            elif user_lang == "UKR": day_name = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"][day_idx]
            elif user_lang == "ENG": day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day_idx]

            # Retrieve localized motivational quote locally
            motivation_text = get_random_motivation(user_lang)

            tax_coeff_val = profile.get("tax_coeff", 0.71)
            card_money = total_gross * tax_coeff_val
            
            # Localized labels for shift submission confirmation message
            shift_title = {"ENG": "SHIFT CLOSED", "PL": "ZMIANA ZAKOŃCZONA", "UKR": "ЗМІНА ЗАКРИТА", "RUS": "СМЕНА ЗАКРЫТА"}.get(user_lang, "СМЕНА ЗАКРЫТА")
            lbl_date = {"ENG": "Date", "PL": "Data", "UKR": "Дата", "RUS": "Дата"}.get(user_lang, "Дата")
            lbl_status = {"ENG": "Status", "PL": "Status", "UKR": "Статус", "RUS": "Статус"}.get(user_lang, "Статус")
            lbl_object = {"ENG": "Object", "PL": "Obiekt", "UKR": "Об'єкт", "RUS": "Объект"}.get(user_lang, "Объект")
            lbl_on_site = {"ENG": "On site", "PL": "Na obiekcie", "UKR": "На об'єкті", "RUS": "На объекте"}.get(user_lang, "На объекте")
            lbl_driving = {"ENG": "Driving", "PL": "Za kierownicą", "UKR": "Za kierownicą", "RUS": "За рулем"}.get(user_lang, "За рулем")
            lbl_h = {"ENG": "h", "PL": "h", "UKR": "год", "RUS": "ч."}.get(user_lang, "ч.")
            lbl_day_summary = {"ENG": "DAILY SUMMARY", "PL": "PODSUMOWANIE DNIA", "UKR": "ПІДСУМКИ ДНЯ", "RUS": "ИТОГИ ДНЯ"}.get(user_lang, "ИТОГИ ДНЯ")
            lbl_net_payout = {"ENG": "Net payout", "PL": "Na rękę", "UKR": "На руки", "RUS": "На руки"}.get(user_lang, "На руки")
            lbl_gross = {"ENG": "Gross", "PL": "Brutto", "UKR": "Брутто", "RUS": "Брутто"}.get(user_lang, "Брутто")
            lbl_to_card = {"ENG": "To card", "PL": "Na kartę", "UKR": "На карту", "RUS": "На карту"}.get(user_lang, "На карту")
            lbl_env = {"ENG": "Unresolved balance (Nierozliczone saldo)", "PL": "Nierozliczone saldo", "UKR": "Nierozliczone saldo", "RUS": "Nierozliczone saldo"}.get(user_lang, "Nierozliczone saldo")
            
            final_text = (
                f"🧾 <b>{shift_title}</b> 🧾\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 <b>{lbl_date}:</b> {start_date.strftime('%d.%m.%Y')} ({day_name})\n"
                f"🛠 <b>{lbl_status}:</b> {status_icon}\n"
                f"📍 <b>{lbl_object}:</b> {location} {country_flag}\n"
                "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"⏱ {lbl_on_site}: <code>{work_hours:.1f} {lbl_h}</code>\n"
                f"🚗 {lbl_driving}:   <code>{driving_hours:.1f} {lbl_h}</code>\n"
                "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"💰 <b>{lbl_day_summary}:</b>\n"
                f"💵 {lbl_net_payout}:   <code>{total_net:.2f} zł</code>\n"
                f"📄 {lbl_gross}:    <code>{total_gross:.2f} zł</code>\n"
                f"💳 {lbl_to_card}:  <code>{card_money:.2f} zł</code>\n"
                f"⚖️ {lbl_env}: <code>{total_cash_diff:.2f} zł</code>\n"
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
                link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
            
        elif data.get("action") == "update_settings":
            for field in ["base_rate", "extra_rate", "rate_eur", "rate_drive", "rate_drive_eur", "goal_target", "total_vacation_days"]:
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
            month = data.get("month") or datetime.now().strftime("%m.%Y")
            status_msg = await message.answer(t["report_wait"].format(month=month))
            from handlers.reports import generate_excel_report
            await generate_excel_report(target_user_id=user_id, target_month=month, bot=message.bot)
            try:
                await status_msg.delete()
            except Exception: pass
            await increment_report_count(user_id)
            reports_count, is_premium = await get_user_subscription_status(user_id)
            if not is_premium and reports_count > 0 and reports_count % 5 == 0:
                await message.answer(t["freemium"].format(count=reports_count), parse_mode="Markdown", reply_markup=get_support_keyboard(user_lang))

        elif data.get("action") == "get_boss_report":
            month = data.get("month") or datetime.now().strftime("%m.%Y")
            status_msg = await message.answer(t["report_wait"].format(month=month))
            from handlers.reports import generate_boss_excel_report
            await generate_boss_excel_report(target_user_id=user_id, target_month=month, bot=message.bot)
            try:
                await status_msg.delete()
            except Exception: pass
            await increment_report_count(user_id)
            reports_count, is_premium = await get_user_subscription_status(user_id)
            if not is_premium and reports_count > 0 and reports_count % 5 == 0:
                await message.answer(t["freemium"].format(count=reports_count), parse_mode="Markdown", reply_markup=get_support_keyboard(user_lang))

        elif data.get("action") == "get_pure_logistics_report":
            month = data.get("month") or datetime.now().strftime("%m.%Y")
            status_msg = await message.answer(t["report_wait"].format(month=month))
            from handlers.reports import generate_pure_logistics_report
            await generate_pure_logistics_report(target_user_id=user_id, target_month=month, bot=message.bot)
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
                
                # Dynamic translation for audit inline buttons
                btn_save_10 = {
                    "ENG": f"💰 Save 10% ({ten_percent} zł)",
                    "PL": f"💰 Odłóż 10% ({ten_percent} zł)",
                    "UKR": f"💰 Відкласти 10% ({ten_percent} zł)",
                    "RUS": f"💰 Закинуть 10% ({ten_percent} zł)"
                }.get(user_lang, f"💰 Закинуть 10% ({ten_percent} zł)")
                
                btn_custom = {
                    "ENG": "✍️ Enter custom amount",
                    "PL": "✍️ Wpisz własną kwotę",
                    "UKR": "✍️ Ввести свою суму",
                    "RUS": "✍️ Ввести свою сумму"
                }.get(user_lang, "✍️ Ввести свою сумму")
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=btn_save_10, callback_data=f"add_savings_{ten_percent}")],
                    [InlineKeyboardButton(text=btn_custom, callback_data="custom_savings")]
                ])
                
                advice_tip = {
                    "ENG": f"\n\n💡 *Kasia's Advice:*\nGreat month! I recommend putting aside 10% of your earnings ({ten_percent} zł) into the piggy bank for your goal.",
                    "PL": f"\n\n💡 *Rada od Kasi:*\nŚwietny miesiąc! Zalecam odłożyć 10% zarobków ({ten_percent} zł) do skarbonki na Twój cel.",
                    "UKR": f"\n\n💡 *Порада від Касі:*\nЧудовий місяць! Рекомендую відкласти 10% від заробленого ({ten_percent} zł) у скарбничку на твою мету.",
                    "RUS": f"\n\n💡 *Совет от Каси:*\nОтличный месяц! Рекомендую отложить 10% от заработанного ({ten_percent} zł) в копилку на твою цель."
                }.get(user_lang, f"\n\n💡 *Совет от Каси:*\nОтличный месяц! Рекомендую отложить 10% от заработанного ({ten_percent} zł) в копилку на твою цель.")
                
                msg_text = t["audit_ok"].format(month=target_month, card=card_amount, total=f"{total_net:.2f}", env=f"{max(0, envelope):.2f}") + advice_tip
                
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
            values = [float(row[3]) if row[3] is not None else 0.0 for row in analytics_data]
            
            chart_title = {
                "ENG": f"Earnings by objects ({target_month})",
                "PL": f"Przychody według obiektów ({target_month})",
                "UKR": f"Прибутки по об'єктах ({target_month})",
                "RUS": f"Доходы по объектам ({target_month})"
            }.get(user_lang, f"Доходы по объектам ({target_month})")
            
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
                    "title": { "display": True, "text": chart_title, "fontSize": 20 },
                    "plugins": { "datalabels": { "color": "white", "font": { "weight": "bold" } } }
                }
            }
            
            encoded_config = urllib.parse.quote(json.dumps(chart_config))
            quickchart_key = os.environ.get("QUICKCHART_API_KEY", "")
            key_param = f"key={quickchart_key}&" if quickchart_key else ""
            chart_url = f"https://quickchart.io/chart?{key_param}c={encoded_config}&width=500&height=300&bkg=white"

            analytics_title = {
                "ENG": f"📊 **Analytics by objects for {target_month}**\n\n",
                "PL": f"📊 **Analityka obiektów za {target_month}**\n\n",
                "UKR": f"📊 **Аналітика по об'єктах за {target_month}**\n\n",
                "RUS": f"📊 **Аналитика по объектам за {target_month}**\n\n"
            }.get(user_lang, f"📊 **Аналитика по объектам за {target_month}**\n\n")
            
            msg_text = analytics_title
            medals = ["🥇", "🥈", "🥉"]
            h_lbl = {"ENG": "h", "PL": "h", "UKR": "год", "RUS": "ч."}.get(user_lang, "ч.")
            for i, row in enumerate(analytics_data):
                loc, t_work, t_drive, t_net = row[0], row[1], row[2], row[3]
                medal = medals[i] if i < 3 else "🔸"
                msg_text += f"{medal} **{loc}**: {t_net:.2f} zł (⏱ {t_work:g} {h_lbl} | 🚗 {t_drive:g} {h_lbl})\n"

            await message.answer_photo(
                photo=chart_url,
                caption=msg_text,
                parse_mode="Markdown"
            )

        elif data.get("action") == "vacation_stats":
            vacations = await get_user_vacations(user_id)
            profile = await get_user_profile(user_id)
            total_allowed = profile.get("total_vacation_days", 26)
            used = len(vacations)
            remaining = max(0, total_allowed - used)

            title_map = {
                "RUS": "🌴 **Статус отпуска**\n\n",
                "UKR": "🌴 **Статус відпустки**\n\n",
                "PL": "🌴 **Status urlopu**\n\n",
                "ENG": "🌴 **Vacation Status**\n\n"
            }
            stats_text = title_map.get(user_lang, title_map["RUS"])
            
            allowed_lbl = {"ENG": "Total allowed:", "PL": "Przysługuje rocznie:", "UKR": "Всього днів:", "RUS": "Всего дней в году:"}.get(user_lang, "Всего дней в году:")
            used_lbl = {"ENG": "Days used:", "PL": "Wykorzystano dni:", "UKR": "Використано днів:", "RUS": "Использовано дней:"}.get(user_lang, "Использовано дней:")
            rem_lbl = {"ENG": "Remaining days:", "PL": "Pozostało dni:", "UKR": "Залишилось днів:", "RUS": "Осталось дней:"}.get(user_lang, "Осталось дней:")
            
            stats_text += f"🔹 {allowed_lbl} **{total_allowed}**\n"
            stats_text += f"🔻 {used_lbl} **{used}**\n"
            stats_text += f"✅ {rem_lbl} **{remaining}**\n\n"
            
            if used > 0:
                list_lbl = {"ENG": "Dates used:", "PL": "Wykorzystane daty:", "UKR": "Використані дати:", "RUS": "Даты отпуска:"}.get(user_lang, "Даты отпуска:")
                stats_text += f"📅 **{list_lbl}**\n"
                
                # Format them nicely
                for v in vacations:
                    stats_text += f"▫️ {v}\n"
                    
            await message.answer(stats_text, parse_mode="Markdown")

        elif data.get("action") == "history_view":
            target_month = data.get("month")
            logs = await get_work_logs_for_month(user_id, target_month)
            if not logs:
                await message.answer(t["hist_err"].format(month=target_month))
                return
            
            total_work_hours = 0.0
            total_driving_hours = 0.0
            total_net = 0.0
            
            title_map = {
                "RUS": "📋 **Просмотр смен за {month}**\n\n",
                "UKR": "📋 **Перегляд змін за {month}**\n\n",
                "PL": "📋 **Podgląd zmian w {month}**\n\n",
                "ENG": "📋 **View shifts for {month}**\n\n"
            }
            title = title_map.get(user_lang, title_map["RUS"]).format(month=target_month)
            lines = [title]
            
            for log in logs:
                log_date, day_of_week, status, location, car, route, work_hours, driving_hours, hours_50, hours_100, is_trip, bonuses, gross, net, *extra = log
                
                work_hours_f = float(work_hours or 0)
                driving_hours_f = float(driving_hours or 0)
                net_f = float(net or 0)
                
                total_work_hours += work_hours_f
                total_driving_hours += driving_hours_f
                total_net += net_f
                
                icon = "💼" if status == "Work" else "💊" if status == "L4" else "🌴"
                status_desc = {
                    "Work": {"RUS": "Работа", "UKR": "Робота", "PL": "Praca", "ENG": "Work"},
                    "L4": {"RUS": "Больничный (L4)", "UKR": "Лікарняний (L4)", "PL": "Zwolnienie (L4)", "ENG": "Sick Leave (L4)"},
                    "Urlop": {"RUS": "Отпуск", "UKR": "Відпустка", "PL": "Urlop", "ENG": "Vacation"}
                }.get(status, {"RUS": status, "UKR": status, "PL": status, "ENG": status}).get(user_lang, status)
                
                day_short = day_of_week[:3] if day_of_week else ""
                lines.append(f"📅 **{log_date} ({day_short})** — {icon} {status_desc}")
                
                if status == "Work":
                    if location:
                        loc_lbl = "Object" if user_lang == "ENG" else "Объект" if user_lang == "RUS" else "Об'єкт" if user_lang == "UKR" else "Obiekt"
                        car_lbl = "Car" if user_lang == "ENG" else "Авто" if user_lang in ["RUS", "UKR"] else "Auto"
                        lines.append(f"   📍 {loc_lbl}: {location}" + (f" | 🚛 {car_lbl}: {car}" if car else ""))
                    
                    if work_hours_f > 0 or driving_hours_f > 0:
                        h_lbl = "h" if user_lang in ["PL", "ENG"] else "ч." if user_lang == "RUS" else "год" if user_lang == "UKR" else "h"
                        on_site_lbl = "On site" if user_lang == "ENG" else "Na obiekcie" if user_lang == "PL" else "На об'єкті" if user_lang == "UKR" else "На объекте"
                        driving_lbl = "Driving" if user_lang == "ENG" else "Za kierownicą" if user_lang == "PL" else "За кермом" if user_lang == "UKR" else "За рулем"
                        lines.append(f"   ⏱ {on_site_lbl}: {work_hours_f:g} {h_lbl} | 🚗 {driving_lbl}: {driving_hours_f:g} {h_lbl}")
                        
                    if route:
                        r_lbl = "Route" if user_lang == "ENG" else "Маршрут" if user_lang in ["RUS", "UKR"] else "Trasa"
                        lines.append(f"   🛣 {r_lbl}: {route}")
                
                net_lbl = "Net" if user_lang == "ENG" else "Чистыми" if user_lang == "RUS" else "Чистими" if user_lang == "UKR" else "Netto"
                lines.append(f"   💰 {net_lbl}: **{net_f:.2f} zł**")
                lines.append("   ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
            
            tot_lbl = "TOTAL" if user_lang == "ENG" else "ИТОГО" if user_lang == "RUS" else "ВСОГО" if user_lang == "UKR" else "RAZEM"
            w_tot_lbl = "On site" if user_lang == "ENG" else "На объекте" if user_lang == "RUS" else "На об'єкті" if user_lang == "UKR" else "Na obiekcie"
            d_tot_lbl = "Driving" if user_lang == "ENG" else "За рулем" if user_lang == "RUS" else "За кермом" if user_lang == "UKR" else "Za kierownicą"
            n_tot_lbl = "Earned" if user_lang == "ENG" else "Заработано" if user_lang == "RUS" else "Зароблено" if user_lang == "UKR" else "Zarobiono"
            h_lbl = "h" if user_lang in ["PL", "ENG"] else "ч." if user_lang == "RUS" else "год" if user_lang == "UKR" else "h"
            
            lines.append(f"\n📊 **{tot_lbl}:**")
            lines.append(f"⏱ {w_tot_lbl}: **{total_work_hours:g} {h_lbl}**")
            lines.append(f"🚗 {d_tot_lbl}: **{total_driving_hours:g} {h_lbl}**")
            lines.append(f"💵 {n_tot_lbl}: **{total_net:.2f} zł**")
            
            final_text = "\n".join(lines)
            await message.answer(final_text, parse_mode="Markdown")

        elif data.get("action") == "history_edit":
            target_date = data.get("date")
            if not target_date:
                await message.answer("Выберите дату.")
                return
            logs = await get_work_logs_for_date(user_id, target_date)
            if not logs:
                await message.answer(t.get("hist_err", "Смены за этот день не найдены.").format(month=target_date))
                return
            text = t.get("hist_edit_ok", "Смены за {date}:").format(date=target_date)
            keyboard = []
            profile = await get_user_profile(user_id)
            for log in logs:
                date_str, status, net = log[0], log[2], log[13]
                is_abroad_val = log[14] if len(log) > 14 else 0
                
                # Format to YYYY-MM-DD for HTML date input
                dt = datetime.strptime(date_str, "%d.%m.%Y")
                edate = dt.strftime("%Y-%m-%d")
                
                # build edit_url
                base_url = await build_app_url(user_id, profile)
                eobj = urllib.parse.quote(log[3] or "")
                ecar = urllib.parse.quote(log[4] or "")
                eroute = urllib.parse.quote(log[5] or "")
                work_hours = log[6] or 0.0
                driving_hours = log[7] or 0.0
                is_trip = log[10] or 0
                
                edit_params = f"&edit=true&edate={edate}&estatus={status}&ehours={work_hours:g}&edrive={driving_hours:g}&eobj={eobj}&ecar={ecar}&eroute={eroute}&eabroad={is_abroad_val}&ediet={is_trip}"
                edit_url = base_url + edit_params
                
                icon = "💼" if status == "Work" else "💊" if status == "L4" else "🌴"
                btn_del_text = f"❌ {date_str} ({icon} {net:.2f} zł)"
                btn_edit_text = t.get("btn_edit_log", "✏️ Изменить")
                
                keyboard.append([
                    InlineKeyboardButton(text=btn_del_text, callback_data=f"del_log_{date_str}"),
                    InlineKeyboardButton(text=btn_edit_text, web_app=WebAppInfo(url=edit_url))
                ])
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")

        elif data.get("action") == "feedback":
            text = data.get("text", "").strip()
            if text:
                from config import ADMIN_ID
                user_info = f"От: {message.from_user.full_name} (@{message.from_user.username}, ID: {message.from_user.id})"
                feedback_msg = f"📬 **НОВЫЙ ОТЗЫВ ИЗ WEBAPP**\n{user_info}\n\n{text}"
                try:
                    await message.bot.send_message(ADMIN_ID, feedback_msg, parse_mode="Markdown")
                    await message.answer("✅ Спасибо! Твой отзыв успешно отправлен разработчику.")
                except Exception as e:
                    await message.answer("❌ Произошла ошибка при отправке отзыва. Пожалуйста, попробуй позже.")

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