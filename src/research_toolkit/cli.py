"""
src/research_toolkit/cli.py
Main command-line interface for the Research Toolkit.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from pathlib import Path
from typing import Optional

import click

from research_toolkit.discovery.curation import CurationCheckpoint
from research_toolkit.discovery.models import (
    AssessmentRecord,
    PaperCandidate,
    PaperCandidateBatch,
    SelectionResult,
    SnowballResult,
)
from research_toolkit.discovery.query import QueryTranslator
from research_toolkit.discovery.ranker import Ranker
from research_toolkit.discovery.service import DiscoveryService
from research_toolkit.discovery.snowballer import (
    CitationSnowballer,
    adapt_seeds,
    load_seeds_from_collection,
)
from research_toolkit.notebook import skim as notebook_skim
from research_toolkit.notebook import sync as notebook_sync
from research_toolkit.zotero.manager import ZoteroManager
from research_toolkit.zotero.models import SyncResult

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


def _execute_scout_pipeline(
    topic_query: str,
    collection: Optional[str],
    top_n: int,
    direction: str,
    dry_run: bool,
    as_json: bool,
    quiet: bool,
    detail: bool,
    interactive: Optional[bool] = None,
    min_cites: int = 0,
    year: Optional[str] = None,
    peer_reviewed: bool = False,
    sort: str = "composite",
) -> None:
    """Executes the full literature discovery pipeline: Search -> Rank -> Snowball -> Re-rank -> Curation -> Export."""
    y_range = parse_year_range(year)
    effective_topic = topic_query
    col_name = collection or QueryTranslator.to_collection_name(topic_query)

    if not quiet:
        click.echo(f"🔭 Starting scout pipeline for topic: '{topic_query}'...", err=True)
        click.echo(f"   Target collection: '{col_name}'", err=True)

    # 1. Literature Search Atom
    service = DiscoveryService()
    search_batch = service.search(
        query=topic_query,
        limit=max(top_n * 2, 10),
        min_cites=min_cites,
        year_range=y_range,
        peer_reviewed_only=peer_reviewed,
    )
    search_candidates = search_batch.papers

    if not search_candidates:
        if not quiet:
            click.echo("No matching papers found in initial search.", err=True)
        if as_json or not sys.stdout.isatty():
            click.echo(json.dumps({
                "collection_key": None,
                "collection_name": col_name,
                "selected_count": 0,
                "created_count": 0,
                "reused_count": 0,
                "selected_papers": [],
                "status": "no_results",
            }, indent=2))
        return

    # 2. Initial Ranking & Selection for Snowball Seeds
    ranker = Ranker()
    initial_sel = ranker.select(
        candidates=search_candidates,
        requested_n=min(len(search_candidates), max(5, top_n)),
        topic=effective_topic,
    )
    seeds = initial_sel.selected_papers if initial_sel.selected_papers else search_candidates[:5]

    # 3. 1-Hop Citation Snowballing
    if not quiet:
        click.echo(
            f"🌱 Snowballing from {len(seeds)} seed papers (direction: {direction})...",
            err=True,
        )
    snowballer = CitationSnowballer()
    snowball_res = snowballer.snowball(
        seeds=seeds,
        direction=direction,
        max_backward=20,
        max_forward=20,
    )

    # 4. Re-Ranking & Stratified MMR Diversity Selection
    all_pool = list(seeds) + list(snowball_res.discovered_candidates)
    final_sel = ranker.select(
        candidates=all_pool,
        requested_n=top_n,
        topic=effective_topic,
    )
    ranked_candidates = final_sel.selected_papers if final_sel.selected_papers else all_pool[:top_n]

    # 5. Interactive CurationCheckpoint
    is_interactive = (
        interactive
        if interactive is not None
        else (sys.stdin.isatty() and not as_json and not quiet and not dry_run)
    )
    checkpoint = CurationCheckpoint(stream=sys.stderr)
    curated = checkpoint.review(ranked_candidates, auto_confirm=not is_interactive)
    if not curated:
        if not quiet:
            click.echo("Curation aborted. No papers selected.", err=True)
        return

    # 6. Export to Zotero
    if not quiet:
        click.echo(f"📦 Exporting {len(curated)} papers to Zotero collection '{col_name}'...", err=True)

    zotero_mgr = ZoteroManager()
    col_obj, sync_res = zotero_mgr.sync_to_collection(
        col_name,
        curated,
        auto_download_oa=not dry_run,
        dry_run=dry_run,
    )

    session = load_session()
    if not dry_run:
        session["active_collection"] = col_obj.name
        session["active_collection_key"] = col_obj.key
        save_session(session)

    if not quiet:
        table_disp = format_export_table(col_obj.name, col_obj.key, curated, sync_res)
        click.echo(table_disp, err=True)
        if dry_run:
            click.echo(
                f"[dry-run] Preview: {sync_res.created_count} new, {sync_res.reused_count} existing. No changes committed.",
                err=True,
            )
        else:
            click.echo(
                f"✨ Successfully exported {sync_res.total_count} papers to '{col_obj.name}' (Key: {col_obj.key}).",
                err=True,
            )
        if col_obj.web_url:
            click.echo(f"🔗 Collection URL: {col_obj.web_url}", err=True)

    # Formulate output summary
    summary_data = {
        "collection_key": col_obj.key,
        "collection_name": col_obj.name,
        "collection_url": col_obj.web_url,
        "selected_count": len(curated),
        "created_count": sync_res.created_count,
        "reused_count": sync_res.reused_count,
        "total_count": sync_res.total_count,
        "dry_run": dry_run,
        "status": "completed",
    }
    if detail:
        summary_data["candidates"] = [c.to_dict() for c in curated]

    if as_json or not sys.stdout.isatty():
        click.echo(json.dumps(summary_data, indent=2))


@cli.command("scout")
@click.argument("topic", required=False)
@click.option(
    "--topic",
    "-t",
    "topic_opt",
    default=None,
    help="Topic keyword or query expression.",
)
@click.option(
    "--collection",
    "-c",
    default=None,
    help="Target Zotero collection name or key.",
)
@click.option(
    "--top-n",
    "-n",
    default=10,
    type=int,
    help="Target number of papers (default: 10).",
)
@click.option(
    "--direction",
    type=click.Choice(["forward", "backward", "both"], case_sensitive=False),
    default="both",
    help="Snowballing direction (forward, backward, both, default both).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview candidate discovery and selection without mutating Zotero.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emits JSON selection and export summary to stdout.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppresses intermediate tables and progress on stderr.",
)
@click.option(
    "--detail",
    "-d",
    is_flag=True,
    default=False,
    help="Includes extended candidate previews in output.",
)
@click.option(
    "--interactive/--non-interactive",
    default=None,
    help="Interactive CurationCheckpoint multi-selection (default: auto).",
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
def scout(
    topic: Optional[str],
    topic_opt: Optional[str],
    collection: Optional[str],
    top_n: int,
    direction: str,
    dry_run: bool,
    as_json: bool,
    quiet: bool,
    detail: bool,
    interactive: Optional[bool],
    min_cites: int,
    year: Optional[str],
    peer_reviewed: bool,
) -> None:
    """End-to-end literature discovery pipeline: Search -> Rank -> Snowball -> Re-rank -> Curation -> Export."""
    effective_topic = topic_opt or topic
    if not effective_topic:
        raise click.UsageError("Topic must be provided either as argument or via --topic.")

    _execute_scout_pipeline(
        topic_query=effective_topic,
        collection=collection,
        top_n=top_n,
        direction=direction,
        dry_run=dry_run,
        as_json=as_json,
        quiet=quiet,
        detail=detail,
        interactive=interactive,
        min_cites=min_cites,
        year=year,
        peer_reviewed=peer_reviewed,
    )


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
@click.option(
    "--auto-sync",
    is_flag=True,
    default=False,
    help="Legacy option: Automatic sync to Zotero.",
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
    auto_sync: bool,
) -> None:
    """Pure literature retrieval atom across Semantic Scholar and OpenAlex."""
    # Check for legacy options requiring compatibility shim to scout
    is_legacy_mode = bool(collection or auto_sync or snowball)
    if is_legacy_mode:
        warn_msg = (
            "DeprecationWarning: Invoking 'search' with legacy workflow options (--collection, "
            "--snowball, --auto-sync) is deprecated. Use 'research-toolkit scout' instead."
        )
        warnings.warn(warn_msg, DeprecationWarning, stacklevel=2)
        click.echo(f"⚠️  {warn_msg}", err=True)

        _execute_scout_pipeline(
            topic_query=query,
            collection=collection,
            top_n=limit,
            direction="both",
            dry_run=dry_run,
            as_json=as_json,
            quiet=quiet,
            detail=detail,
            min_cites=min_cites,
            year=year,
            peer_reviewed=peer_reviewed,
            sort=sort,
        )
        return

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


def resolve_batch_path(val: str) -> Path:
    """Resolves a batch ID or file path to an existing Path, or raises click.BadParameter."""
    p = Path(val)
    if p.is_file():
        return p

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
            return sp

    raise click.BadParameter(f"Batch file or ID '{val}' not found.")


def load_candidate_batch(val: str) -> PaperCandidateBatch:
    """Loads a PaperCandidateBatch from a file path or resolves a batch ID."""
    p = resolve_batch_path(val)
    return PaperCandidateBatch.load(p)


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


def format_snowball_table(result: SnowballResult) -> str:
    """Formats discovered candidates into a Rich table for terminal output on stderr."""
    try:
        from io import StringIO

        from rich.console import Console
        from rich.table import Table

        buf = StringIO()
        console = Console(file=buf, force_terminal=True)
        table = Table(
            title=f"Snowball Discovered Candidates (Direction: {result.direction}, Status: {result.status})",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Type", width=7)
        table.add_column("Role", width=14)
        table.add_column("Title", style="bold", min_width=30, max_width=50)
        table.add_column("Author", width=15)
        table.add_column("Year", width=6)
        table.add_column("Cites", justify="right", width=7)
        table.add_column("Co-Cites", justify="right", width=8)
        table.add_column("DOI / ID", style="dim", width=24)

        for idx, p in enumerate(result.discovered_candidates, 1):
            if p.is_review:
                doc_type = "[REV]"
            elif p.is_preprint:
                doc_type = "[PRE]"
            else:
                doc_type = "[RES]"

            role_badge = f"[{p.topological_role}]" if p.topological_role else "-"
            first_author = p.authors[0] if p.authors else "-"
            if len(first_author) > 15:
                first_author = first_author[:13] + ".."

            title_disp = (p.title[:47] + "...") if len(p.title) > 50 else p.title
            doi_disp = p.doi or p.arxiv_id or p.paper_id
            if len(doi_disp) > 24:
                doi_disp = doi_disp[:22] + ".."

            table.add_row(
                str(idx),
                doc_type,
                role_badge,
                title_disp,
                first_author,
                str(p.year or "-"),
                str(p.citation_count),
                str(p.co_citation_count),
                doi_disp,
            )

        console.print(table)
        return buf.getvalue()
    except ImportError:
        return f"Discovered {len(result.discovered_candidates)} candidates."


@cli.command("snowball")
@click.option(
    "--batch",
    "-b",
    default=None,
    help="Candidate batch ID or file path to evaluate as seeds.",
)
@click.option(
    "--seeds",
    "-s",
    default=None,
    help="Comma-separated DOIs or platform IDs to use as seeds.",
)
@click.option(
    "--from-collection",
    "-c",
    default=None,
    help="Existing Zotero collection name or key to load seeds from.",
)
@click.option(
    "--direction",
    type=click.Choice(["forward", "backward", "both"], case_sensitive=False),
    default="both",
    help="Expansion direction: forward, backward, or both (default: both).",
)
@click.option(
    "--max-backward",
    default=20,
    type=int,
    help="Maximum backward references to expand (default: 20).",
)
@click.option(
    "--max-forward",
    default=20,
    type=int,
    help="Maximum forward citations to expand (default: 20).",
)
@click.option(
    "--min-co-cites",
    default=1,
    type=int,
    help="Minimum co-citation threshold (default: 1).",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress Rich table and progress diagnostics on stderr.",
)
def snowball(
    batch: Optional[str],
    seeds: Optional[str],
    from_collection: Optional[str],
    direction: str,
    max_backward: int,
    max_forward: int,
    min_co_cites: int,
    quiet: bool,
) -> None:
    """Executes 1-hop bidirectional citation expansion from multi-source seeds."""
    seed_candidates: list[PaperCandidate] = []

    if seeds:
        seed_candidates = adapt_seeds(seeds)
    elif from_collection:
        seed_candidates = load_seeds_from_collection(from_collection)
    elif batch:
        batch_obj = load_candidate_batch(batch)
        seed_candidates = batch_obj.papers
    else:
        stdin_stream = sys.stdin
        if not stdin_stream.isatty():
            stdin_data = stdin_stream.read().strip()
            if stdin_data:
                try:
                    data = json.loads(stdin_data)
                    seed_candidates = adapt_seeds(data)
                except Exception as e:
                    raise click.UsageError(f"Failed to parse seeds from stdin JSON: {e}")
        if not seed_candidates:
            session = load_session()
            active_file = session.get("active_batch_file")
            if active_file and Path(active_file).is_file():
                batch_obj = PaperCandidateBatch.load(active_file)
                seed_candidates = batch_obj.papers
            elif session.get("active_collection"):
                seed_candidates = load_seeds_from_collection(session["active_collection"])
            else:
                raise click.UsageError(
                    "Seed papers must be provided via stdin JSON stream, --batch, --seeds, or --from-collection."
                )

    if not quiet:
        click.echo(
            f"Ingested {len(seed_candidates)} seed papers. Executing 1-hop {direction} citation expansion...",
            err=True,
        )

    snowballer = CitationSnowballer()
    result = snowballer.snowball(
        seeds=seed_candidates,
        direction=direction,
        max_backward=max_backward,
        max_forward=max_forward,
        min_co_citations=min_co_cites,
    )

    if not quiet:
        if result.discovered_candidates:
            table_disp = format_snowball_table(result)
            click.echo(table_disp, err=True)
            click.echo(
                f"Discovered {len(result.discovered_candidates)} candidates ({len(result.foundational)} foundational, {len(result.recent_advancements)} recent advancements) across {len(result.seeds)} seeds.",
                err=True,
            )
        else:
            click.echo("No candidates discovered within budget.", err=True)

    click.echo(result.to_json(indent=2))


def parse_export_payload(
    raw_json: str,
) -> tuple[list[PaperCandidate], Optional[str], Optional[str]]:
    """
    Parses a JSON string representing SelectionResult or PaperCandidateBatch.
    Returns (candidates, batch_id, topic).
    """
    data = json.loads(raw_json)
    if isinstance(data, dict):
        if "selected_papers" in data:
            sel = SelectionResult.from_dict(data)
            return sel.selected_papers, sel.batch_id, None
        elif "papers" in data:
            batch = PaperCandidateBatch.from_dict(data)
            return batch.papers, batch.batch_id, batch.topic or batch.query
        else:
            raise click.BadParameter(
                "JSON payload must contain 'selected_papers' or 'papers'."
            )
    elif isinstance(data, list):
        papers = [
            p if isinstance(p, PaperCandidate) else PaperCandidate.from_dict(p)
            for p in data
        ]
        return papers, None, None
    raise click.BadParameter("Invalid JSON payload structure.")


def load_export_batch(
    val: str,
) -> tuple[list[PaperCandidate], Optional[str], Optional[str]]:
    """Loads SelectionResult or PaperCandidateBatch from file path or batch ID."""
    p = resolve_batch_path(val)
    content = p.read_text(encoding="utf-8")
    return parse_export_payload(content)


def format_export_table(
    collection_name: str,
    collection_key: str,
    candidates: list[PaperCandidate],
    sync_result: SyncResult,
) -> str:
    """Formats exported candidates and collection sync summary into a Rich terminal table."""
    if not candidates:
        return f"No candidate papers to export for collection '{collection_name}'."

    try:
        import io

        from rich.console import Console
        from rich.table import Table

        from research_toolkit.discovery.dedup import Deduplicator

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)
        table = Table(
            title=f"Zotero Library Export: '{collection_name}' (Key: {collection_key}, Total: {len(candidates)})",
            show_header=True,
            header_style="bold",
        )
        table.add_column("#", justify="right", style="cyan", width=4)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Type", justify="center", width=6)
        table.add_column("Title", style="bold", min_width=35)
        table.add_column("Author", min_width=12)
        table.add_column("Year", justify="center", width=6)
        table.add_column("DOI / Identifier", min_width=20)

        # Index existing/reused items by DOI or title
        reused_dois = set()
        reused_titles = set()
        for r_item in sync_result.reused_items:
            r_data = r_item.get("data", {}) if isinstance(r_item, dict) else {}
            r_doi = Deduplicator.clean_doi(r_data.get("DOI"))
            if r_doi:
                reused_dois.add(r_doi)
            r_t = Deduplicator.clean_title(r_data.get("title", ""))
            if r_t:
                reused_titles.add(r_t)

        for idx, p in enumerate(candidates, start=1):
            if p.is_review:
                doc_type = "[REV]"
            elif p.is_preprint:
                doc_type = "[PRE]"
            else:
                doc_type = "[RES]"

            first_author = p.authors[0] if p.authors else "-"
            if len(first_author) > 15:
                first_author = first_author[:13] + ".."

            title_disp = (p.title[:45] + "...") if len(p.title) > 48 else p.title
            doi_disp = p.doi or p.arxiv_id or p.paper_id or "-"

            p_doi = Deduplicator.clean_doi(p.doi) if p.doi else ""
            p_title = Deduplicator.clean_title(p.title) if p.title else ""
            is_reused = (p_doi and p_doi in reused_dois) or (
                not p_doi and p_title and p_title in reused_titles
            )
            status_tag = "[REUSED]" if is_reused else "[CREATED]"

            table.add_row(
                str(idx),
                status_tag,
                doc_type,
                title_disp,
                first_author,
                str(p.year or "-"),
                doi_disp,
            )

        console.print(table)
        return buf.getvalue()
    except ImportError:
        return f"Exported {len(candidates)} papers to '{collection_name}'."


@cli.command("export")
@click.option(
    "--batch",
    "-b",
    default=None,
    help="Candidate batch or selection result ID or file path.",
)
@click.option(
    "--collection",
    "-c",
    default=None,
    help="Target Zotero collection name or key. Defaults to active collection in session.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview export without modifying Zotero personal library.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress table and progress output to stderr.",
)
def export(
    batch: Optional[str],
    collection: Optional[str],
    dry_run: bool,
    quiet: bool,
) -> None:
    """Exports literature candidates to personal Zotero library collection."""
    candidates: list[PaperCandidate] = []
    batch_id: Optional[str] = None
    topic: Optional[str] = None

    if batch:
        candidates, batch_id, topic = load_export_batch(batch)
    else:
        stdin_stream = sys.stdin
        stdin_data = ""
        if not stdin_stream.isatty():
            stdin_data = stdin_stream.read().strip()
        if stdin_data:
            candidates, batch_id, topic = parse_export_payload(stdin_data)
        else:
            session = load_session()
            active_file = session.get("active_batch_file")
            if active_file and Path(active_file).is_file():
                candidates, batch_id, topic = load_export_batch(active_file)
            else:
                raise click.UsageError(
                    "Candidate batch or selection result must be provided via stdin JSON stream or --batch <path_or_id>."
                )

    session = load_session()
    target_col = collection or session.get("active_collection")
    if not target_col:
        raise click.UsageError(
            "No target collection specified. Provide --collection <name_or_key> or set active collection in session."
        )

    if not quiet:
        click.echo(
            f"Exporting {len(candidates)} papers to Zotero collection '{target_col}'...",
            err=True,
        )

    zotero_mgr = ZoteroManager()
    col_obj, sync_res = zotero_mgr.sync_to_collection(
        target_col,
        candidates,
        auto_download_oa=not dry_run,
        dry_run=dry_run,
    )

    if not dry_run:
        session["active_collection"] = col_obj.name
        session["active_collection_key"] = col_obj.key
        save_session(session)

    if not quiet:
        table_disp = format_export_table(col_obj.name, col_obj.key, candidates, sync_res)
        click.echo(table_disp, err=True)
        if dry_run:
            click.echo(
                f"[dry-run] Preview: {sync_res.created_count} new, {sync_res.reused_count} existing. No changes committed.",
                err=True,
            )
        else:
            click.echo(
                f"✨ Successfully exported {sync_res.total_count} papers to '{col_obj.name}' (Key: {col_obj.key}).",
                err=True,
            )
        if col_obj.web_url:
            click.echo(f"🔗 Collection URL: {col_obj.web_url}", err=True)

    summary = sync_res.to_dict()
    summary["dry_run"] = dry_run
    click.echo(json.dumps(summary, indent=2))


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


def stdin_is_interactive() -> bool:
    """Whether a person can answer a prompt (agents run without a terminal)."""
    return sys.stdin.isatty()


@cli.command("skim-notebook")
@click.option("--notebook", required=True, help="Gemini Notebook UUID or exact title.")
@click.option(
    "--key",
    "keys",
    multiple=True,
    help="Zotero item key of a `[key]` source (repeatable). Default: every `[key]` source.",
)
@click.option(
    "--focus",
    default=None,
    help="Research question: rate each paper's relevance and tag it gemini-skim/relevance:<level>.",
)
@click.option("--refresh", is_flag=True, help="Re-read papers that already have a skim note (same note).")
@click.option("--yes", is_flag=True, help="Skip the confirmation when the quota looks too small.")
def skim_notebook(
    notebook: str, keys: tuple[str, ...], focus: Optional[str], refresh: bool, yes: bool
) -> None:
    """Skim `[key]` sources one by one in fresh conversations; write each as a Zotero child note.

    Papers that already have a skim note are skipped unless --refresh. The notebook's existing
    conversation is saved as a notebook note before it is replaced.
    """

    def confirm() -> bool:
        if yes:
            return True
        if not stdin_is_interactive():
            click.echo("Not an interactive terminal; rerun with --yes to skim anyway.", err=True)
            return False
        return click.confirm("Continue?", default=False, err=True)

    try:
        report = notebook_skim.skim_notebook(
            ZoteroManager().client,
            notebook,
            list(keys),
            progress=lambda m: click.echo(m, err=True),
            focus=focus,
            refresh=refresh,
            confirm=confirm,
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

