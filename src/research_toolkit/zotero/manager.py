"""
src/research_toolkit/zotero/manager.py
ZoteroManager for personal library syncing, local PDF resolution, duplicate reconciliation,
and FulltextCheckpoint state transitions.
"""

from __future__ import annotations

import logging
import os
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from research_toolkit.discovery.dedup import Deduplicator
from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.zotero.client import ZoteroClient
from research_toolkit.zotero.models import CheckpointReport, ZoteroCollection, ZoteroItem

logger = logging.getLogger(__name__)


class ZoteroManager:
    """Coordinates personal library collection sync, PDF resolution, and duplicate clustering."""

    def __init__(
        self,
        client: Optional[ZoteroClient] = None,
        storage_dir: Optional[Path] = None,
    ):
        self.client = client or ZoteroClient()
        self.storage_dir = Path(
            storage_dir or os.getenv("ZOTERO_STORAGE_DIR") or (Path.home() / "Zotero" / "storage")
        )

    def find_local_pdf(self, attachment_key: str) -> Optional[Path]:
        """Probes ~/Zotero/storage/<attachment_key>/*.pdf directly on disk."""
        if not attachment_key or not self.storage_dir.exists():
            return None

        attach_dir = self.storage_dir / attachment_key
        if not attach_dir.is_dir():
            return None

        pdf_files = list(attach_dir.glob("*.pdf"))
        for pdf in pdf_files:
            if pdf.is_file() and pdf.stat().st_size > 0:
                return pdf
        return None

    def _parse_author_name(self, name_str: str) -> Dict[str, str]:
        parts = name_str.strip().split()
        if len(parts) > 1:
            return {"creatorType": "author", "firstName": " ".join(parts[:-1]), "lastName": parts[-1]}
        return {"creatorType": "author", "name": name_str}

    def sync_candidates(
        self,
        collection_name: str,
        candidates: List[PaperCandidate],
        auto_download_oa: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Inserts PaperCandidates into the personal library collection with canonical DOIs and tags.
        Downloads open-access PDFs if available and attaches them.
        """
        collection = self.client.get_or_create_collection(collection_name)
        col_key = collection.key

        items_payload: List[Dict[str, Any]] = []
        for c in candidates:
            clean_doi = Deduplicator.clean_doi(c.doi)
            creators = [self._parse_author_name(a) for a in c.authors] if c.authors else []
            tags = [{"tag": "checkpoint/awaiting-fulltext"}, {"tag": "research-toolkit"}]
            if c.is_review:
                tags.append({"tag": "type/review"})

            url = f"https://doi.org/{clean_doi}" if clean_doi else (c.pdf_url or "")

            item_data = {
                "itemType": "journalArticle",
                "title": c.title,
                "creators": creators,
                "abstractNote": c.abstract or "",
                "publicationTitle": c.venue or "",
                "date": str(c.year) if c.year else "",
                "DOI": clean_doi or "",
                "url": url,
                "tags": tags,
                "collections": [col_key],
            }
            items_payload.append(item_data)

        created_items = self.client.create_items(items_payload)

        # Handle Open Access PDF downloads/attachments
        if auto_download_oa:
            for idx, c in enumerate(candidates):
                if c.pdf_url and idx < len(created_items):
                    created = created_items[idx]
                    parent_key = created.get("key") if isinstance(created, dict) else None
                    if parent_key:
                        try:
                            self.client.create_attachment_link(
                                parent_key=parent_key,
                                title=f"{c.title} - Full Text PDF",
                                url=c.pdf_url,
                            )
                        except Exception as e:
                            logger.warning("Failed to link OA PDF for %s: %s", c.title, e)

        return created_items

    def reconcile_duplicates(self, items: List[ZoteroItem]) -> Tuple[List[ZoteroItem], int]:
        """
        Clusters items by canonical DOI or normalized title.
        Adopts the entry with a valid PDF attachment as the winner.
        """
        clusters: Dict[str, List[ZoteroItem]] = {}
        no_id_items: List[ZoteroItem] = []

        for item in items:
            clean_doi = Deduplicator.clean_doi(item.doi)
            if clean_doi:
                clusters.setdefault(f"doi:{clean_doi}", []).append(item)
            elif item.title:
                norm_title = Deduplicator.clean_title(item.title)
                clusters.setdefault(f"title:{norm_title}", []).append(item)
            else:
                no_id_items.append(item)

        reconciled: List[ZoteroItem] = []
        duplicate_count = 0

        for key, cluster in clusters.items():
            if len(cluster) == 1:
                reconciled.append(cluster[0])
            else:
                duplicate_count += len(cluster) - 1
                # Winner selection: prioritize item with valid PDF
                with_pdf = [it for it in cluster if it.has_pdf]
                if with_pdf:
                    winner = with_pdf[0]
                else:
                    winner = cluster[0]

                # Merge tags across duplicates
                merged_tags = set(winner.tags)
                for it in cluster:
                    merged_tags.update(it.tags)
                winner.tags = sorted(list(merged_tags))

                # Normalize DOI on winner
                if winner.doi:
                    winner.doi = Deduplicator.clean_doi(winner.doi)

                reconciled.append(winner)

        reconciled.extend(no_id_items)
        return reconciled, duplicate_count

    def scan_collection_checkpoint(
        self, collection_key: str, collection_name: str = ""
    ) -> CheckpointReport:
        """
        Scans a collection for full-text PDF attachments on disk and partitions
        items into ready and missing sets.
        """
        raw_items = self.client.get_collection_items(collection_key)

        parent_items: Dict[str, ZoteroItem] = {}
        attachments: Dict[str, List[Dict[str, Any]]] = {}

        for raw in raw_items:
            key = raw.get("key", "")
            data = raw.get("data", {})
            itype = data.get("itemType", "")

            if itype == "attachment":
                parent_k = data.get("parentItem")
                if parent_k:
                    attachments.setdefault(parent_k, []).append(raw)
            else:
                doi = data.get("DOI")
                url = data.get("url")
                title = data.get("title", "Untitled")
                tags = [t.get("tag", "") for t in data.get("tags", [])]
                parent_items[key] = ZoteroItem(
                    key=key,
                    title=title,
                    doi=doi,
                    url=url,
                    item_type=itype,
                    tags=tags,
                )

        # Associate PDF attachments with parent items
        for p_key, item in parent_items.items():
            child_attachments = attachments.get(p_key, [])
            for att in child_attachments:
                att_key = att.get("key", "")
                att_data = att.get("data", {})
                content_type = att_data.get("contentType", "")

                if "pdf" in content_type.lower() or att_data.get("filename", "").endswith(".pdf"):
                    item.attachment_key = att_key
                    local_pdf = self.find_local_pdf(att_key)
                    if local_pdf:
                        item.has_pdf = True
                        item.pdf_path = str(local_pdf)
                        break

        # Reconcile duplicates
        reconciled_items, dup_count = self.reconcile_duplicates(list(parent_items.values()))

        ready_items = [it for it in reconciled_items if it.has_pdf]
        missing_items = [it for it in reconciled_items if not it.has_pdf]

        return CheckpointReport(
            collection_key=collection_key,
            collection_name=collection_name or collection_key,
            total_items=len(reconciled_items),
            ready_items=ready_items,
            missing_items=missing_items,
            reconciled_duplicates=dup_count,
        )

    def format_checkpoint_report(self, report: CheckpointReport) -> str:
        """Formats the checkpoint report into a structured terminal view."""
        lines: List[str] = [
            "=" * 70,
            f"📋 FULLTEXT CHECKPOINT REPORT: '{report.collection_name}'",
            "=" * 70,
            f"Total unique papers : {report.total_items}",
            f"Ready on disk (PDF) : {len(report.ready_items)}/{report.total_items}",
            f"Reconciled duplicate: {report.reconciled_duplicates}",
            "-" * 70,
        ]

        if report.ready_items:
            lines.append("\n✅ Ready for NotebookLM Ingestion:")
            for item in report.ready_items:
                path_info = f" ({item.pdf_path})" if item.pdf_path else ""
                lines.append(f"  • {item.title[:60]}{path_info}")

        if report.missing_items:
            lines.append(f"\n⚠️ Missing PDFs ({len(report.missing_items)}):")
            lines.append("  Use standard DOI links below in your browser with Zotero Connector:")
            for item in report.missing_items:
                lines.append(f"  • Title: {item.title}")
                if item.doi:
                    clean_doi = Deduplicator.clean_doi(item.doi)
                    lines.append(f"    DOI: {clean_doi}")
                    lines.append(f"    URL: https://doi.org/{clean_doi}")
                elif item.url:
                    lines.append(f"    URL: {item.url}")
            lines.append("\n👉 Action Required:")
            lines.append("  1. Open the DOI URL in your browser to access the publication.")
            lines.append("  2. Click Zotero Connector to save the full text into your collection.")
            lines.append("  3. Run `research-toolkit checkpoint` to re-verify.")
        else:
            lines.append("\n✨ All PDFs are resolved and ready on disk!")
            lines.append("  Run `research-toolkit sync-notebook` to synthesize in NotebookLM.")

        lines.append("=" * 70)
        return "\n".join(lines)
