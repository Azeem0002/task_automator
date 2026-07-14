#!/usr/bin/env python3

import time

import typer

from ..app.application import (
    install_autoclear_service,
    get_autoclear_status,
    format_autoclear_status,
    resolve_interval_text,
    start_autoclear,
    restart_autoclear,
    stop_autoclear,
)

from ..adapters.runtime_adapter import setup_env, setup_logger


app = typer.Typer(name='autoclear', help="Cross-platform terminal autoclear controller")

@app.callback()
def init()-> None:

    log_file = setup_env()
    setup_logger(log_file)



# Typer's public API

@ app.command()
def status()-> None:
    typer.echo(format_autoclear_status(get_autoclear_status()))

@app.command()
def stop():
    typer.echo(stop_autoclear())

@app.command()
def start(interval: str= typer.Option("1h", "--interval", "-i", help="Interval e.g 60, 1m, 1h30m, 2h"),
          interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
          system: bool = typer.Option(False, "--system", help="Start system-level service on linux"),
          )-> None:
    try:
        result = start_autoclear(resolve_interval_text(interval, interval_parts or []), system=system)
    except (ValueError, RuntimeError, OSError) as e:
        typer.echo(f"Error: {str(e)}")
        raise typer.Exit(code=1)
    
    time.sleep(1)
    typer.echo(result)

@app.command()
def restart(interval: str = typer.Option("1h", "--interval", "-i", help= "New interval (e.g. 600, 1m, 1h30m, 2h)"),
            interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
            system:bool = typer.Option(False, "--system", help= "restart system-level service on linux"),
            )-> None:

    try:
        result = restart_autoclear(resolve_interval_text(interval, interval_parts), system=system)
    except (ValueError, RuntimeError, OSError) as e:
        typer.echo(f"Error: {str(e)}")
        raise typer.Exit(code=1)
    
    time.sleep(1)
    typer.echo(result)


@app.command("install-service")
def install_service(
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval e.g 60, 1m, 1h30m"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
    system:bool = typer.Option(False, "--system", help="install as system-level service on Linux")

)-> None:
    try:
        message, steps = install_autoclear_service(interval= resolve_interval_text(interval, interval_parts or []), system=system)
    
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