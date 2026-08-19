#! usr/bin/env python3

import os
import time
import sys
import subprocess
from typing import Callable

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
import typer

from ..adapters.runtime_adapter import setup_env, setup_logger
from ..models.lifecycle_models import AutoclearConfig


# Worker-catalog metadata is read with ``ast`` by the controller, so listing
# workers never imports or starts the worker merely to explain it.
WORKER_DESCRIPTION = "Clear the terminal that started it on a repeating interval."
WORKER_ARGUMENT_HINT = "Use the explicit command: task-automator autoclear start --interval 2h"


CLEAR_SEQUENCE = "\033[H\033[2J\033[3J"


def _get_clear_command()-> list[str]:

    command = ["cmd", "/c", "cls"] if os.name == "nt" else ["clear"]
    return command

def _get_target_tty_path() -> str | None:
    """Return the terminal path the detached worker should clear, when one was provided."""
    tty_path = os.getenv("AUTOCLEAR_TTY")
    return tty_path.strip() if tty_path else None


def _write_clear_sequence_to_tty(tty_path: str) -> None:
    """Write a clear-screen sequence directly to the terminal that launched the worker."""
    fd = os.open(tty_path, os.O_WRONLY | os.O_NOCTTY)
    try:
        os.write(fd, CLEAR_SEQUENCE.encode("utf-8"))
    finally:
        os.close(fd)


def _write_clear_sequence_to_stdout() -> None:
    """Write a clear-screen sequence to the foreground terminal."""
    sys.stdout.write(CLEAR_SEQUENCE)
    sys.stdout.flush()


def _execute_command(command: list[str])-> None:
    target_tty = _get_target_tty_path()
    if target_tty and os.name != "nt":
        _write_clear_sequence_to_tty(target_tty)
        return

    if os.name != "nt" and sys.stdout.isatty():
        _write_clear_sequence_to_stdout()
        return

    if os.name != "nt" and not sys.stdout.isatty():
        logger.warning("No terminal attached; autoclear skipped this cycle")
        return

    try:
        subprocess.run(command, timeout=5, check=True)
    
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Clear failed: {command}") from e
    
def _sleep(seconds: int)-> None:
    time.sleep(seconds)


def log_before(retry_state)-> None:
    attempt = retry_state.attempt_number
    logger.info(f"Attempt {attempt} / {retry_state}")

def log_after(retry_state)-> None:

    if retry_state.outcome.failed:
        logger.warning(f"Attempt Failed: {retry_state}")
    else:
        logger.info(f"Attempt Succeeded")


def with_retry(max_attempt: int, delay: float)-> Callable:

    def decorator(func: Callable)-> Callable:
        @retry(
            stop= stop_after_attempt(max_attempt),
            wait= wait_fixed(delay),
            before= log_before,
            after= log_after,
            reraise=True,
        )
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapped
    return decorator



def clear_terminal(config: AutoclearConfig):

    command = _get_clear_command()
    operation = with_retry(config.max_retries, config.retry_delay)(_execute_command)
    operation(command)

def run_autoclear_once(config: AutoclearConfig) -> None:
    """Clear the terminal once and report success unless silent mode is enabled."""
    clear_terminal(config)
    if not os.getenv("AUTOCLEAR_SILENT"):
        logger.success("Terminal cleared")


def run_autoclear(config: AutoclearConfig) -> None:

    while True:
        try:
            run_autoclear_once(config)
        except RuntimeError:
            time.sleep(1)
        _sleep(config.interval)


    
def init() -> None:
    log_file =  setup_env()
    setup_logger(log_file)

app = typer.Typer(help="Run the autoclear worker.")


@app.command()
def main(
    interval: int = typer.Argument(3600, min=1, help="Seconds between terminal clears."),
) -> None:
    """Initialize the worker and run continuously."""
    init()
    if not os.getenv("AUTOCLEAR_SILENT"):
        logger.info(f"Received interval: {interval}s")
    config = AutoclearConfig(interval)
    run_autoclear(config)


if __name__ == "__main__":
    app()
