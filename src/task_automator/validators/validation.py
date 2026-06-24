
import pytimeparse

MIN_DURATION_SECONDS:int = 60

def parse_duration_seconds(value: int | str,
                            *,
                            field_name: str= "duration")-> int:
    if isinstance(value, int):
        seconds = value
        
    elif isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f" {field_name} cannot be empty")
        if cleaned.isdigit():
            seconds = int(cleaned)
        else:
            parsed = pytimeparse.parse(cleaned)
            if parsed is None:
                raise ValueError(f"Invalid {field_name}: {value}")
            seconds = int(parsed)
    
    else:
        raise ValueError(f"{field_name} must be a number or time expression")
    if seconds < MIN_DURATION_SECONDS:
        raise ValueError(f"{field_name} must be at least 1 minute")
    return seconds

def parse_interval(value: int | str)-> int:
    
    seconds = parse_duration_seconds(value, field_name = "interval")
    if seconds > 172800:
        raise ValueError("Interval too large. (max 2 days)")
    return seconds

def format_duration_seconds(seconds: int | None)-> str:

    if seconds is None:
        return "unknown"
    
    if seconds % 86400 == 0:
        label = f"{seconds // 86400}d"
    
    elif seconds % 3600 == 0:
        label = f"{seconds // 3600}h"
    elif seconds % 60 == 0:
        label = f"{seconds // 60}m"
    else:
        label = f"{seconds}s"
    
    return f"{seconds}s ({label})"


