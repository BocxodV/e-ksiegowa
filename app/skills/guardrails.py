import re as _re
from datetime import datetime as _dt


def validate_shift_data(parsed_data: dict) -> list[str]:
    """
    Validates parsed shift data according to business rules.
    Returns a list of error messages. If there are no errors, returns an empty list.
    """
    errors = []

    work_hours = parsed_data.get("work_hours")
    driving_hours = parsed_data.get("driving_hours")
    status = parsed_data.get("status")
    date = parsed_data.get("date")

    work_val = work_hours if work_hours is not None else 0.0
    driving_val = driving_hours if driving_hours is not None else 0.0

    # Rule 1: Negative hours are not allowed (prevents financial fraud)
    if work_val < 0:
        errors.append(f"work_hours cannot be negative (got {work_val}).")
    if driving_val < 0:
        errors.append(f"driving_hours cannot be negative (got {driving_val}).")

    # Rule 2: Sum of work_hours and driving_hours must not exceed 24
    if work_val + driving_val > 24.0:
        errors.append(
            f"The sum of work hours ({work_val}) and driving hours ({driving_val}) "
            f"exceeds the 24-hour daily limit."
        )

    # Rule 3: If status is "L4" or "Urlop", hours must be empty (None) or 0
    if status in ("L4", "Urlop"):
        has_work_hours = work_hours is not None and work_hours > 0
        has_driving_hours = driving_hours is not None and driving_hours > 0
        if has_work_hours or has_driving_hours:
            errors.append(
                f"When status is '{status}', work hours and driving hours "
                f"must be empty or 0 (got work_hours={work_hours}, driving_hours={driving_hours})."
            )

    # Rule 4: Status must be one of 'Work', 'L4', 'Urlop' and not empty
    if not status or status not in ("Work", "L4", "Urlop"):
        errors.append(
            f"Invalid or missing status '{status}'. Status must be 'Work', 'L4', or 'Urlop'."
        )

    # Rule 5: Date must be in YYYY-MM-DD format if provided
    if date:
        try:
            _dt.strptime(str(date), "%Y-%m-%d")
        except ValueError:
            errors.append(f"Invalid date format '{date}'. Expected YYYY-MM-DD.")

    return errors
