#!/usr/bin/env python3
"""CLI boundary for autoclear.

This file translates command-line input/output into calls to the application layer.
Keep real orchestration out of here as much as possible.
"""

import shlex
import time

import psutil
import typer

try:
    from ..app.application import (
        format_autoclear_status,
        get_autoclear_status,
        resolve_interval_text,
        restart_autoclear,
        start_autoclear,
        stop_autoclear,
    )
    from ..adapters.runtime_adapter import setup_env, setup_logger
    from ..adapters.worker_catalog_adapter import (
        discover_background_worker_names, discover_worker_names, get_background_worker_status, run_discovered_worker,
        spawn_discovered_worker, stop_background_worker, worker_details,
    )

except ImportError:
    from application import (
        format_autoclear_status,
        get_autoclear_status,
        resolve_interval_text,
        restart_autoclear,
        start_autoclear,
        stop_autoclear,
    )
    # from lifecycle_models import AutoclearStatus
    from runtime_adapter import setup_env, setup_logger
    from worker_catalog_adapter import (
        discover_background_worker_names, discover_worker_names, get_background_worker_status, run_discovered_worker,
        spawn_discovered_worker, stop_background_worker, worker_details,
    )
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


@workers_app.command("start", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def start_worker_command(
    ctx: typer.Context,
    worker_name: str = typer.Argument(..., help="Worker filename without .py"),
    arguments: list[str] = typer.Argument(None, help="Arguments passed to the selected worker"),
) -> None:
    """Start a terminal-independent worker in the background with lifecycle tracking."""
    if worker_name == "autoclear":
        raise typer.BadParameter("Use `task-automator autoclear start` for terminal-bound autoclear.")
    try:
        pid, log_path = spawn_discovered_worker(worker_name, [*(arguments or []), *ctx.args])
    except (ValueError, RuntimeError, OSError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2)
    typer.echo(f"Started {worker_name} in background (PID {pid}). Log: {log_path}")


@workers_app.command("status")
def worker_status_command(worker_name: str = typer.Argument(..., help="Worker filename without .py")) -> None:
    """Show the running state and log path for a managed background worker."""
    try:
        status_value = get_background_worker_status(worker_name)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    state = "running" if status_value.is_running else "stopped"
    typer.echo(f"{worker_name}: {state} | pid={status_value.pid or 'none'} | log={status_value.log_path}")


@workers_app.command("stop")
def stop_worker_command(worker_name: str = typer.Argument(..., help="Worker filename without .py")) -> None:
    """Stop one controller-managed background worker."""
    try:
        status_value = stop_background_worker(worker_name)
    except (ValueError, OSError, psutil.Error) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2)
    typer.echo(f"Stopped {worker_name}. Log: {status_value.log_path}")


@workers_app.command("logs")
def worker_logs_command(worker_name: str = typer.Argument(..., help="Worker filename without .py")) -> None:
    """Print the durable log path for a managed background worker."""
    try:
        typer.echo(get_background_worker_status(worker_name).log_path)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

def status() -> None:
    """Display the current status to the caller."""
    typer.echo(format_autoclear_status(get_autoclear_status()))


def stop() -> None:
    """Stop the requested runtime path."""
    typer.echo(stop_autoclear())


def _start_autoclear_from_text(
    interval: str,
    interval_parts: list[str] | None = None,
) -> None:
    """Run the plain-Python autoclear action after CLI input has been decoded.

    Interactive mode can call this safely because it has ordinary Python
    defaults, unlike a Typer command function whose defaults are OptionInfo
    and ArgumentInfo objects before Typer invokes it.
    """
    try:
        result = start_autoclear(resolve_interval_text(interval, interval_parts or []))
    except (ValueError, RuntimeError, OSError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(code=1)

    time.sleep(1)
    typer.echo(result)
    typer.echo("Autoclear is session-scoped: it only manages the terminal that started it.")


def start(
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval e.g. 1m, 1h30m, 2h"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
) -> None:
    """Start the requested runtime path."""
    _start_autoclear_from_text(interval, interval_parts)


@autoclear_app.command("start")
def autoclear_start(
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval e.g. 1m, 1h30m, 2h"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
) -> None:
    """Start autoclear through its explicit worker command group."""
    start(interval=interval, interval_parts=interval_parts)


@autoclear_app.command("status")
def autoclear_status() -> None:
    """Show autoclear status through its explicit worker command group."""
    status()


@autoclear_app.command("stop")
def autoclear_stop() -> None:
    """Stop autoclear through its explicit worker command group."""
    stop()


@autoclear_app.command("restart")
def autoclear_restart(
    interval: str = typer.Option("1h", "--interval", "-i", help="New interval e.g. 1m, 1h30m, 2h"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
) -> None:
    """Restart autoclear through its explicit worker command group."""
    restart(interval=interval, interval_parts=interval_parts)


@app.command()
def restart(
    interval: str = typer.Option("1h", "--interval", "-i", help="New interval (e.g. 600, 2h 30m)"),
    interval_parts: list[str] = typer.Argument(None, help="Optional interval words, e.g. 1h30m or 1h 30m"),
) -> None:
    """Restart the requested runtime path."""
    try:
        # Restart follows the same boundary rule as start: CLI accepts text,
        # application validates meaning, adapters perform process/service work.
        result = restart_autoclear(resolve_interval_text(interval, interval_parts or []))
    except (ValueError, RuntimeError, OSError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(code=1)

    time.sleep(1)
    typer.echo(result)
    typer.echo("Autoclear restart stays attached to the current terminal session.")


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
            names = ["autoclear", *discover_background_worker_names()]
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
