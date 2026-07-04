import sys

with open('handlers/webapp.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''        elif data.get("action") in ["history", "history_edit"]:
            target_month = data.get("month")
            logs = await get_work_logs_for_month(user_id, target_month)
            if not logs:
                await message.answer(t["hist_err"].format(month=target_month))
                return
            text = t["hist_ok"].format(month=target_month)'''

new_block = '''        elif data.get("action") == "history_edit":
            target_date = data.get("date")
            if not target_date:
                await message.answer("Выберите дату.")
                return
            logs = await get_work_logs_for_date(user_id, target_date)
            if not logs:
                await message.answer(t.get("hist_err", "Смены за этот день не найдены.").format(month=target_date))
                return
            text = t.get("hist_edit_ok", "Смены за {date}:").format(date=target_date)'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('handlers/webapp.py', 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    print('REPLACED')
else:
    print('NOT FOUND')