# Multi-Agent Design System

A collaborative design assistance system powered by specialized AI agents communicating through a Model Communication Protocol (MCP) server.

## Features

- **Multiple Specialized Agents**:
  - Coordinator Agent: Orchestrates tasks between specialized agents
  - Aesthetic Agent: Provides visual and aesthetic design guidance
  - UX Flow Agent: Creates user experience flows and interaction patterns
  - Accessibility Agent: Ensures designs meet accessibility standards and best practices
  - Persona Agent: Analyzes design from different user persona perspectives

- **Enhanced Infrastructure**:
  - Redis-based shared memory for persistent state management across agents
  - Solana blockchain integration for verifiable agent contributions
  - Robust error handling and monitoring with Prometheus and Grafana
  - Comprehensive test suite with unit and integration tests
  - CI/CD pipelines for automated testing and deployment

## Architecture

```
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│   Frontend UI │◄────►│   MCP Server  │◄────►│  Coordinator  │
└───────────────┘      └───────┬───────┘      └───────┬───────┘
                               │                      │
                               ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│     Redis     │◄────►│  Specialized  │◄────►│    Solana     │
│ Shared Memory │      │    Agents     │      │  Blockchain   │
└───────────────┘      └───────────────┘      └───────────────┘
```

## Prerequisites

- Docker and Docker Compose
- Node.js 16+ (for UI development)
- Python 3.9+ (for agent development)
- Redis (for shared memory, included in Docker Compose)
- Solana CLI tools (optional, for blockchain integration)

## Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/multi-agent-design-system.git
   cd multi-agent-design-system
   ```

2. Create a `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the System

### Using Docker Compose (Recommended)

Start the entire system with a single command:

```bash
docker-compose up
```

This will launch:
- MCP Server (WebSocket server at ws://localhost:8080)
- All specialized agents (coordinator, aesthetic, ux-flow, accessibility, persona)
- Redis for shared memory
- Local Solana test validator (for blockchain integration)
- Frontend UI (available at http://localhost:3000)
- Monitoring stack (Prometheus at http://localhost:9090, Grafana at http://localhost:3001)

### Running Individual Components

To run individual components for development:

1. Start the MCP server:
   ```bash
   cd mcp-server
   zig build run
   ```

2. Start Redis (if not using Docker):
   ```bash
   redis-server
   ```

3. Start individual agents:
   ```bash
   cd agents/coordinator
   python agent.py

   # In separate terminals
   cd agents/aesthetic
   python agent.py

   cd agents/ux-flow
   python agent.py

   cd agents/accessibility
   python agent.py

   cd agents/persona
   python agent.py
   ```

4. Start the frontend UI:
   ```bash
   cd ui
   npm install  # First time only
   npm start
   ```

## Running Tests

Run unit tests:
```bash
pytest tests/unit/
```

Run integration tests:
```bash
pytest tests/integration/
```

Run with coverage:
```bash
coverage run -m pytest tests/
coverage report
```

## Development

### Adding a New Agent

1. Create a new directory under `agents/`:
   ```bash
   mkdir -p agents/new-agent-name
   ```

2. Create an agent implementation based on the template:
   ```bash
   cp agents/shared/templates/agent_template.py agents/new-agent-name/agent.py
   ```

3. Update the agent.py file with your specialized logic

4. Add the new agent to docker-compose.yml

### Project Structure

- `agents/` - All specialized agents
  - `coordinator/` - Task orchestration agent
  - `aesthetic/` - Visual design agent
  - `ux-flow/` - User experience agent
  - `accessibility/` - Accessibility standards agent
  - `persona/` - User persona analysis agent
  - `shared/` - Shared utilities and modules
    - `memory/` - State management modules
- `blockchain/` - Solana smart contracts for agent registry
- `mcp-server/` - Model Communication Protocol server (Zig)
- `monitoring/` - Prometheus and Grafana configurations
- `protocols/` - Communication protocol definitions
- `tests/` - Unit and integration tests
  - `unit/` - Unit tests for individual components
  - `integration/` - Tests for component interactions
- `ui/` - Frontend React application

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit your changes: `git commit -m 'Add new feature'`
4. Push to the branch: `git push origin feature/new-feature`
5. Open a Pull Request

## License

[MIT License](LICENSE)