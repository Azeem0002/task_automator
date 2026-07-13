#!/usr/bin/env python3

import time

import typer

from ..app.application import (
    install_autoclear_service,
    get_autoclear_status,
    start_autoclear,
    restart_autoclear,
    stop_autoclear,
)
from ..models.lifecycle_models import AutoclearStatus
from ..adapters.runtime_adapter import is_dev_env, setup_env, setup_logger
from ..validators.validation import format_duration_seconds


app = typer.Typer(name='autoclear', help="Cross-platform terminal autoclear controller")

@app.callback()
def init()-> None:

    log_file = setup_env()
    setup_logger(log_file)


def _format_autoclear_status(status: AutoclearStatus)-> str:

    state = "running" if status.is_running else "stopped"
    parts = [f"Autoclear status: {state}", f"backend={status.backend}"]

    if status.pid is not None:
        parts.append(f"pid={status.pid}")
    
    if status.interval_secs is not None:
        parts.append(f"interval = {format_duration_seconds(status.interval_secs)}")
    
    if status.last_trigger:
        parts.append(f"last_trigger={status.last_trigger}")
    if status.pid_file is not None and is_dev_env():
        parts.append(f"pid_file= {status.pid_file}")
    
    if status.target_tty is not None and is_dev_env():
        parts.append(f"target_tty= {status.target_tty}")
    
    if status.detail:
        parts.append(f"detail= {status.detail}")
    
    return " | ".join(parts)

# Typer's public API

@ app.command()
def status()-> None:
    typer.echo(_format_autoclear_status(get_autoclear_status()))

@app.command()
def stop():
    typer.echo(stop_autoclear())

@app.command()
def start(interval: str= typer.Option("1h", "--interval", "-i", help="Interval e.g 60, 1m, 1h30m, 2h"),
          system: bool = typer.Option(False, "--system", help="Start system-level service on linux"),
          )-> None:
    try:
        result = start_autoclear(interval, system=system)
    except (ValueError, RuntimeError, OSError) as e:
        typer.echo(f"Error: {str(e)}")
        raise typer.Exit(code=1)
    
    time.sleep(1)
    typer.echo(result)

@app.command()
def restart(interval: str = typer.Option("1h", "--interval", "-i", help= "New interval (e.g. 600, 1m, 1h30m, 2h)"),
            system:bool = typer.Option(False, "--system", help= "restart system-level service on linux"),
            )-> None:

    try:
        result = restart_autoclear(interval, system=system)
    except (ValueError, RuntimeError, OSError) as e:
        typer.echo(f"Error: {str(e)}")
        raise typer.Exit(code=1)
    
    time.sleep(1)
    typer.echo(result)


@app.command("install-service")
def install_service(
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval e.g 60, 1m, 1h30m"),
    system:bool = typer.Option(False, "--system", help="install as system-level service on Linux")

)-> None:
    try:
        message, steps = install_autoclear_service(interval=interval, system=system)
    
    except (ValueError, RuntimeError) as e:
        typer.echo(f"Error: {str(e)}")
        raise typer.Exit(code=1)
    
    typer.echo(message)
    for step in steps:
        typer.echo(step)

def main():
    app()

if __name__ == "__main__":
    main()



# uv run -m  src.task_automator.cli.controller start
# python -m  src.task_automator.cli.controller start