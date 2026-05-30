# database.py
import asyncpg
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

# Глобальный пул соединений
pool = None

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL)
    return pool

async def init_db():
    """Создает таблицы и обновляет структуру при запуске в PostgreSQL."""
    p = await get_pool()
    async with p.acquire() as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                language TEXT DEFAULT 'PL',
                base_rate NUMERIC DEFAULT 32.0,
                extra_rate NUMERIC DEFAULT 4.0,
                tax_coeff NUMERIC DEFAULT 0.71,
                rate_drive NUMERIC DEFAULT 20.0,
                diet_value NUMERIC DEFAULT 45.0,
                night_coeff NUMERIC DEFAULT 0.2,
                last_location TEXT,
                last_country TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS work_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                log_date TEXT,
                month_year TEXT,
                day_of_week TEXT,
                status TEXT,
                location TEXT,
                car TEXT,
                route TEXT,
                work_hours NUMERIC,
                driving_hours NUMERIC,
                hours_50 NUMERIC,
                hours_100 NUMERIC,
                is_trip INTEGER,
                bonuses NUMERIC,
                gross NUMERIC,
                net NUMERIC
            )
        ''')
        
        # Безопасное добавление колонок (PostgreSQL поддерживает IF NOT EXISTS)
        columns = [
            "language TEXT DEFAULT 'PL'",
            "last_location TEXT", 
            "last_country TEXT", 
            "rate_eur NUMERIC DEFAULT 0.0", 
            "rate_drive_eur NUMERIC DEFAULT 0.0",
            "default_car TEXT DEFAULT ''",
            "reports_generated INTEGER DEFAULT 0",
            "is_premium INTEGER DEFAULT 0",
            "goal_name TEXT DEFAULT 'Финансовая цель'", 
            "goal_target NUMERIC DEFAULT 8000.0",
            "shifts_added INTEGER DEFAULT 0",
            "current_savings NUMERIC DEFAULT 0.0",
            "goal_deadline TEXT DEFAULT ''"
        ]
        for col in columns:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col}")
            except Exception as e:
                pass

async def get_user_profile(user_id):
    p = await get_pool()
    async with p.acquire() as db:
        user = await db.fetchrow('''
            SELECT 
                language, base_rate, extra_rate, tax_coeff, rate_drive, 
                rate_eur, rate_drive_eur, default_car, goal_name, 
                goal_target, current_savings, goal_deadline 
            FROM users WHERE user_id = $1
        ''', user_id)

        if not user:
            await db.execute('INSERT INTO users (user_id) VALUES ($1)', user_id)
            return await get_user_profile(user_id)
        
        return {
            "lang": user[0],
            "base_rate": float(user[1]) if user[1] else 0.0,
            "extra_rate": float(user[2]) if user[2] else 0.0, 
            "tax_coeff": float(user[3]) if user[3] else 0.0,
            "rate_drive": float(user[4]) if user[4] else 0.0,
            "rate_eur": float(user[5]) if user[5] else 0.0, 
            "rate_drive_eur": float(user[6]) if user[6] else 0.0,
            "default_car": user[7] or "",
            "goal_name": user[8] or "Финансовая цель",     
            "goal_target": float(user[9]) if user[9] else 8000.0,
            "current_savings": float(user[10]) if user[10] else 0.0,
            "goal_deadline": user[11] or ""
        }

async def update_user_setting(user_id, field, value):
    p = await get_pool()
    async with p.acquire() as db:
        await db.execute(f'UPDATE users SET {field} = $1 WHERE user_id = $2', value, user_id)

async def update_user_language(user_id, lang):
    p = await get_pool()
    async with p.acquire() as db:
        await db.execute('UPDATE users SET language = $1 WHERE user_id = $2', lang, user_id)

async def update_last_location(user_id, location, country):
    p = await get_pool()
    async with p.acquire() as db:
        await db.execute("UPDATE users SET last_location=$1, last_country=$2 WHERE user_id=$3", location, country, user_id)

async def get_users_for_audit():
    p = await get_pool()
    async with p.acquire() as db:
        return await db.fetch("SELECT user_id, language FROM users")

async def get_all_users():
    p = await get_pool()
    async with p.acquire() as db:
        return await db.fetch("SELECT user_id FROM users")

async def get_work_logs_for_month(user_id, month_year):
    p = await get_pool()
    async with p.acquire() as db:
        return await db.fetch('''
            SELECT log_date, day_of_week, status, location, car, route, work_hours, driving_hours, hours_50, hours_100, is_trip, bonuses, gross, net
            FROM work_logs
            WHERE user_id = $1 AND month_year = $2
            ORDER BY log_date ASC
        ''', user_id, month_year)

async def delete_work_log(user_id, log_date):
    p = await get_pool()
    async with p.acquire() as db:
        status = await db.execute("DELETE FROM work_logs WHERE user_id=$1 AND log_date=$2", user_id, log_date)
        return int(status.split()[-1]) # Парсим "DELETE 1" в 1

async def get_monthly_net_sum(user_id, month_year):
    p = await get_pool()
    async with p.acquire() as db:
        val = await db.fetchval("SELECT SUM(net) FROM work_logs WHERE user_id=$1 AND month_year=$2", user_id, month_year)
        return float(val) if val else 0.0

async def get_last_geo(user_id):
    p = await get_pool()
    async with p.acquire() as db:
        return await db.fetchrow("SELECT last_location, last_country FROM users WHERE user_id=$1", user_id)

async def get_work_log_id(user_id, log_date):
    p = await get_pool()
    async with p.acquire() as db:
        return await db.fetchrow('SELECT id FROM work_logs WHERE user_id = $1 AND log_date = $2', user_id, log_date)

async def upsert_work_log(user_id, log_date, month_year, day_of_week, status, location, car, route, work_hours, driving_hours, hours_50, hours_100, is_trip_int, bonuses, gross, net, record_id=None):
    p = await get_pool()
    async with p.acquire() as db:
        if record_id:
            await db.execute('''
                UPDATE work_logs
                SET day_of_week=$1, status=$2, location=$3, car=$4, route=$5, work_hours=$6, driving_hours=$7, hours_50=$8, hours_100=$9, is_trip=$10, bonuses=$11, gross=$12, net=$13
                WHERE id=$14
            ''', day_of_week, status, location, car, route, work_hours, driving_hours, hours_50, hours_100, is_trip_int, bonuses, gross, net, record_id)
        else:
            await db.execute('''
                INSERT INTO work_logs (user_id, log_date, month_year, day_of_week, status, location, car, route, work_hours, driving_hours, hours_50, hours_100, is_trip, bonuses, gross, net)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            ''', user_id, log_date, month_year, day_of_week, status, location, car, route, work_hours, driving_hours, hours_50, hours_100, is_trip_int, bonuses, gross, net)

async def get_available_months(user_id):
    p = await get_pool()
    async with p.acquire() as db:
        return await db.fetch('SELECT DISTINCT month_year FROM work_logs WHERE user_id = $1 ORDER BY month_year DESC', user_id)

async def increment_report_count(user_id: int):
    p = await get_pool()
    async with p.acquire() as db:
        await db.execute("UPDATE users SET reports_generated = reports_generated + 1 WHERE user_id = $1", user_id)

async def get_user_subscription_status(user_id: int):
    p = await get_pool()
    async with p.acquire() as db:
        try:
            row = await db.fetchrow("SELECT reports_generated, is_premium FROM users WHERE user_id = $1", user_id)
            if row:
                return row[0] or 0, row[1] or 0
        except Exception:
            pass
    return 0, 0

async def activate_user_premium(user_id: int):
    p = await get_pool()
    async with p.acquire() as db:
        await db.execute("UPDATE users SET is_premium = 1 WHERE user_id = $1", user_id)

async def increment_shift_count(user_id: int) -> int:
    p = await get_pool()
    async with p.acquire() as db:
        await db.execute("UPDATE users SET shifts_added = shifts_added + 1 WHERE user_id = $1", user_id)
        val = await db.fetchval("SELECT shifts_added FROM users WHERE user_id = $1", user_id)
        return val if val else 1
        
async def add_user_savings(user_id: int, amount: float) -> float:
    p = await get_pool()
    async with p.acquire() as db:
        await db.execute("UPDATE users SET current_savings = current_savings + $1 WHERE user_id = $2", amount, user_id)
        val = await db.fetchval("SELECT current_savings FROM users WHERE user_id = $1", user_id)
        return float(val) if val else 0.0
        
async def get_analytics_by_location(user_id, month_year):
    p = await get_pool()
    async with p.acquire() as db:
        return await db.fetch('''
            SELECT 
                location, 
                SUM(work_hours) as total_work, 
                SUM(driving_hours) as total_drive, 
                SUM(net) as total_net
            FROM work_logs
            WHERE user_id = $1 AND month_year = $2 AND location != '' AND status = 'Work'
            GROUP BY location
            ORDER BY total_net DESC
        ''', user_id, month_year)
        
async def get_user_unique_records(user_id: int):
    p = await get_pool()
    async with p.acquire() as db:
        cars = await db.fetch('''
            SELECT car 
            FROM work_logs 
            WHERE user_id = $1 AND car IS NOT NULL AND car != '' 
            GROUP BY car 
            ORDER BY MAX(id) DESC 
            LIMIT 5
        ''', user_id)
        
        locations = await db.fetch('''
            SELECT location 
            FROM work_logs 
            WHERE user_id = $1 AND location IS NOT NULL AND location != '' 
            GROUP BY location 
            ORDER BY MAX(id) DESC 
            LIMIT 10
        ''', user_id)

    return {
        "cars": [row[0] for row in cars], 
        "locations": [row[0] for row in locations]
    }