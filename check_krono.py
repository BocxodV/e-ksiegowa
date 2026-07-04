import asyncio
import asyncpg
import os

async def main():
    conn = await asyncpg.connect("postgresql://neondb_owner:npg_hBCcwvoXYF86@ep-ancient-math-alkpj39z-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require")
    
    records = await conn.fetch("SELECT DISTINCT location FROM work_logs WHERE location ILIKE '%krono%'")
    print('Locations with Krono:')
    for r in records:
        print(f'- {r["location"]}')
        
    await conn.close()

asyncio.run(main())