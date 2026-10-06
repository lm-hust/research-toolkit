"""
src/research_toolkit/cli.py
Main command-line interface for the Research Toolkit.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import click

from research_toolkit.discovery.service import DiscoveryService
from research_toolkit.zotero.manager import ZoteroManager

logger = logging.getLogger(__name__)

STATE_FILE = Path.home() / ".cache" / "research-toolkit" / "session.json"


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
@click.argument("topic")
@click.option(
    "--limit",
    "-k",
    default=8,
    type=int,
    help="Number of top papers to discover and rank (default: 8).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Perform discovery and ranking dry-run without writing to Zotero.",
)
@click.option(
    "--sync-zotero",
    is_flag=True,
    default=False,
    help="Automatically insert ranked candidates into Zotero personal library collection.",
)
def search(topic: str, limit: int, dry_run: bool, sync_zotero: bool) -> None:
    """Search literature and rank candidates across Semantic Scholar and OpenAlex."""
    click.echo(f"Searching literature for: '{topic}'...")
    service = DiscoveryService()
    candidates = service.search_and_rank(topic, top_k=limit)

    if not candidates:
        click.echo("No matching papers found.")
        return

    table_output = service.format_table(candidates)
    click.echo(table_output)

    col_name = f"research/{topic.lower().replace(' ', '-')}"

    if dry_run:
        click.echo(
            f"\n[dry-run] Discovered and ranked {len(candidates)} papers. No changes committed."
        )
        return

    if sync_zotero:
        click.echo(f"\n📁 Syncing to Zotero personal library collection: '{col_name}'...")
        zotero_mgr = ZoteroManager()
        created = zotero_mgr.sync_candidates(col_name, candidates)
        save_session({"active_collection": col_name, "topic": topic})
        click.echo(f"💾 Successfully inserted {len(created)} items into '{col_name}'.")
        click.echo("Run `research-toolkit checkpoint` to verify local full-text PDFs.")
    else:
        save_session({"last_search_topic": topic})
        click.echo(
            f"\nDiscovered {len(candidates)} papers. Pass `--sync-zotero` to insert into your personal Zotero library."
        )


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


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
