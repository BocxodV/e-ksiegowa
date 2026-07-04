
import sys
content = open('handlers/webapp.py', 'r', encoding='utf-8').read()
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
                await message.answer("???????? ????.")
                return
            logs = await get_work_logs_for_date(user_id, target_date)
            if not logs:
                await message.answer(t.get("hist_err", "????? ?? ???? ???? ?? ???????.").format(month=target_date))
                return
            text = t.get("hist_edit_ok", "????? ?? {date}:").format(date=target_date)'''

content = content.replace(old_block, new_block)
open('handlers/webapp.py', 'w', encoding='utf-8').write(content)

