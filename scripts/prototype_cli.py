#!/usr/bin/env python3
"""
scripts/prototype_cli.py - Runnable CLI prototype demonstrating staged workflow
and FulltextCheckpoint state transitions.
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional

STATE_FILE = Path.home() / ".cache" / "research-toolkit" / "prototype_state.json"
UCL_PROXY_PREFIX = "https://libproxy.ucl.ac.uk/login?url=https://doi.org/"


@dataclass
class PaperItem:
    key: str
    title: str
    doi: str
    is_review: bool
    has_pdf: bool
    pdf_source: Optional[str] = None
    is_reconciled: bool = False


@dataclass
class SessionState:
    stage: str
    collection_name: str
    papers: List[PaperItem]
    notebook_id: Optional[str] = None
    duplicates_reconciled: int = 0


def load_state() -> SessionState:
    if not STATE_FILE.exists():
        return SessionState(stage="IDLE", collection_name="", papers=[])
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        papers = [PaperItem(**p) for p in data.get("papers", [])]
        return SessionState(
            stage=data.get("stage", "IDLE"),
            collection_name=data.get("collection_name", ""),
            papers=papers,
            notebook_id=data.get("notebook_id"),
            duplicates_reconciled=data.get("duplicates_reconciled", 0),
        )
    except Exception:
        return SessionState(stage="IDLE", collection_name="", papers=[])


def save_state(state: SessionState) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": state.stage,
        "collection_name": state.collection_name,
        "papers": [asdict(p) for p in state.papers],
        "notebook_id": state.notebook_id,
        "duplicates_reconciled": state.duplicates_reconciled,
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def cmd_search(args) -> None:
    topic = args.topic
    print(f"\n🔍 [Discovery] Searching Semantic Scholar and OpenAlex for: '{topic}'...")
    print("📊 [Ranker] Applying composite scoring (relevance 0.40, citation velocity 0.35, venue 0.25, review bonus)...")
    print("🌟 [Stratified Selection] Review paper reserved at Rank #1.")

    col_name = f"research/{topic.lower().replace(' ', '-')}"
    papers = [
        PaperItem(
            key="ZOT01",
            title="A Comprehensive Survey on Graph Neural Networks (2024)",
            doi="10.1109/tpami.2024.101234",
            is_review=True,
            has_pdf=True,
            pdf_source="OpenAlex Open Access",
        ),
        PaperItem(
            key="ZOT02",
            title="Geometric Deep Learning: Grids, Groups, Graphs, Geodesics",
            doi="10.1038/s41586-021-03819-2",
            is_review=False,
            has_pdf=False,  # Paywalled
            pdf_source=None,
        ),
        PaperItem(
            key="ZOT03",
            title="Relational Inductive Biases, Deep Learning, and Graph Networks",
            doi="10.48550/arXiv.1806.01261",
            is_review=False,
            has_pdf=True,
            pdf_source="ArXiv Open Access",
        ),
    ]

    print(f"\n📁 [Zotero] Created/Verified collection: '{col_name}'")
    print(f"💾 [Zotero] Inserted {len(papers)} PaperCandidate items with tag 'checkpoint/awaiting-fulltext'.")

    state = SessionState(
        stage="CHECKPOINT_PENDING",
        collection_name=col_name,
        papers=papers,
        duplicates_reconciled=0,
    )
    save_state(state)

    print("\n" + "=" * 70)
    print("🛑 FULLTEXT CHECKPOINT REACHED")
    print("=" * 70)
    print(f"Collection: {col_name}")
    print("PDF Status: 2/3 verified locally.")
    print("Missing PDF (1):")
    print(f"  • Title: 'Geometric Deep Learning...'")
    print(f"  • DOI: 10.1038/s41586-021-03819-2")
    print(f"  • UCL EZproxy Link: {UCL_PROXY_PREFIX}10.1038/s41586-021-03819-2")
    print("\n👉 Action Required:")
    print("  1. Click the UCL link above to authenticate via UCL Single Sign-On.")
    print("  2. In your browser, click Zotero Connector to save the full text PDF into Zotero.")
    print("  3. Run `python3 scripts/prototype_cli.py checkpoint` to verify, or `sync-notebook`.")


def cmd_checkpoint(args) -> None:
    state = load_state()
    if state.stage == "IDLE":
        print("No active search session. Run `search` first.")
        return

    print(f"\n📋 [FulltextCheckpoint] Collection: '{state.collection_name}'")
    ready = [p for p in state.papers if p.has_pdf]
    pending = [p for p in state.papers if not p.has_pdf]

    print(f"✅ Ready on disk: {len(ready)}/{len(state.papers)}")
    for p in ready:
        tag = "[REVIEW]" if p.is_review else "[RESEARCH]"
        src = f"({p.pdf_source})" if p.pdf_source else ""
        print(f"   • {tag} {p.title[:50]}... {src}")

    if pending:
        print(f"\n⚠️ Pending PDFs: {len(pending)}")
        for p in pending:
            print(f"   • {p.title}")
            print(f"     DOI: {p.doi}")
            print(f"     🔗 UCL Proxy: {UCL_PROXY_PREFIX}{p.doi}")
    else:
        print("\n✨ All PDFs are ready! You can now run `sync-notebook`.")


def cmd_resolve(args) -> None:
    """Simulates user clicking UCL link and using Zotero Connector."""
    target_doi = args.doi.lower().strip()
    state = load_state()
    matched = False
    for p in state.papers:
        if p.doi.lower() == target_doi:
            p.has_pdf = True
            p.pdf_source = "UCL Institutional Access (via Zotero Connector)"
            p.is_reconciled = True
            matched = True
            state.duplicates_reconciled += 1
            break

    if matched:
        print(f"⚡ [Simulate Zotero Connector] Captured item and full PDF for DOI: {target_doi}")
        print("🔄 [Reconciler] Duplicate entry clustered by DOI: merged into collection.")
        if all(p.has_pdf for p in state.papers):
            state.stage = "CHECKPOINT_READY"
        save_state(state)
        print("✅ Paper marked READY. Run `sync-notebook` to proceed.")
    else:
        print(f"❌ DOI {target_doi} not found in active collection.")


def cmd_sync_notebook(args) -> None:
    state = load_state()
    if not state.papers:
        print("No papers in collection. Run `search` first.")
        return

    ready_papers = [p for p in state.papers if p.has_pdf]
    pending_papers = [p for p in state.papers if not p.has_pdf]

    if pending_papers and not args.allow_partial:
        print(f"\n❌ [Checkpoint Blocked] {len(pending_papers)} paper(s) still lack full-text PDFs.")
        print("Use --allow-partial to proceed with only available papers, or resolve missing PDFs.")
        for p in pending_papers:
            print(f"  • {p.title} -> {UCL_PROXY_PREFIX}{p.doi}")
        return

    print(f"\n🚀 [NotebookLM Gateway] Connecting via `notebooklm-py`...")
    nb_title = f"Research: {state.collection_name}"
    nb_id = f"nb_{os.urandom(4).hex()}"
    print(f"📓 [NotebookLM] Created Notebook: '{nb_title}' (ID: {nb_id})")

    for i, p in enumerate(ready_papers, 1):
        print(f"   [{i}/{len(ready_papers)}] Uploading PDF source: '{p.title[:45]}...' -> NotebookSource created")

    state.notebook_id = nb_id
    state.stage = "SYNCED"
    save_state(state)

    print(f"\n🎉 [Success] Uploaded {len(ready_papers)} sources to Google NotebookLM!")
    print(f"💡 You can now query your notebook: `python3 scripts/prototype_cli.py ask 'Your question'`")


def cmd_ask(args) -> None:
    state = load_state()
    if not state.notebook_id:
        print("Notebook not synced yet. Run `sync-notebook` first.")
        return

    prompt = args.query
    print(f"\n💬 [Grounded Query] Asking NotebookLM ({state.notebook_id}): '{prompt}'")
    print("-" * 70)
    print("🤖 [NotebookLM Synthesis]:")
    print("Based on the 3 uploaded sources, the core advancements in Graph Neural Networks include:")
    print("1. Relational Inductive Biases [1]: Exploiting permutational invariance across nodes.")
    print("2. Geometric Deep Learning [2]: Unifying CNNs and GNNs through symmetry groups and gauge transformations.")
    print("\n📚 [DistilledEvidence Extracted]:")
    print("  • [1] Source: 'Relational Inductive Biases' (Offset 1420-1580)")
    print("        Quote: \"Relational inductive biases constrain how entities interact over graphs.\"")
    print("  • [2] Source: 'Geometric Deep Learning' (Offset 310-440)")
    print("        Quote: \"Symmetry groups provide a unifying geometric blueprint for representation learning.\"")
    print("-" * 70)
    print("📌 Ready for Obsidian PKM ingestion into `/home/ling/vault/PKM/90-staging/`.")


def main():
    parser = argparse.ArgumentParser(description="Research Toolkit CLI Prototype")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search and insert into Zotero")
    p_search.add_argument("topic", help="Topic keywords")

    p_check = sub.add_parser("checkpoint", help="Check FulltextCheckpoint status")

    p_res = sub.add_parser("resolve", help="Simulate Zotero Connector resolving a DOI")
    p_res.add_argument("doi", help="DOI to resolve")

    p_sync = sub.add_parser("sync-notebook", help="Upload ready PDFs to NotebookLM")
    p_sync.add_argument("--allow-partial", action="store_true", help="Allow syncing with partial PDFs")

    p_ask = sub.add_parser("ask", help="Query grounded sources in NotebookLM")
    p_ask.add_argument("query", help="Question prompt")

    args = parser.parse_args()
    if args.cmd == "search":
        cmd_search(args)
    elif args.cmd == "checkpoint":
        cmd_checkpoint(args)
    elif args.cmd == "resolve":
        cmd_resolve(args)
    elif args.cmd == "sync-notebook":
        cmd_sync_notebook(args)
    elif args.cmd == "ask":
        cmd_ask(args)


if __name__ == "__main__":
    main()
