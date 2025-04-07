"""Eden CLI implementation."""
import asyncio
import json
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .server import EdenServer, ServerConfig

app = typer.Typer()
console = Console()

def load_config(config_path: Path) -> dict:
    """Load configuration from eden.json file."""
    if not config_path.exists():
        console.print(f"[red]Configuration file not found: {config_path}[/red]")
        raise typer.Exit(1)
    
    try:
        with open(config_path) as f:
            return json.load(f)
    except json.JSONDecodeError:
        console.print(f"[red]Invalid JSON in configuration file: {config_path}[/red]")
        raise typer.Exit(1)

@app.command()
def up(
    config_path: Path = typer.Option(
        "eden.json",
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    dev: bool = typer.Option(
        False,
        "--dev",
        "-d",
        help="Run in development mode",
    ),
):
    """Start the Eden server and dashboard."""
    config = load_config(config_path)
    
    # Start the server
    server_config = ServerConfig(
        config_path=config_path,
        dev_mode=dev,
    )
    server = EdenServer(server_config)
    
    # In development mode, start the dashboard dev server
    dashboard_process: Optional[subprocess.Popen] = None
    if dev:
        try:
            dashboard_process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=Path("eden-dash"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            console.print("[green]Started dashboard development server[/green]")
        except Exception as e:
            console.print(f"[red]Failed to start dashboard: {e}[/red]")
            raise typer.Exit(1)
    
    # Start the server
    console.print(Panel.fit(
        "[bold green]Eden Server[/bold green]\n"
        f"Config: {config_path}\n"
        f"Mode: {'Development' if dev else 'Production'}",
    ))
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    finally:
        if dashboard_process:
            dashboard_process.terminate()
            dashboard_process.wait()

@app.command()
def init(
    config_path: Path = typer.Option(
        "eden.json",
        "--config",
        "-c",
        help="Path to configuration file",
    ),
):
    """Initialize a new Eden configuration file."""
    if config_path.exists():
        if not typer.confirm(f"{config_path} already exists. Overwrite?"):
            raise typer.Exit()
    
    default_config = {
        "servers": [],
        "llm_vendors": [],
        "tools": [],
    }
    
    with open(config_path, "w") as f:
        json.dump(default_config, f, indent=2)
    
    console.print(f"[green]Created new configuration file: {config_path}[/green]")

if __name__ == "__main__":
    app() 