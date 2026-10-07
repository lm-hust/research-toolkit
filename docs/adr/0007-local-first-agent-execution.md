# 7. Local-First Agent Execution; Remote Gateway Frozen

Agents run the toolkit through the CLI in local agent tools (Claude Code, Antigravity CLI). The DualStackGateway from ADR-0006 is frozen at its current feature set and is not deployed.

## Context
ADR-0006 added an MCP/REST gateway so that the claude.ai and ChatGPT web apps could drive the toolkit through connectors. Bringing the `lit-scout` skill to claude.ai would have meant building a second execution surface:
- MCP tools that mirror every CLI capability, including `expand`, the sort/filter flags, dry-run, and a discover → preview → confirm-code → ingest flow to replace the terminal CurationCheckpoint.
- A server-side candidate batch store, plus continuous deployment, TLS, auth, and uptime upkeep.

The two surfaces were already drifting apart: MCP `search_literature` had no filters and wrote to Zotero on every call. The earlier Cyber9 retrieval and ingestion connectors decayed once their backends were removed. Research workflows also depend on things web connectors cannot provide: running the CLI directly, a filesystem for ledgers, PDFs and the Obsidian vault, and agent-driven iteration on errors.

## Decision
1. **The CLI is the single execution surface.** Skills (e.g. `lit-scout`) invoke `research_toolkit.cli` commands. No capability is added to MCP to reach parity with the CLI.
2. **The gateway is frozen, not removed.** `src/research_toolkit/mcp/` stays as of #29 (Streamable HTTP at `/mcp/http`, token gate) but is not deployed. The do-vps deployment was torn down on 2026-10-08.
3. **Remote use goes through a remote agent, not connectors.** When access away from the workstation is needed, run a local-style agent (e.g. Claude Code) on a host that has the repo and `.env`, and connect to that agent remotely.
4. **CloudStorageResolver is independent of the gateway.** Zotero Cloud Storage PDF resolution (ADR-0006 §3) remains part of the core for headless hosts.

## Consequences
- One code path per capability; skills and CLI evolve together under the existing Skill & Agent Capability Synchronization standard.
- claude.ai and ChatGPT web apps cannot use the toolkit directly.
- If the gateway is permanently abandoned, delete `src/research_toolkit/mcp/`, the `serve` command, the Caddy service and `Caddyfile` together, keeping CloudStorageResolver.
