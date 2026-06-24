from ..models.lifecycle_models import AutoclearStatus

SYSTEMD_SERVICE_NAME = "autoclear.service"


def install_service(*, interval_secs: int | None, system:bool= False)-> tuple[str, list[str]]:
    ...

def is_service_installed(system:bool= False):
    ...

def start_service(interval_secs: int | None= None, system:bool=False)-> str:
    ...

def stop_service(*, system:bool= False)-> str:
    ...

def get_status_from_systemd(system:bool= False)-> AutoclearStatus:
    ...