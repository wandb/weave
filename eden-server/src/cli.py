import json
import os
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer()
console = Console()

def load_config(config_path: str = "eden.json") -> dict:
    """Load configuration from eden.json file."""
    if not os.path.exists(config_path):
        return {
            "servers": [],
            "tools": [],
            "llm_vendors": [],
        }
    
    with open(config_path, "r") as f:
        return json.load(f)

def save_config(config: dict, config_path: str = "eden.json") -> None:
    """Save configuration to eden.json file."""
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

@app.command()
def up(
    config_path: str = typer.Option("eden.json", help="Path to configuration file"),
    port: int = typer.Option(8000, help="Port to run the server on"),
):
    """Start the Eden server."""
    config = load_config(config_path)
    
    console.print(Panel.fit(
        "[bold green]Eden Server[/bold green]\n"
        f"Configuration: {config_path}\n"
        f"Port: {port}",
        title="Starting Server",
    ))
    
    # Import and run the server
    from server import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)

@app.command()
def config(
    action: str = typer.Argument(..., help="Action to perform (show/edit)"),
    config_path: str = typer.Option("eden.json", help="Path to configuration file"),
):
    """Manage Eden configuration."""
    if action == "show":
        config = load_config(config_path)
        console.print(json.dumps(config, indent=2))
    elif action == "edit":
        config = load_config(config_path)
        # TODO: Implement interactive configuration editing
        console.print("Interactive configuration editing not implemented yet.")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")

@app.command()
def server(
    action: str = typer.Argument(..., help="Action to perform (add/remove/list)"),
    name: Optional[str] = typer.Option(None, help="Server name"),
    url: Optional[str] = typer.Option(None, help="Server URL"),
    config_path: str = typer.Option("eden.json", help="Path to configuration file"),
):
    """Manage MCP servers."""
    config = load_config(config_path)
    
    if action == "add":
        if not name or not url:
            console.print("[red]Name and URL are required for adding a server[/red]")
            return
        
        config["servers"].append({
            "name": name,
            "url": url,
            "enabled": True,
        })
        save_config(config, config_path)
        console.print(f"[green]Added server: {name}[/green]")
    
    elif action == "remove":
        if not name:
            console.print("[red]Name is required for removing a server[/red]")
            return
        
        config["servers"] = [s for s in config["servers"] if s["name"] != name]
        save_config(config, config_path)
        console.print(f"[green]Removed server: {name}[/green]")
    
    elif action == "list":
        for server in config["servers"]:
            status = "[green]enabled[/green]" if server["enabled"] else "[red]disabled[/red]"
            console.print(f"{server['name']} ({server['url']}) - {status}")
    
    else:
        console.print(f"[red]Unknown action: {action}[/red]")

if __name__ == "__main__":
    app() 