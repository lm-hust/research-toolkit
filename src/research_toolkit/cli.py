"""
src/research_toolkit/cli.py
Main command-line interface for the Research Toolkit.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import click

from research_toolkit.discovery.curation import CurationCheckpoint
from research_toolkit.discovery.models import (
    AssessmentRecord,
    PaperCandidateBatch,
    SelectionResult,
)
from research_toolkit.discovery.ranker import Ranker
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
    "--limit",
    "-k",
    default=10,
    type=int,
    help="Number of candidate papers to discover (default: 10).",
)
@click.option(
    "--topic",
    "-t",
    default=None,
    help="Optional topic identifier or query refinement.",
)
@click.option(
    "--collection",
    "-c",
    default=None,
    help="Legacy option: Target collection (deprecated in search atom).",
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
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Output machine-readable PaperCandidateBatch JSON to stdout.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress table and progress output to stderr.",
)
@click.option(
    "--data-dir",
    default=None,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Directory to persist candidate batches (default: ./.research/batches).",
)
@click.option(
    "--batch-dir",
    default=None,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Directory to persist candidate batches.",
)
@click.option(
    "--batch-id",
    default=None,
    help="Explicit ID to assign to the candidate batch.",
)
@click.option(
    "--snowball/--no-snowball",
    default=False,
    help="Legacy option: Snowballing is decoupled from the search atom.",
)
@click.option(
    "--detail",
    "-d",
    is_flag=True,
    default=False,
    help="Legacy option.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Legacy option: search atom is read-only retrieval by default.",
)
@click.option(
    "--sort",
    "-s",
    default="composite",
    help="Ranking order (composite, citations, recent).",
)
def search(
    query: str,
    limit: int,
    topic: Optional[str],
    collection: Optional[str],
    min_cites: int,
    year: Optional[str],
    peer_reviewed: bool,
    as_json: bool,
    quiet: bool,
    data_dir: Optional[Path],
    batch_dir: Optional[Path],
    batch_id: Optional[str],
    snowball: bool,
    detail: bool,
    dry_run: bool,
    sort: str,
) -> None:
    """Pure literature retrieval atom across Semantic Scholar and OpenAlex."""
    if not quiet:
        click.echo(f"Searching literature for: '{query}'...", err=True)

    y_range = parse_year_range(year)
    effective_topic = topic or query
    service = DiscoveryService()
    batch = service.search(
        query=query,
        limit=limit,
        min_cites=min_cites,
        year_range=y_range,
        peer_reviewed_only=peer_reviewed,
        batch_id=batch_id,
    )

    # Persist batch file atomically
    target_dir = batch_dir or data_dir
    saved_path = batch.save(directory=target_dir)

    # Persist session state
    save_session(
        {
            "active_batch": batch.batch_id,
            "active_batch_file": str(saved_path),
            "topic": effective_topic,
        }
    )

    # Route Rich table and progress info to stderr
    if not quiet:
        if batch.papers:
            table_output = service.format_table(batch.papers)
            click.echo(table_output, err=True)
            click.echo(
                f"Persisted batch '{batch.batch_id}' ({len(batch.papers)} papers) to {saved_path}",
                err=True,
            )
        else:
            click.echo("No matching papers found.", err=True)

    # Route pure JSON to stdout when piped (non-tty) or when --json is specified
    is_piped = not sys.stdout.isatty()
    if as_json or is_piped:
        click.echo(batch.to_json(indent=2))


def load_candidate_batch(val: str) -> PaperCandidateBatch:
    """Loads a PaperCandidateBatch from a file path or resolves a batch ID."""
    p = Path(val)
    if p.is_file():
        return PaperCandidateBatch.load(p)

    search_paths = [
        Path.cwd() / ".research" / "batches" / f"{val}.json",
        Path.cwd() / ".research" / "batches" / val,
    ]
    batch_dir = os.getenv("RESEARCH_BATCH_DIR") or os.getenv("RESEARCH_DATA_DIR")
    if batch_dir:
        search_paths.extend([
            Path(batch_dir) / f"{val}.json",
            Path(batch_dir) / val,
        ])
    for sp in search_paths:
        if sp.is_file():
            return PaperCandidateBatch.load(sp)

    raise click.BadParameter(f"Candidate batch file or ID '{val}' not found.")


def load_assessment_records(val: str) -> list[AssessmentRecord]:
    """Loads AssessmentRecords from a JSONL or JSON file, or inline text."""
    p = Path(val)
    if p.is_file():
        content = p.read_text(encoding="utf-8").strip()
    else:
        content = val.strip()

    if not content:
        return []

    # JSON array format
    if content.startswith("[") and content.endswith("]"):
        try:
            arr = json.loads(content)
            return [AssessmentRecord.from_dict(item) for item in arr]
        except Exception:
            pass

    # JSONL format (one object per line)
    records: list[AssessmentRecord] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            records.append(AssessmentRecord.from_json(line))
        except Exception as e:
            logger.warning("Could not parse assessment record line: %s (%s)", line, e)
    return records


def format_selection_table(result: SelectionResult, ranker: Ranker) -> str:
    """Formats top selected candidates and diagnostic score breakdowns into a Rich terminal table."""
    if not result.selected_papers:
        return "No candidates selected."

    try:
        import io

        from rich.console import Console
        from rich.table import Table

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)
        table = Table(
            title=f"Top Selected Literature Candidates (MMR Diversity Ranking, N={len(result.selected_papers)})",
            show_header=True,
            header_style="bold",
        )
        table.add_column("Rank", justify="right", style="cyan", width=5)
        table.add_column("Type", justify="center", width=6)
        table.add_column("Title", style="bold", min_width=30)
        table.add_column("Author", min_width=12)
        table.add_column("Year", justify="center", width=6)
        table.add_column("Cites", justify="right", width=7)
        table.add_column("Score", justify="right", width=7)
        table.add_column("Breakdown (rel/cite/ven/rec)", min_width=25)
        table.add_column("DOI / Identifier", min_width=20)

        for idx, p in enumerate(result.selected_papers, start=1):
            if p.is_review:
                doc_type = "[REV]"
            elif p.is_preprint:
                doc_type = "[PRE]"
            else:
                doc_type = "[RES]"

            first_author = p.authors[0] if p.authors else "-"
            if len(first_author) > 15:
                first_author = first_author[:13] + ".."

            score = result.scores.get(p.paper_id, p.composite_score)
            bd = ranker.score_breakdown(p)
            bd_str = f"r:{bd['s_rel']:.2f} c:{bd['s_cite']:.2f} v:{bd['s_venue']:.2f} y:{bd['s_recency']:.2f}"
            title_disp = (p.title[:45] + "...") if len(p.title) > 48 else p.title
            doi_disp = p.doi or p.arxiv_id or p.paper_id

            table.add_row(
                str(idx),
                doc_type,
                title_disp,
                first_author,
                str(p.year or "-"),
                str(p.citation_count),
                f"{score:.3f}",
                bd_str,
                doi_disp,
            )

        console.print(table)
        return buf.getvalue()
    except ImportError:
        return f"Selected {len(result.selected_papers)} papers."


@cli.command("rank")
@click.option(
    "--batch",
    "-b",
    default=None,
    help="Candidate batch ID or file path to evaluate.",
)
@click.option(
    "--assessments",
    "-a",
    default=None,
    help="Path to structured AssessmentRecords JSONL or JSON file.",
)
@click.option(
    "--topic",
    "-t",
    default=None,
    help="Topic identifier or query text (defaults to batch topic).",
)
@click.option(
    "--top-n",
    "-n",
    default=10,
    type=int,
    help="Number of top candidates to select (default: 10).",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress Rich table and progress diagnostics on stderr.",
)
def rank(
    batch: Optional[str],
    assessments: Optional[str],
    topic: Optional[str],
    top_n: int,
    quiet: bool,
) -> None:
    """Ranks candidate papers with composite scoring and MMR diversity selection."""
    batch_obj: Optional[PaperCandidateBatch] = None
    if batch:
        batch_obj = load_candidate_batch(batch)
    else:
        stdin_stream = sys.stdin
        if not stdin_stream.isatty():
            stdin_data = stdin_stream.read().strip()
            if stdin_data:
                batch_obj = PaperCandidateBatch.from_json(stdin_data)
        if batch_obj is None:
            session = load_session()
            active_file = session.get("active_batch_file")
            if active_file and Path(active_file).is_file():
                batch_obj = PaperCandidateBatch.load(active_file)
            else:
                raise click.UsageError(
                    "Candidate batch must be provided via stdin JSON stream or --batch <path_or_id>."
                )

    assessment_records = (
        load_assessment_records(assessments) if assessments else None
    )
    effective_topic = topic or batch_obj.topic or batch_obj.query

    ranker = Ranker()
    result = ranker.select(
        candidates=batch_obj.papers,
        requested_n=top_n,
        assessments=assessment_records,
        batch_id=batch_obj.batch_id,
        topic=effective_topic,
    )

    if not quiet:
        if result.selected_papers:
            table_disp = format_selection_table(result, ranker)
            click.echo(table_disp, err=True)
            click.echo(
                f"Selected {len(result.selected_papers)}/{top_n} candidates (strategy: {result.strategy}, status: {result.status})",
                err=True,
            )
        else:
            click.echo("No eligible candidates found.", err=True)

    click.echo(result.to_json(indent=2))


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

