# Eden Dashboard

The React dashboard component of Eden, providing a user interface for managing MCP servers.

## Features

- Real-time server status monitoring
- Configuration management
- Interactive playground for MCP requests
- Approval request handling
- Modern, responsive UI with Material-UI

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   npm install
   ```

## Development

### Starting the Development Server

```bash
npm start
```

The app will be available at [http://localhost:3000](http://localhost:3000).

### Building for Production

```bash
npm run build
```

### Running Tests

```bash
npm test
```

## Environment Variables

- `REACT_APP_API_URL`: Backend API URL (default: http://localhost:8000/api)
- `REACT_APP_WS_URL`: WebSocket URL (default: ws://localhost:8000/ws)

## Project Structure

- `src/components/`: React components
  - `Layout.tsx`: Main layout with navigation
  - `Dashboard.tsx`: Server status overview
  - `Config.tsx`: Configuration management
  - `Playground.tsx`: MCP request testing
  - `Approver.tsx`: Approval request handling

## License

MIT 