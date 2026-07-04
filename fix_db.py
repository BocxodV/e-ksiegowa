import asyncio
import os
import asyncpg
from config import DATABASE_URL

async def run():
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT DISTINCT location FROM work_logs WHERE location ILIKE '%swiss krono%'")
        print('Found variations:', [r['location'] for r in records])
        
        # update all variations to just 'SWISS KRONO'
        result = await conn.execute("UPDATE work_logs SET location = 'SWISS KRONO' WHERE location ILIKE '%swiss krono%'")
        print('Update result:', result)
        
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        print('Tables:', [t['table_name'] for t in tables])
        
asyncio.run(run())
