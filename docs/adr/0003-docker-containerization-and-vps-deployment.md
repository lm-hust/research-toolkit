# 3. Docker Containerization and Headless VPS Deployment

We package the research toolkit into a containerized runtime supporting both local execution and headless VPS deployment.

## Context
Researchers frequently operate across multiple computing environments: a local laptop running Zotero Desktop and Chrome browser, and remote VPS servers with high-speed internet and long-running daemons. The toolkit relies on Python 3.11+, asynchronous networking, session tokens, and optional browser engines. Installing these dependencies natively on remote servers introduces environment divergence and secret leakage risks.

## Decision
1. **Container Specification**: Provide a minimal `Dockerfile` based on `python:3.11-slim`, bundling dependencies defined in `pyproject.toml` / `requirements.txt`.
2. **Persistence & Secrets**:
   - Secrets are loaded strictly via `.env` / environment variables (`.env.example` template provided).
   - Local state, cached PDFs, and session stores live in persistent Docker volumes (`/app/data` and `toolkit-cache`).
   - Host Obsidian Vault is mounted optionally via bind-mount (`/app/vault`).
3. **Dual Execution Pattern**:
   - **Local CLI**: Runs natively or via Docker for rapid desktop interaction.
   - **Headless VPS**: Deployed via `docker-compose.yml`, enabling scheduled literature discovery and remote NotebookLM gateway calls.

## Consequences
- Eliminates dependency conflicts on VPS environments.
- Protects credentials by isolating API keys inside container environment files.
- Lays the foundation for future daemonized MCP servers or REST API gateways.
