import asyncio
import asyncpg
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def main():
    conn = await asyncpg.connect("postgresql://neondb_owner:npg_hBCcwvoXYF86@ep-ancient-math-alkpj39z-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require")
    
    result = await conn.execute(
        "UPDATE work_logs SET location = 'SWISS KRONO/Żary' WHERE location ILIKE '%krono%' OR location ILIKE '%Свисс Кроно%'"
    )
    print(f'Update result: {result}')

    await conn.close()

asyncio.run(main())