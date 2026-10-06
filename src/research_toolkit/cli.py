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

from research_toolkit.discovery.query import QueryTranslator
from research_toolkit.discovery.service import DiscoveryService
from research_toolkit.synthesis.adapters import get_default_gateway
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
    help="Display detailed table of retrieved paper candidates.",
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
def search(
    query: str,
    topic: Optional[str],
    limit: int,
    detail: bool,
    as_json: bool,
    dry_run: bool,
) -> None:
    """Search literature and rank candidates across Semantic Scholar and OpenAlex."""
    if not as_json and detail:
        click.echo(f"Searching literature for: '{query}'...")

    service = DiscoveryService()
    candidates = service.search_and_rank(query, top_k=limit)

    if not candidates:
        if as_json:
            click.echo(json.dumps({"status": "no_results", "query": query, "count": 0}))
        else:
            click.echo("No matching papers found.")
        return

    # Derive canonical ZoteroCollection name
    col_name = QueryTranslator.to_collection_name(query, topic)

    # Print table if detailed view requested and not JSON mode
    if detail and not as_json:
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
    "--collection",
    "-c",
    default=None,
    help="Target Zotero collection name or key. Defaults to active collection in session.",
)
@click.option(
    "--allow-partial",
    is_flag=True,
    default=False,
    help="Proceed with upload even if some PDFs are missing.",
)
def sync_notebook(collection: Optional[str], allow_partial: bool) -> None:
    """Create a topic notebook in NotebookLM and upload verified local PDF sources."""
    session = load_session()
    col = collection or session.get("active_collection")
    if not col:
        click.echo("⚠️ No collection specified. Provide --collection <name-or-key>.", err=True)
        sys.exit(1)

    manager = ZoteroManager()
    report = manager.scan_collection_checkpoint(col)

    if report.missing_items and not allow_partial:
        click.echo(
            f"🛑 FulltextCheckpoint: {len(report.missing_items)}/{report.total_items} items lack local PDFs.\n"
            f"Resolve missing PDFs in Zotero first, or pass --allow-partial to proceed with ready items.",
            err=True,
        )
        sys.exit(1)

    if not report.ready_items:
        click.echo("⚠️ No ready PDF files found in collection.", err=True)
        sys.exit(1)

    click.echo(f"🔄 Creating NotebookLM notebook for: '{report.collection_name}'...")
    gw = get_default_gateway()
    notebook = gw.create_notebook(report.collection_name)
    click.echo(f"📓 Notebook created: ID={notebook.id} ({notebook.title})")

    uploaded = []
    for item in report.ready_items:
        if item.pdf_path:
            click.echo(f"  Uploading source: {item.title[:45]}...")
            src = gw.upload_source(notebook.id, Path(item.pdf_path))
            uploaded.append(src)

    session["notebook_id"] = notebook.id
    session["active_collection"] = col
    save_session(session)
    click.echo(f"✨ Successfully synced {len(uploaded)} sources to NotebookLM (ID: {notebook.id}).")


@cli.command()
@click.argument("query")
@click.option(
    "--notebook-id",
    "-nb",
    default=None,
    help="Target NotebookLM notebook ID. Defaults to active notebook in session.",
)
def ask(query: str, notebook_id: Optional[str]) -> None:
    """Execute source-grounded Q&A against synthesized notebook sources."""
    session = load_session()
    nb_id = notebook_id or session.get("notebook_id")
    if not nb_id:
        click.echo(
            "⚠️ No active notebook ID found. Run `sync-notebook` first or pass --notebook-id.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"💬 Querying notebook '{nb_id}'...")
    gw = get_default_gateway()
    grounded = gw.query_sources(nb_id, query)

    click.echo("\n" + "=" * 60)
    click.echo("🧠 GROUNDED SYNTHESIS ANSWER")
    click.echo("=" * 60)
    click.echo(grounded.answer)

    if grounded.citations:
        click.echo("\n" + "-" * 60)
        click.echo("📌 Distilled Evidence (Verbatim Grounded Quotes):")
        click.echo("-" * 60)
        for idx, cit in enumerate(grounded.citations, 1):
            src_str = cit.source_title or cit.source_id
            offset_str = f" [offset {cit.start_offset}:{cit.end_offset}]" if cit.end_offset else ""
            click.echo(f"{idx}. \"{cit.quote}\"")
            click.echo(f"   Source: {src_str}{offset_str}")
    click.echo("=" * 60)


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
    storage_dir = Path(os.getenv("ZOTERO_STORAGE_DIR") or (Path.home() / "Zotero" / "storage"))
    if storage_dir.exists():
        checks.append(("Zotero Storage", "PASS", f"Local directory found: {storage_dir}"))
    else:
        checks.append(("Zotero Storage", "INFO", f"Local directory not found at {storage_dir} (probe will create if mounted)."))

    # 3. Discovery APIs
    s2_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    checks.append(("Semantic Scholar", "PASS" if s2_key else "INFO", "API key configured" if s2_key else "Unauthenticated rate limit (1 RPS) active."))

    oa_key = os.getenv("OPENALEX_API_KEY")
    checks.append(("OpenAlex", "PASS" if oa_key else "INFO", "API key configured" if oa_key else "Public polite pool active."))

    # 4. NotebookLM / Gemini Gateway
    nlm_auth = os.getenv("NOTEBOOKLM_AUTH_JSON")
    gemini_key = os.getenv("GEMINI_API_KEY")
    master_token_file = Path.home() / ".notebooklm" / "profiles" / "default" / "master_token.json"

    if nlm_auth:
        checks.append(("Synthesis Gateway", "PASS", "NOTEBOOKLM_AUTH_JSON configured."))
    elif master_token_file.exists():
        checks.append(("Synthesis Gateway", "PASS", f"Master token file found: {master_token_file}"))
    elif gemini_key:
        checks.append(("Synthesis Gateway", "PASS", "GEMINI_API_KEY configured (Gemini fallback active)."))
    else:
        checks.append(("Synthesis Gateway", "WARN", "No synthesis credentials found (NOTEBOOKLM_AUTH_JSON, master_token.json, or GEMINI_API_KEY)."))

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


def main() -> None:
    cli()


if __name__ == "__main__":
    main()

