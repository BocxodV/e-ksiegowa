with open('handlers/webapp.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'delete_work_log, get_work_logs_for_month,',
    'delete_work_log, get_work_logs_for_month, get_work_logs_for_date,'
)

with open('handlers/webapp.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print('Updated imports')