#!/usr/bin/env python3
"""CLI boundary for autoclear.

This file translates command-line input/output into calls to the application layer.
Keep real orchestration out of here as much as possible.
"""

import shlex
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
    from ..adapters.service_adapter import (
        start_service as start_native_service,
        stop_service as stop_native_service,
    )

    from ..adapters.runtime_adapter import setup_env, setup_logger
    from ..adapters.worker_catalog_adapter import discover_worker_names, run_discovered_worker, spawn_discovered_worker, worker_details

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
    from adapters.service_adapter import (
        start_service as start_native_service,
        stop_service as stop_native_service,
    )
    # from lifecycle_models import AutoclearStatus
    from runtime_adapter import setup_env, setup_logger
    from worker_catalog_adapter import discover_worker_names, run_discovered_worker, spawn_discovered_worker, worker_details
    # from validation import format_duration_seconds


app = typer.Typer(name="task-automator", help="Cross-platform local worker automation controller")
workers_app = typer.Typer(help="Discover and run worker files from the workers directory.")
autoclear_app = typer.Typer(help="Manage the terminal-bound autoclear worker.")
app.add_typer(workers_app, name="workers")
app.add_typer(autoclear_app, name="autoclear")


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

@workers_app.command("list")
def list_workers() -> None:
    """List runnable ``workers/*.py`` modules; no central registration required."""
    workers = discover_worker_names()
    if not workers:
        typer.echo("No workers found. Add a runnable .py file to the workers directory.")
        return
    typer.echo("Available workers:")
    for index, worker_name in enumerate(workers, start=1):
        purpose, hint = worker_details(worker_name)
        typer.echo(f"  {index}. {worker_name} — {purpose}\n     {hint}")
    typer.echo("Use `task-automator interactive` for guided execution.")


@workers_app.command(
    "run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_worker_command(
    ctx: typer.Context,
    worker_name: str | None = typer.Argument(None, help="Worker filename without .py"),
    arguments: list[str] = typer.Argument(None, help="Arguments passed to the selected worker"),
) -> None:
    """Interactively select and run a worker, or run one by filename."""
    workers = discover_worker_names()
    if not workers:
        raise typer.BadParameter("No workers found. Add a runnable .py file to the workers directory.")

    if worker_name is None:
        typer.echo("Available workers:")
        for index, name in enumerate(workers, start=1):
            typer.echo(f"  {index}. {name}")
        selected = typer.prompt("Worker name").strip()
    else:
        selected = worker_name

    worker_arguments = [*(arguments or []), *ctx.args]
    if worker_name is None and not worker_arguments:
        raw_arguments = typer.prompt("Worker arguments (blank for none)", default="")
        try:
            worker_arguments = shlex.split(raw_arguments)
        except ValueError as error:
            raise typer.BadParameter(f"Invalid worker arguments: {error}") from error

    if selected == "autoclear":
        typer.echo("Autoclear is terminal-bound. Use `task-automator autoclear start -i 60m` instead of `workers run autoclear`.", err=True)
        raise typer.Exit(code=2)

    try:
        exit_code = run_discovered_worker(selected, worker_arguments)
    except ValueError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2)
    if exit_code:
        raise typer.Exit(code=exit_code)

def status(system: bool = typer.Option(False, "--system", help="Check system-level service on Linux")) -> None:
    """Display the current status to the caller."""
    typer.echo(format_autoclear_status(get_autoclear_status(system=system)))


def stop(system: bool = typer.Option(False, "--system", help="Stop system-level service on Linux")) -> None:
    """Stop the requested runtime path."""
    typer.echo(stop_autoclear(system=system))


