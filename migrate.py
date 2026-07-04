import sqlite3
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def run_migration():
    # Load .env
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found in .env")
        return
    
    print(f"Connecting to Postgres: {db_url.split('@')[-1]}")
    pg_conn = await asyncpg.connect(db_url)
    
    # SQLite Connection
    db_file = "bot_database.db"
    if not os.path.exists(db_file):
        print(f"Error: {db_file} not found!")
        return
        
    print("Connecting to SQLite...")
    sl_conn = sqlite3.connect(db_file)
    sl_conn.row_factory = sqlite3.Row
    sl_cursor = sl_conn.cursor()
    
    # 1. Migrate Users
    sl_cursor.execute("SELECT * FROM users")
    users = sl_cursor.fetchall()
    print(f"Found {len(users)} users in SQLite.")
    
    for u in users:
        u_dict = dict(u)
        columns = list(u_dict.keys())
        values = list(u_dict.values())
        
        # Build query
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        col_names = ", ".join(columns)
        
        query = f"INSERT INTO users ({col_names}) VALUES ({placeholders}) ON CONFLICT (user_id) DO NOTHING"
        await pg_conn.execute(query, *values)
        
    print("Users migrated successfully.")
    
    # 2. Migrate Work Logs
    sl_cursor.execute("SELECT * FROM work_logs")
    logs = sl_cursor.fetchall()
    print(f"Found {len(logs)} work logs in SQLite.")
    
    for log in logs:
        l_dict = dict(log)
        # We don't want to insert 'id' if we want PG to auto-increment, 
        # but to keep exact match we CAN insert 'id' as well. 
        # The schema uses SERIAL, so inserting explicit 'id' is fine, 
        # but we must reset the sequence afterwards!
        columns = list(l_dict.keys())
        values = list(l_dict.values())
        
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        col_names = ", ".join(columns)
        
        query = f"INSERT INTO work_logs ({col_names}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
        await pg_conn.execute(query, *values)
        
    # Reset sequence for work_logs_id_seq
    if logs:
        max_id = max(log['id'] for log in logs)
        print(f"Resetting work_logs sequence to {max_id + 1}...")
        await pg_conn.execute(f"SELECT setval('work_logs_id_seq', {max_id + 1}, false)")

    print("Work logs migrated successfully.")
    
    await pg_conn.close()
    sl_conn.close()
    print("Migration COMPLETE!")

if __name__ == "__main__":
    asyncio.run(run_migration())
