import typer
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint
import os
from pathlib import Path
import json
from typing import Optional
from .server import start_server

app = typer.Typer(help="Eden MCP Server CLI")
console = Console()

def load_config(config_path: str) -> dict:
    """Load configuration from a JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[red]Error: Configuration file not found at {config_path}[/red]")
        raise typer.Exit(1)
    except json.JSONDecodeError:
        console.print(f"[red]Error: Invalid JSON in configuration file {config_path}[/red]")
        raise typer.Exit(1)

@app.command()
def up(
    config: str = typer.Option(
        "eden.json",
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug mode",
    ),
):
    """Start the Eden MCP server"""
    # Load configuration
    config_data = load_config(config)
    
    # Set environment variables
    os.environ["DEBUG"] = str(debug).lower()
    
    # Display startup message
    console.print(Panel.fit(
        "[bold green]Eden MCP Server[/bold green]\n"
        f"Configuration: {config}\n"
        f"Debug Mode: {debug}",
        title="Starting Server",
        border_style="green"
    ))
    
    # Start the server
    start_server()

@app.command()
def init(
    config: str = typer.Option(
        "eden.json",
        "--config",
        "-c",
        help="Path to configuration file",
    ),
):
    """Initialize a new Eden configuration file"""
    if os.path.exists(config):
        if not typer.confirm(f"Configuration file {config} already exists. Overwrite?"):
            raise typer.Exit()
    
    default_config = {
        "servers": [],
        "tools": [],
        "resources": [],
        "prompts": [],
        "sampling": {}
    }
    
    with open(config, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    console.print(f"[green]Created new configuration file at {config}[/green]")

if __name__ == "__main__":
    app() 