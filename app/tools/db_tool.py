import logging
from datetime import datetime
from app.state import AgentState
from database import (
    get_user_profile,
    get_work_log_id,
    upsert_work_log
)
from nbp_service import get_eur_rate

logger = logging.getLogger(__name__)

async def save_shift_to_db(state: AgentState) -> dict:
    """
    Saves the validated shift data to the PostgreSQL database.
    Calculates gross/net pay, bonuses, work/driving hours, and updates/inserts
    the record using the existing upsert_work_log function.
    
    Returns {"is_confirmed": True} upon successful completion.
    """
    user_id = state.get("user_id")
    parsed_data = state.get("parsed_data") or {}

    # Extract parsed fields
    date_str = parsed_data.get("date")
    status = parsed_data.get("status") or "Work"
    location = parsed_data.get("location") or ""
    
    # Optional fields with default values
    car = parsed_data.get("car") or ""
    route = parsed_data.get("route") or ""
    is_trip = parsed_data.get("is_trip") or False
    is_trip_int = 1 if is_trip else 0
    is_abroad = bool(parsed_data.get("is_abroad") or False)
    is_abroad_int = 1 if is_abroad else 0

    # Parse and format the date
    if not date_str:
        date_str = datetime.today().strftime("%Y-%m-%d")
        
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d.%m.%Y")
    month_year = date_obj.strftime("%m.%Y")
    
    # Fetch user profile to get rates and configurations
    profile = await get_user_profile(user_id)
    
    # Map weekdays for language compatibility (default to Polish)
    days_map = {
        'RUS': ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
        'UKR': ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"],
        'PL': ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
    }
    lang = profile.get("lang") or "PL"
    day_of_week = days_map.get(lang, days_map['PL'])[date_obj.weekday()]

    # If L4 or Urlop, force logged work/driving hours to 0 but calculate standard pay
    if status in ("L4", "Urlop"):
        work_hours = 0.0
        driving_hours = 0.0
        hours_50 = 0.0
        hours_100 = 0.0
        is_trip_int = 0
        
        base_rate = float(profile.get("base_rate") or 32.0)
        tax_coeff = float(profile.get("tax_coeff") or 0.71)
        
        if status == "L4":
            gross = 8.0 * base_rate * 0.8
        else:  # Urlop
            gross = 8.0 * base_rate
            
        net = gross * tax_coeff
        bonuses = 0.0
    else:
        work_hours = float(parsed_data.get("work_hours") or 0.0)
        driving_hours = float(parsed_data.get("driving_hours") or 0.0)
        
        # Calculate normal vs. overtime hours (50% and 100%)
        weekday_num = date_obj.weekday()
        if weekday_num == 5:  # Saturday
            hours_50, hours_100, normal_hours = work_hours, 0.0, 0.0
        elif weekday_num == 6:  # Sunday
            hours_50, hours_100, normal_hours = 0.0, work_hours, 0.0
        else:  # Weekday
            hours_50 = max(0.0, work_hours - 8.0)
            normal_hours = min(8.0, work_hours)
            hours_100 = 0.0

        # Load rates from profile
        base_rate = float(profile.get("base_rate") or 32.0)
        extra_rate = float(profile.get("extra_rate") or 4.0)
        rate_drive = float(profile.get("rate_drive") or 20.0)
        tax_coeff = float(profile.get("tax_coeff") or 0.71)
        diet_value = float(profile.get("diet_value") or 45.0)

        # Apply EUR rate if working abroad
        applied_nbp_rate = await get_eur_rate(date_str) if is_abroad else None
        if is_abroad and applied_nbp_rate:
            rate_eur = float(profile.get("rate_eur") or 0.0)
            rate_drive_eur = float(profile.get("rate_drive_eur") or 0.0)
            if rate_eur > 0:
                extra_rate = rate_eur * applied_nbp_rate
            if rate_drive_eur > 0:
                rate_drive = rate_drive_eur * applied_nbp_rate

        # Calculate gross and net pay
        gross = (
            (normal_hours * base_rate) +
            (hours_50 * base_rate * 1.5) +
            (hours_100 * base_rate * 2.0)
        )
        
        net = (
            (normal_hours * extra_rate) +
            (hours_50 * extra_rate * 1.5) +
            (hours_100 * extra_rate * 2.0) +
            (driving_hours * rate_drive)
        )
        
        if is_trip_int:
            net += diet_value
            
        bonuses = max(0.0, net - (gross * tax_coeff))

    # Retrieve existing record if it exists to perform update instead of insert
    record = await get_work_log_id(user_id, formatted_date)
    record_id = record[0] if record else None

    # Use default car from profile if not provided in parsed_data
    if not car:
        car = profile.get("default_car") or ""

    # Save to Database
    await upsert_work_log(
        user_id=user_id,
        log_date=formatted_date,
        month_year=month_year,
        day_of_week=day_of_week,
        status=status,
        location=location,
        car=car,
        route=route,
        work_hours=work_hours,
        driving_hours=driving_hours,
        hours_50=hours_50,
        hours_100=hours_100,
        is_trip_int=is_trip_int,
        bonuses=bonuses,
        gross=gross,
        net=net,
        is_abroad_int=is_abroad_int,
        record_id=record_id
    )

    return {"is_confirmed": True}
