from dataclasses import dataclass

@dataclass
class AutoclearConfig:
    interval: int = 3600
    max_retries: int= 3
    retry_delay: float= 1.0