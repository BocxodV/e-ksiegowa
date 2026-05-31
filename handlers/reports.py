# handlers/reports.py
import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from aiogram import Router, types, F, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

# Импортируем наши новые асинхронные функции
from database import get_user_profile, get_available_months, get_work_logs_for_month
from texts import TRANSLATIONS

router = Router()

@router.message(F.text.in_(["📊 Mój raport", "📊 Мій звіт", "📊 Мой отчет"]))
async def ask_report_month(message: types.Message):
    user_id = message.from_user.id
    profile = await get_user_profile(user_id) # Добавили await
    t = TRANSLATIONS.get(profile["lang"], TRANSLATIONS["PL"])

    # Запрашиваем месяцы асинхронно
    months = await get_available_months(user_id)

    if not months:
        await message.answer(t["empty_db"])
        return

    all_buttons = [InlineKeyboardButton(text=f"📅 {m[0]}", callback_data=f"report_{m[0]}") for m in months]
    rows_of_3 = [all_buttons[i:i+3] for i in range(0, len(all_buttons), 3)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows_of_3)
    await message.answer(t["choose_month"], reply_markup=keyboard)

@router.callback_query(F.data.startswith("report_"))
async def generate_excel_report(callback: types.CallbackQuery = None, target_user_id=None, target_month=None, bot: Bot = None):
    if callback:
        user_id = callback.from_user.id
        selected_month = callback.data.split("_")[1]
        await callback.message.delete()
        await callback.bot.send_chat_action(chat_id=callback.message.chat.id, action="upload_document")
    else:
        user_id = target_user_id
        selected_month = target_month

    profile = await get_user_profile(user_id) # Добавили await
    t = TRANSLATIONS.get(profile["lang"], TRANSLATIONS["PL"])

    # Получаем логи асинхронно
    rows = await get_work_logs_for_month(user_id, selected_month)

    if not rows:
        if callback:
            await callback.message.answer(t["empty_db"])
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Raport {selected_month}"

    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    center_aligned = Alignment(horizontal="center", vertical="center")
    left_aligned = Alignment(horizontal="left", vertical="center")

    urlop_fill = PatternFill(start_color="FFE699", end_color="FFE699", fill_type="solid")
    l4_fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")

    headers = t["excel_headers"]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_aligned

    # === ИЗМЕНЕНИЕ 1: Добавили счетчик total_drive_hours ===
    total_net, total_gross, total_bonuses, total_hours, total_drive_hours = 0, 0, 0, 0, 0

    for row in rows:
        is_trip_text = "✅" if row[10] == 1 else ""

        excel_row = [
            row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9],
            is_trip_text, row[11], row[12], row[13]
        ]
        ws.append(excel_row)

        current_row_num = ws.max_row
        status = row[2]
        fill_to_apply = urlop_fill if status == "Urlop" else l4_fill if status == "L4" else None

        for col_num, cell in enumerate(ws[current_row_num], start=1):
            if fill_to_apply:
                cell.fill = fill_to_apply
            if col_num in [4, 5, 6]:
                cell.alignment = left_aligned
            else:
                cell.alignment = center_aligned

        total_hours += row[6]
        # === ИЗМЕНЕНИЕ 2: Суммируем часы за рулем ===
        total_drive_hours += row[7] 
        total_bonuses += row[11]
        total_gross += row[12]
        total_net += row[13]

    ws.append([]) 

    card_money = total_gross * profile["tax_coeff"]
    envelope_money = total_net - card_money
    if envelope_money < 0: envelope_money = 0

    # === ИЗМЕНЕНИЕ 3: Выводим total_drive_hours в 8-ю колонку ===
    total_row = [
        "", "", "", "", t["total_month"], "", total_hours, total_drive_hours, "", "", "",
        round(total_bonuses, 2), round(total_gross, 2), round(total_net, 2)
    ]
    ws.append(total_row)

    ws.append([])
    ws.append(["", "", "", "", "", "💳 НА КАРТУ (Официально):", "", "", "", "", "", "", round(card_money, 2), "zł"])
    ws.append(["", "", "", "", "", "✉️ В КОНВЕРТЕ (Наличка):", "", "", "", "", "", "", round(envelope_money, 2), "zł"])

    for row_idx in range(ws.max_row - 2, ws.max_row + 1):
        for cell in ws[row_idx]:
            cell.font = Font(bold=True)
            cell.alignment = center_aligned

    ws.append([])
    last_row = ws.max_row + 1
    ws.merge_cells(start_row=last_row, start_column=11, end_row=last_row, end_column=14)
    sig_cell = ws.cell(row=last_row, column=11)
    sig_cell.value = "© Created by bocxodv"
    sig_cell.font = Font(italic=True, size=9, color="A6A6A6")
    sig_cell.alignment = Alignment(horizontal="right", vertical="center")

    for col in ws.columns:
        max_length = max((len(str(cell.value)) for cell in col if cell.value is not None), default=0)
        ws.column_dimensions[col[0].column_letter].width = (max_length * 1.25) + 3

    # === ГЛАВНЫЙ ФИКС ДЛЯ GOOGLE CLOUD RUN ===
    # Сохраняем файл во временную директорию /tmp/
    file_name = f"/tmp/Zarobki_{selected_month}.xlsx"
    
    wb.save(file_name)
    document = FSInputFile(file_name)

    caption_text = t["excel_caption"].format(
        month=selected_month,
        hours=total_hours,
        net=round(total_net, 2)
    )

    try:
        if callback:
            await callback.message.answer_document(document, caption=caption_text, parse_mode="Markdown")
        elif bot:
            await bot.send_document(user_id, document, caption=caption_text, parse_mode="Markdown")
    except Exception as e:
        print(f"Ошибка отправки: {e}")
    finally:
        os.remove(file_name)