"""
src/research_toolkit/cli.py
Main command-line interface for the Research Toolkit.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from research_toolkit.discovery.curation import CurationCheckpoint
from research_toolkit.discovery.query import QueryTranslator
from research_toolkit.discovery.service import DiscoveryService
from research_toolkit.notebook import skim as notebook_skim
from research_toolkit.notebook import sync as notebook_sync
from research_toolkit.zotero.manager import ZoteroManager

logger = logging.getLogger(__name__)

STATE_FILE = Path.home() / ".cache" / "research-toolkit" / "session.json"


def load_env_file(path: Optional[Path] = None) -> None:
    """Loads environment variables from .env file into os.environ if present."""
    import os

    env_file = path or (Path.cwd() / ".env")
    if not env_file.is_file():
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        if not env_file.is_file():
            return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if len(v) >= 2 and ((v[0] == "'" and v[-1] == "'") or (v[0] == '"' and v[-1] == '"')):
                v = v[1:-1]
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception as e:
        logger.debug("Failed to auto-load .env: %s", e)


load_env_file()



def load_session() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_session(data: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Could not persist session state: %s", e)


@click.group()
def cli() -> None:
    """Research Toolkit - literature discovery, Zotero sync, and synthesis."""
    pass


def parse_year_range(year_str: Optional[str]) -> Optional[tuple[int, int]]:
    """Parses year filter strings like '2020-2025', '2023+', or '2024' into (min_year, max_year)."""
    if not year_str:
        return None
    val = year_str.strip()
    try:
        if "-" in val:
            parts = val.split("-", 1)
            return (int(parts[0].strip()), int(parts[1].strip()))
        elif val.endswith("+"):
            return (int(val[:-1].strip()), 9999)
        else:
            y = int(val)
            return (y, y)
    except ValueError:
        logger.warning("Invalid year filter format: '%s'. Expected YYYY, YYYY-YYYY, or YYYY+.", year_str)
        return None


@cli.command()
@click.argument("query")
@click.option(
    "--topic",
    "-t",
    "-c",
    "--collection",
    default=None,
    help="Name of target Zotero collection (default: auto slugified from query).",
)
@click.option(
    "--limit",
    "-k",
    default=8,
    type=int,
    help="Number of top papers to discover and rank (default: 8).",
)
@click.option(
    "--detail",
    "-d",
    is_flag=True,
    default=False,
    help="Display detailed table of retrieved paper candidates (default: True).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Output collection info and results as structured JSON.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Perform discovery and ranking dry-run without writing to Zotero.",
)
@click.option(
    "--sort",
    "-s",
    type=click.Choice(["composite", "citations", "recent", "topological"], case_sensitive=False),
    default="composite",
    help="Ranking order: composite (balanced), citations (most cited), recent (newest), topological (most co-cited).",
)
@click.option(
    "--min-cites",
    default=0,
    type=int,
    help="Minimum citation count threshold.",
)
@click.option(
    "--year",
    "-y",
    default=None,
    help="Publication year filter (e.g., 2020-2025, 2023+, or 2024).",
)
@click.option(
    "--peer-reviewed",
    is_flag=True,
    default=False,
    help="Filter out unreviewed preprints (e.g. arXiv).",
)
@click.option(
    "--snowball/--no-snowball",
    default=True,
    help="Enable 1-hop bidirectional citation snowballing (default: True).",
)
@click.option(
    "--interactive/--non-interactive",
    "-i/-I",
    "interactive",
    default=None,
    help="Interactive CurationCheckpoint multi-selection (default: auto).",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Accept all candidates without prompting (alias for --non-interactive).",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress table output in terminal.",
)
def search(
    query: str,
    topic: Optional[str],
    limit: int,
    detail: bool,
    as_json: bool,
    dry_run: bool,
    sort: str,
    min_cites: int,
    year: Optional[str],
    peer_reviewed: bool,
    snowball: bool,
    interactive: Optional[bool],
    yes: bool,
    quiet: bool,
) -> None:
    """Search literature and rank candidates across Semantic Scholar and OpenAlex."""
    if not as_json and not quiet:
        click.echo(f"Searching literature for: '{query}'...")

    y_range = parse_year_range(year)
    service = DiscoveryService()
    candidates = service.search_and_rank(
        query,
        top_k=limit,
        sort_by=sort,
        min_cites=min_cites,
        year_range=y_range,
        peer_reviewed_only=peer_reviewed,
        snowball=snowball,
    )

    if not candidates:
        if as_json:
            click.echo(json.dumps({"status": "no_results", "query": query, "count": 0}))
        else:
            click.echo("No matching papers found.")
        return

    # Derive canonical ZoteroCollection name
    col_name = QueryTranslator.to_collection_name(query, topic)

    # Interactive CurationCheckpoint
    is_interactive = (
        False
        if (yes or interactive is False)
        else (
            True
            if interactive is True
            else (sys.stdin.isatty() and not dry_run and not as_json and not quiet)
        )
    )
    if not as_json and not quiet:
        if is_interactive:
            checkpoint = CurationCheckpoint()
            candidates = checkpoint.review(candidates, interactive=True)
            if not candidates:
                click.echo("CurationCheckpoint aborted. No papers were committed.")
                return
        else:
            table_output = service.format_table(candidates)
            click.echo(table_output)

    if dry_run:
        if as_json:
            payload = {
                "dry_run": True,
                "collection_name": col_name,
                "query": query,
                "count": len(candidates),
            }
            if detail:
                payload["candidates"] = [
                    {
                        "paper_id": c.paper_id,
                        "title": c.title,
                        "year": c.year,
                        "venue": c.venue,
                        "doi": c.doi,
                        "composite_score": c.composite_score,
                    }
                    for c in candidates
                ]
            click.echo(json.dumps(payload, indent=2))
        else:
            click.echo(
                f"\n[dry-run] Discovered and ranked {len(candidates)} papers. No changes committed."
            )
        return

    # Mandatory Zotero insertion
    try:
        zotero_mgr = ZoteroManager()
        collection, created = zotero_mgr.sync_to_collection(col_name, candidates)
    except ValueError as e:
        if as_json:
            click.echo(
                json.dumps({"status": "error", "error_type": "auth_missing", "message": str(e)}),
                err=True,
            )
        else:
            click.echo(f"\n⚠️  Zotero 配置错误: {e}", err=True)
            click.echo("💡 提示: 若需本地预览文献检索与排序，可使用 `--dry-run`；若需入库，请在 .env 中配置 ZOTERO_USER_ID 与 ZOTERO_API_KEY。", err=True)
        sys.exit(1)

    save_session(
        {
            "active_collection": col_name,
            "topic": query,
            "collection_key": collection.key,
            "collection_url": collection.web_url,
        }
    )

    if as_json:
        payload = {
            "collection_id": collection.key,
            "collection_url": collection.web_url,
            "collection_name": col_name,
            "count": len(created),
            "created_count": getattr(created, "created_count", len(created)),
            "reused_count": getattr(created, "reused_count", 0),
        }
        if detail:
            payload["candidates"] = [
                {
                    "paper_id": c.paper_id,
                    "title": c.title,
                    "year": c.year,
                    "venue": c.venue,
                    "doi": c.doi,
                    "composite_score": c.composite_score,
                }
                for c in candidates
            ]
        click.echo(json.dumps(payload, indent=2))
    else:
        click.echo(f"ID: {collection.key}")
        click.echo(f"URL: {collection.web_url}")


@cli.command("expand")
@click.argument("collection", required=False)
@click.option(
    "--target",
    "-t",
    default=None,
    help="Target Zotero collection name (default: append to source collection).",
)
@click.option(
    "--limit",
    "-k",
    default=10,
    type=int,
    help="Number of core candidates to discover (default: 10).",
)
@click.option(
    "--min-co-cites",
    default=1,
    type=int,
    help="Minimum co-citation threshold (default: 1).",
)
@click.option(
    "--sort",
    "-s",
    type=click.Choice(
        ["composite", "topological", "citations", "recent"], case_sensitive=False
    ),
    default="topological",
    help="Ranking order: topological (default), composite, citations, recent.",
)
@click.option(
    "--interactive/--non-interactive",
    "-i/-I",
    "interactive",
    default=None,
    help="Interactive CurationCheckpoint multi-selection (default: auto).",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Accept all candidates without prompting.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Perform expansion dry-run without writing to Zotero.",
)
def expand(
    collection: Optional[str],
    target: Optional[str],
    limit: int,
    min_co_cites: int,
    sort: str,
    interactive: Optional[bool],
    yes: bool,
    dry_run: bool,
) -> None:
    """Expand an existing Zotero collection via bidirectional citation snowballing."""
    session = load_session()
    source_col = collection or session.get("active_collection")

    if not source_col:
        click.echo(
            "⚠️ No collection specified. Provide [COLLECTION] or run search first.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Loading seed literature from Zotero collection: '{source_col}'...")
    zotero_mgr = ZoteroManager()
    seeds = zotero_mgr.get_collection_candidates(source_col)

    if not seeds:
        click.echo(f"⚠️ No papers found in collection '{source_col}'.", err=True)
        return

    click.echo(f"Found {len(seeds)} seed papers. Executing citation snowballing...")
    service = DiscoveryService()
    snowball_res = service.snowballer.snowball(
        seeds, min_co_citations=min_co_cites, max_backward=20, max_forward=20
    )

    ranked = service.ranker.rank_and_select(
        snowball_res.all_candidates, top_k=limit, sort_by=sort
    )

    is_interactive = (
        False
        if (yes or interactive is False)
        else (True if interactive is True else (sys.stdin.isatty() and not dry_run))
    )
    if is_interactive:
        checkpoint = CurationCheckpoint()
        curated = checkpoint.review(ranked, interactive=True)
    else:
        table_output = service.format_table(ranked)
        click.echo(table_output)
        curated = ranked

    if not curated:
        click.echo("Curation aborted. No papers added.")
        return

    if dry_run:
        click.echo(f"\n[dry-run] Discovered {len(curated)} core papers. No changes committed.")
        return

    dest_col = target or source_col
    _, sync_res = zotero_mgr.sync_to_collection(dest_col, curated)
    click.echo(f"🎉 Successfully expanded and synced {len(curated)} papers to '{dest_col}'!")


@cli.command()
@click.option(
    "--collection",
    "-c",
    default=None,
    help="Target Zotero collection name or key. Defaults to active collection in session.",
)
@click.option(
    "--status",
    is_flag=True,
    default=False,
    help="Display current checkpoint status and missing items report.",
)
def checkpoint(collection: Optional[str], status: bool) -> None:
    """Inspect FulltextCheckpoint status and resolve missing PDF full texts."""
    session = load_session()
    col = collection or session.get("active_collection")

    if not col:
        click.echo(
            "⚠️ No active collection found in session. Please specify --collection <name-or-key>."
        )
        return

    click.echo(f"Scanning checkpoint for collection: '{col}'...")
    manager = ZoteroManager()
    report = manager.scan_collection_checkpoint(col)
    output = manager.format_checkpoint_report(report)
    click.echo(output)


@cli.command("sync-notebook")
@click.option(
    "--collection", "-c", "collections", required=True, multiple=True,
    help="Zotero collection name or key. Repeat to sync several collections into one notebook.",
)
@click.option(
    "--notebook",
    default=None,
    help="Target Gemini Notebook UUID or exact title. Default: the collection's name (created if missing).",
)
@click.option("--recursive", is_flag=True, help="Include every subcollection.")
@click.option(
    "--replace", "replace", multiple=True, metavar="KEY",
    help="Delete the source of this Zotero key and upload it again. Repeatable.",
)
@click.option("--dry-run", is_flag=True, help="Print the plan only; write nothing.")
@click.option("--force", is_flag=True, help="Sync into a notebook whose sources mostly lack [key] titles.")
@click.option(
    "--allow-url",
    is_flag=True,
    help="For items with no PDF/EPUB/HTML snapshot, let Gemini Notebook fetch the DOI or URL "
    "(may only get a paywall page).",
)
def sync_notebook(
    collections: tuple[str, ...],
    notebook: Optional[str],
    recursive: bool,
    replace: tuple[str, ...],
    dry_run: bool,
    force: bool,
    allow_url: bool,
) -> None:
    """Sync Zotero collections' full texts into a Gemini Notebook as `[key] title` sources.

    Each item contributes its first PDF, else an EPUB, else its HTML snapshot (as markdown).
    """
    try:
        report = notebook_sync.sync_collections(
            ZoteroManager(),
            collections,
            notebook,
            recursive=recursive,
            replace=replace,
            dry_run=dry_run,
            force=force,
            allow_url=allow_url,
            progress=lambda m: click.echo(m, err=True),
        )
    except notebook_sync.SyncError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    click.echo(json.dumps(report, ensure_ascii=False, indent=2))


@cli.command("skim-notebook")
@click.option("--notebook", required=True, help="Gemini Notebook UUID or exact title.")
@click.option(
    "--key", "keys", multiple=True, required=True, help="Zotero item key of a `[key]` source (repeatable)."
)
@click.option(
    "--focus",
    default=None,
    help="Research question: rate each paper's relevance and tag it gemini-skim/relevance:<level>.",
)
def skim_notebook(notebook: str, keys: tuple[str, ...], focus: Optional[str]) -> None:
    """Skim `[key]` sources one by one in fresh conversations; write each as a Zotero child note.

    The notebook's existing conversation is saved as a notebook note before it is replaced.
    """
    try:
        report = notebook_skim.skim_notebook(
            ZoteroManager().client,
            notebook,
            list(keys),
            progress=lambda m: click.echo(m, err=True),
            focus=focus,
        )
    except notebook_skim.SkimError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    click.echo(json.dumps(report, ensure_ascii=False, indent=2))


def check_notebook_auth() -> str:
    """Authenticate against Gemini Notebook via notebooklm-py; raise on failure.

    Equivalent to `notebooklm auth check --test`: opens a client from the
    profile master token and lists notebooks as the liveness signal.
    """
    import asyncio

    from research_toolkit.notebook import client as notebook_client

    async def _probe() -> int:
        async with notebook_client.open_client() as client:
            return len(await client.notebooks.list())

    return f"Authenticated ({asyncio.run(_probe())} notebooks)"


@cli.command()
def doctor() -> None:
    """Validate system configuration, credentials, and local storage connectivity."""
    click.echo("\n🩺 Running Research Toolkit Diagnostic Health Check...")
    import os

    checks = []

    # 1. Zotero User ID & API Key
    z_user = os.getenv("ZOTERO_USER_ID")
    z_key = os.getenv("ZOTERO_API_KEY")
    z_type = os.getenv("ZOTERO_LIBRARY_TYPE", "user")

    if z_user and z_key:
        if z_type.lower() == "user":
            checks.append(("Zotero Auth", "PASS", f"User library configured (ID: {z_user})"))
        else:
            checks.append(("Zotero Auth", "FAIL", f"ZOTERO_LIBRARY_TYPE='{z_type}' is invalid. Must be 'user'."))
    else:
        checks.append(("Zotero Auth", "WARN", "Missing ZOTERO_USER_ID or ZOTERO_API_KEY. Required for collection sync."))

    # 2. Zotero Storage Directory
    default_storage = (
        Path("/app/data/storage")
        if Path("/app/data").exists()
        else (Path.home() / "Zotero" / "storage")
    )
    storage_dir = Path(os.getenv("ZOTERO_STORAGE_DIR") or default_storage)
    if storage_dir.exists():
        checks.append(("Zotero Storage", "PASS", f"Storage cache directory ready: {storage_dir}"))
    else:
        checks.append(("Zotero Storage", "PASS", f"Cloud mode active (on-demand cache: {storage_dir})"))

    # 3. Discovery APIs
    s2_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    checks.append(("Semantic Scholar", "PASS" if s2_key else "INFO", "API key configured" if s2_key else "Unauthenticated rate limit (1 RPS) active."))

    oa_key = os.getenv("OPENALEX_API_KEY")
    checks.append(("OpenAlex", "PASS" if oa_key else "INFO", "API key configured" if oa_key else "Public polite pool active."))

    # 4. Gemini Notebook
    try:
        checks.append(("Gemini Notebook", "PASS", check_notebook_auth()))
    except Exception as exc:  # any failure to authenticate is a FAIL, not a crash
        checks.append(("Gemini Notebook", "FAIL", f"Auth check failed: {exc}"))
    if os.getenv("NOTEBOOKLM_AUTH_JSON"):
        checks.append((
            "Gemini Notebook",
            "WARN",
            "NOTEBOOKLM_AUTH_JSON is set; it overrides the profile master token. Unset it.",
        ))

    # Format output
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="System Diagnostics", show_header=True)
        table.add_column("Component", style="bold", width=20)
        table.add_column("Status", width=8)
        table.add_column("Details")
        for comp, status, details in checks:
            color = "green" if status == "PASS" else ("yellow" if status in ("WARN", "INFO") else "red")
            table.add_row(comp, f"[{color}]{status}[/{color}]", details)
        console.print(table)
    except ImportError:
        for comp, status, details in checks:
            click.echo(f"  [{status}] {comp:20} - {details}")


@cli.command("mcp-schema")
def mcp_schema() -> None:
    """Print Model Context Protocol (MCP) tool schema definitions as JSON."""
    from research_toolkit.mcp.tools import get_tools_manifest
    click.echo(json.dumps(get_tools_manifest(), indent=2))


@cli.command()
@click.option("--host", default="0.0.0.0", help="Network host interface to bind.")
@click.option("--port", default=8820, type=int, help="Port to listen on (default: 8820).")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development.")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the DualStackGateway daemon (MCP SSE + OpenAPI REST for ChatGPT)."""
    import uvicorn
    click.echo(f"🚀 Starting Research Toolkit Dual-Stack Gateway on http://{host}:{port} ...")
    click.echo(f"   • OpenAPI Schema & Docs: http://{host}:{port}/docs")
    click.echo(f"   • MCP Streamable HTTP  : http://{host}:{port}/mcp/http")
    click.echo(f"   • MCP SSE (legacy)     : http://{host}:{port}/mcp/sse")
    uvicorn.run("research_toolkit.mcp.server:app", host=host, port=port, reload=reload)


@cli.command("generate-key")
@click.option(
    "--write-env",
    is_flag=True,
    help="Automatically write/update RESEARCH_TOOLKIT_API_KEY in .env file.",
)
@click.option(
    "--prefix",
    default="rtk_",
    help="Prefix for generated token (default: 'rtk_').",
)
def generate_key(write_env: bool, prefix: str) -> None:
    """Generate a cryptographically secure API key for ChatGPT and Claude authentication."""
    import secrets
    token = f"{prefix}{secrets.token_urlsafe(32)}"
    click.echo(f"🔑 Generated API Key: {token}")

    if write_env:
        env_file = Path.cwd() / ".env"
        lines = []
        key_found = False
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("RESEARCH_TOOLKIT_API_KEY="):
                    lines.append(f"RESEARCH_TOOLKIT_API_KEY={token}")
                    key_found = True
                else:
                    lines.append(line)
        if not key_found:
            lines.append(f"RESEARCH_TOOLKIT_API_KEY={token}")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        click.echo(f"✅ Successfully written to {env_file}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()

