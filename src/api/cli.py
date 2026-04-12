import time

import typer
from env.env import setup_env, setup_logger, get_pid_file_path
from core.controller import status_autoclear, stop_autoclear, start_autoclear, restart_autoclear
from parsers.parse import parse_interval



app = typer.Typer()

@app.callback()
def init():
    log_file = setup_env()
    setup_logger(log_file)

@app.command()
def status():
    result = status_autoclear()
    typer.echo(result)

@app.command()
def stop():
    result = stop_autoclear()
    typer.echo(result)

@app.command()
def start(interval: str= typer.Option("1h", "-i", help="interval e.g 1h, 60s, 60, 2m, 3600")):
    try:
        result = start_autoclear(interval)
    except (ValueError, RuntimeError) as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(code=1)
    
    if result:
        time.sleep(1)
        typer.echo("Autoclear started")

@app.command()
def restart(seconds: str= typer.Option("1h", "-i", help="interval e.g 60m, 30s, 3600")):

    try:
        result = restart_autoclear(seconds)
        if result:
            interval = parse_interval(seconds)
            time.sleep(1)
            typer.echo(f"Restarted autoclear with: {interval}s")
            
        else:
            typer.echo(f"Failed to restart autoclear: {result}")
            raise typer.Exit(code=1)
    except ValueError as e:
        typer.echo(f"Error: {e}")
        typer.Exit(code=1)

    
    
if __name__=="__main__":
    app()