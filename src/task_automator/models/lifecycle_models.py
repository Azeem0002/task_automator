from dataclasses import dataclass
from pathlib import Path

# Default config/ state

@dataclass(frozen=True)
class AutoclearStatus:
    backend: str
    is_running: bool
    pid: int | None
    interval_secs: int | None
    last_trigger: str | None
    detail: str | None
    pid_file: Path | None = None
    target_tty: str | None = None

@dataclass(frozen= True)
class AutoclearConfig:
    interval: int = 3600 # 1h
    max_retries: int= 3
    retry_delay: float = 1.0