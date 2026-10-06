"""
src/research_toolkit/cli.py
Main command-line interface for the Research Toolkit.
"""

from __future__ import annotations

import sys
import click

from research_toolkit.discovery.service import DiscoveryService


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
def search(topic: str, limit: int, dry_run: bool) -> None:
    """Search literature and rank candidates across Semantic Scholar and OpenAlex."""
    click.echo(f"Searching literature for: '{topic}'...")
    service = DiscoveryService()
    candidates = service.search_and_rank(topic, top_k=limit)

    if not candidates:
        click.echo("No matching papers found.")
        return

    table_output = service.format_table(candidates)
    click.echo(table_output)

    if dry_run:
        click.echo(
            f"\n[dry-run] Discovered and ranked {len(candidates)} papers. No changes committed."
        )
    else:
        click.echo(
            f"\nDiscovered {len(candidates)} papers. Use Zotero sync to save papers to collection."
        )


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
