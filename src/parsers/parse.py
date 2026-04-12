import pytimeparse

def  parse_interval(value: str)-> int:
    
    if value.isdigit():
        return int(value)
    seconds = pytimeparse.parse(value)
    
    if seconds is None:
        raise ValueError(f"Invalid time format")
    
    if seconds <= 0: 
        raise ValueError(f"value must be > 0: {value}")
    
    if seconds > 172800: # 2days in seconds
        raise ValueError(f"Interval too large. (max 2days)")
    
    return int(seconds)