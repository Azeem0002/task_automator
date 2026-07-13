import os
import sys

def _detect_platform()-> str:

    if os.name == "nt":
        return "windows"
    
    if sys.platform.startswith("linux"):
        return "linux"

    if sys.platform == ("darwin"):
        return "mac"
    
    return "unknown platform"
    
def detect_platform()-> str:
    return _detect_platform()