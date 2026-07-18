#!/usr/bin/env python3
"""CLI boundary for autoclear.

This file translates command-line input/output into calls to the application layer.
Keep real orchestration out of here as much as possible.
"""

import time

import typer

try:
    from ..app.application import (
        format_autoclear_status,
        get_autoclear_status,
        resolve_interval_text,
        install_autoclear_service,
        restart_autoclear,
        start_autoclear,
        stop_autoclear,
    )

    from ..adapters.runtime_adapter import setup_env, setup_logger

except ImportError:
    from application import (
        format_autoclear_status,
        get_autoclear_status,
        resolve_interval_text,
        install_autoclear_service,
        restart_autoclear,
        start_autoclear,
        stop_autoclear,
    )
    # from lifecycle_models import AutoclearStatus
    from runtime_adapter import setup_env, setup_logger
    # from validation import format_duration_seconds


app = typer.Typer(name="autoclear", help="Cross-platform terminal autoclear controller")


# ============================================
# CLI - Thin wrapper around orchestration
# ============================================
# Boundary mental model:
# 1. Typer receives raw terminal strings/options from the user.
# 2. This file does only CLI responsibilities: setup, friendly errors, and printing.
# 3. The application layer parses interval meaning and chooses the runtime backend.
# 4. The adapters do OS work. Keep those side effects out of the CLI.
@app.callback() # runs at app startup
def init() -> None:
    """Initialize the runtime environment for this module."""
    log_file = setup_env()
    setup_logger(log_file)


# Typer's Public API

@app.command()
def status(system: bool = typer.Option(False, "--system", help="Check system-level service on Linux")) -> None:
    """Display the current status to the caller."""
    typer.echo(format_autoclear_status(get_autoclear_status(system=system)))


@app.command()
def stop(system: bool = typer.Option(False, "--system", help="Stop system-level service on Linux")) -> None:
    """Stop the requested runtime path."""
    typer.echo(stop_autoclear(system=system))


@app.command("status-service")
def status_service(system: bool = typer.Option(True, "--system", help="Check system-level service on Linux")) -> None:
    """Display the system-service status explicitly."""
    typer.echo(format_autoclear_status(get_autoclear_status(system=system)))


@app.command("start-service")
def start_service(
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval e.g. 1m, 1h30m, 2h"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
    system: bool = typer.Option(True, "--system", help="Start system-level service on Linux"),
) -> None:
    """Start the native service backend explicitly."""
    try:
        result = start_autoclear(resolve_interval_text(interval, interval_parts or []), system=system)
    except (ValueError, RuntimeError, OSError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(code=1)

    time.sleep(1)
    typer.echo(result)


@app.command("stop-service")
def stop_service(system: bool = typer.Option(True, "--system", help="Stop system-level service on Linux")) -> None:
    """Stop the native service backend explicitly."""
    typer.echo(stop_autoclear(system=system))


@app.command()
def start(
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval e.g. 1m, 1h30m, 2h"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
    system: bool = typer.Option(False, "--system", help="Start system-level service on Linux"),
) -> None:
    """Start the requested runtime path."""
    try:
        # Pass raw user text down to the application. Do not parse it here;
        # parse_interval lives below the boundary so CLI/API can share the rule.
        result = start_autoclear(resolve_interval_text(interval, interval_parts or []), system=system)
    except (ValueError, RuntimeError, OSError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(code=1)

    time.sleep(1)
    typer.echo(result)


@app.command()
def restart(
    interval: str = typer.Option("1h", "--interval", "-i", help="New interval (e.g. 600, 2h 30m)"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
    system: bool = typer.Option(False, "--system", help="Restart system-level service on Linux"),
) -> None:
    """Restart the requested runtime path."""
    try:
        # Restart follows the same boundary rule as start: CLI accepts text,
        # application validates meaning, adapters perform process/service work.
        result = restart_autoclear(resolve_interval_text(interval, interval_parts or []), system=system)
    except (ValueError, RuntimeError, OSError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(code=1)

    time.sleep(1)
    typer.echo(result)


@app.command("install-service")
def install_service(
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval e.g. 1m, 5m, 2h"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
    system: bool = typer.Option(False, "--system", help="Install as system-level service on Linux"),
) -> None:
    """Install or update service."""
    try:
        message, steps = install_autoclear_service(interval=resolve_interval_text(interval, interval_parts or []), system=system)
    except (ValueError, RuntimeError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(code=1)

    typer.echo(message)
    for step in steps:
        typer.echo(step)


def main() -> None:
    """Run the module entrypoint."""
    app()


if __name__ == "__main__":
    main()