@app.command("start-service")
def start_service(system: bool = typer.Option(False, "--system", help="Start system-level service on Linux")) -> None:
    """Start the persistent native service backend."""
    try:
        result = start_native_service(system=system)
    except (ValueError, RuntimeError, OSError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(code=1)

    time.sleep(1)
    typer.echo(result)
    typer.echo("Hint: use `autoclear start` for a terminal-scoped session. `start-service` is for persistent background jobs and crash recovery, including terminal-free workers.")


@app.command("stop-service")
def stop_service(system: bool = typer.Option(False, "--system", help="Stop system-level service on Linux")) -> None:
    """Stop the native service backend explicitly."""
    typer.echo(stop_native_service(system=system))


def _start_autoclear_from_text(
    interval: str,
    interval_parts: list[str] | None = None,
    system: bool = False,
) -> None:
    """Run the plain-Python autoclear action after CLI input has been decoded.

    Interactive mode can call this safely because it has ordinary Python
    defaults, unlike a Typer command function whose defaults are OptionInfo
    and ArgumentInfo objects before Typer invokes it.
    """
    try:
        result = start_autoclear(resolve_interval_text(interval, interval_parts or []), system=system)
    except (ValueError, RuntimeError, OSError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(code=1)

    time.sleep(1)
    typer.echo(result)
    typer.echo("Hint: run `task-automator autoclear start` when you want a terminal-scoped session. `start-service` is for persistent background jobs and restart-only workflows.")


def start(
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval e.g. 1m, 1h30m, 2h"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
    system: bool = typer.Option(False, "--system", help="Start system-level service on Linux"),
) -> None:
    """Start the requested runtime path."""
    _start_autoclear_from_text(interval, interval_parts, system)


@autoclear_app.command("start")
def autoclear_start(
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval e.g. 1m, 1h30m, 2h"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
    system: bool = typer.Option(False, "--system", help="Start system-level service on Linux"),
) -> None:
    """Start autoclear through its explicit worker command group."""
    start(interval=interval, interval_parts=interval_parts, system=system)


@autoclear_app.command("status")
def autoclear_status(system: bool = typer.Option(False, "--system", help="Check system-level service on Linux")) -> None:
    """Show autoclear status through its explicit worker command group."""
    status(system=system)


@autoclear_app.command("stop")
def autoclear_stop(system: bool = typer.Option(False, "--system", help="Stop system-level service on Linux")) -> None:
    """Stop autoclear through its explicit worker command group."""
    stop(system=system)


@autoclear_app.command("restart")
def autoclear_restart(
    interval: str = typer.Option("1h", "--interval", "-i", help="New interval e.g. 1m, 1h30m, 2h"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
    system: bool = typer.Option(False, "--system", help="Restart system-level service on Linux"),
) -> None:
    """Restart autoclear through its explicit worker command group."""
    restart(interval=interval, interval_parts=interval_parts, system=system)


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
    typer.echo("Hint: run `autoclear start` in the terminal you want cleared. `start-service` is for persistence and restart only.")


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


@app.command()
def interactive() -> None:
    """Guide a user through autoclear controls and discovered foreground workers."""
    while True:
        typer.echo("\nTask Automator\n1. Run a foreground worker\n2. Run a background worker\n3. List workers\n4. Exit")
        choice = typer.prompt("Choose an action", default="1").strip()
        if choice == "1":
            names = [name for name in discover_worker_names() if name != "autoclear"]
            typer.echo(f"Foreground workers: {', '.join(names) or 'none'}")
            selected = typer.prompt("Worker name").strip()
            try:
                _, hint = worker_details(selected)
            except ValueError:
                hint = "Use `-- --help` to view this worker's options."
            typer.echo(f"Argument hint: {hint}")
            try:
                exit_code = run_discovered_worker(selected, shlex.split(typer.prompt("Worker arguments", default="")))
            except (ValueError, OSError) as error:
                typer.echo(f"Error: {error}", err=True)
                continue
            if exit_code:
                typer.echo(f"Worker exited with code {exit_code}", err=True)
        elif choice == "2":
            names = discover_worker_names()
            typer.echo(f"Background workers: {', '.join(names) or 'none'}")
            selected = typer.prompt("Worker name").strip()
            if selected == "autoclear":
                typer.echo("Autoclear controls: 1. Start  2. Status  3. Stop")
                autoclear_choice = typer.prompt("Choose an autoclear action", default="1").strip()
                if autoclear_choice == "1":
                    _start_autoclear_from_text(
                        typer.prompt("Clear interval value (e.g. 60m or 2h; do not type --interval)", default="1h")
                    )
                    # Autoclear clears this terminal immediately. Ending the
                    # guided UI prevents this loop from instantly repainting
                    # a menu over that first clear.
                    return
                elif autoclear_choice == "2":
                    status()
                elif autoclear_choice == "3":
                    stop()
                else:
                    typer.echo("Choose 1, 2, or 3.", err=True)
                continue
            try:
                _, hint = worker_details(selected)
            except ValueError:
                hint = "Use `-- --help` to view this worker's options."
            typer.echo(f"Argument hint: {hint}")
            try:
                pid, log_path = spawn_discovered_worker(selected, shlex.split(typer.prompt("Worker arguments", default="")))
            except (ValueError, OSError) as error:
                typer.echo(f"Error: {error}", err=True)
                continue
            typer.echo(f"Started {selected} in background (PID {pid}). Log: {log_path}")
        elif choice == "3":
            list_workers()
        elif choice == "4":
            return
        else:
            typer.echo("Choose a number from 1 to 4.", err=True)


def main() -> None:
    """Run the module entrypoint."""
    app()


if __name__ == "__main__":
    main()
