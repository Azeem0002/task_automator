"""Windows Task Scheduler adapter.

This is the canonical import path. The older ``tskscheduler_adapter`` module
remains as a compatibility implementation while installed users migrate.
"""

from .tskscheduler_adapter import (
    get_status_from_task_scheduler,
    install_task_scheduler_service,
    is_task_scheduler_service_installed,
    start_task_scheduler_service,
    stop_task_scheduler_service,
)

__all__ = [
    "get_status_from_task_scheduler",
    "install_task_scheduler_service",
    "is_task_scheduler_service_installed",
    "start_task_scheduler_service",
    "stop_task_scheduler_service",
]
