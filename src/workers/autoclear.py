#! usr/bin/env python3

import os
import time
import sys
import subprocess
from typing import Callable

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from ..adapters.runtime_adapter import setup_env, setup_logger
from ..models.lifecycle_models import AutoclearConfig


def _get_clear_command()-> list[str]:

    command = ["cmd", "/c", "cls"] if os.name == "nt" else ["clear"]
    return command

def _execute_command(command: list[str])-> None:
    command = _get_clear_command()
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

    if not operation:
        logger.warning(f"Too many commands")
    
    operation(command)

def run_autoclear(config: AutoclearConfig)-> None:

    while True:
        try:
            clear_terminal(config)
            logger.success(f"Terminal cleared")
        
        except RuntimeError:
            time.sleep(1)
        _sleep(config.interval)


    
def init():
    log_file =  setup_env()
    setup_logger(log_file)

if __name__=="__main__":
    init()
    logger.info(f"Received interval: {sys.argv}")
    try:
        interval = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
        config = AutoclearConfig(interval, max_retries=5)
        run_autoclear(config)
    except ValueError:
        logger.info("Invalid time interval")
        sys.exit(1)