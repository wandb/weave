# Eden MCP Server

The Python server component of Eden, providing a unified platform for working with MCP servers.

## Features

- FastAPI-based server with WebSocket support
- Configuration management via JSON files
- CLI interface for server control
- Development and production modes

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Usage

### Starting the Server

```bash
eden up --config eden.json --debug
```

### Initializing Configuration

```bash
eden init --config eden.json
```

## Configuration

The server uses a JSON configuration file with the following structure:

```json
{
  "servers": [],
  "tools": [],
  "resources": [],
  "prompts": [],
  "sampling": {}
}
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
isort .
```

### Type Checking

```bash
mypy .
```

## Environment Variables

- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: 8000)
- `DEBUG`: Enable debug mode (default: False)

## License

MIT 