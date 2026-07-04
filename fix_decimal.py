with open('handlers/webapp.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'values = [row[3] for row in analytics_data]',
    'values = [float(row[3]) if row[3] is not None else 0.0 for row in analytics_data]'
)

with open('handlers/webapp.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print('Updated decimal fix')