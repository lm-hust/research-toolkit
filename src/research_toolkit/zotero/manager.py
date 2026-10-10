"""
src/research_toolkit/zotero/manager.py
ZoteroManager for personal library syncing, local PDF resolution, duplicate reconciliation,
and FulltextCheckpoint state transitions.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from research_toolkit.discovery.dedup import Deduplicator
from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.zotero.client import ZoteroClient
from research_toolkit.zotero.models import (
    CheckpointReport,
    SyncResult,
    ZoteroCollection,
    ZoteroItem,
)

logger = logging.getLogger(__name__)


class ZoteroManager:
    """Coordinates personal library collection sync, PDF resolution, and duplicate clustering."""

    def __init__(
        self,
        client: Optional[ZoteroClient] = None,
        storage_dir: Optional[Path] = None,
    ):
        self.client = client or ZoteroClient()
        default_storage = (
            Path("/app/data/storage")
            if Path("/app/data").exists()
            else (Path.home() / "Zotero" / "storage")
        )
        self.storage_dir = Path(storage_dir or os.getenv("ZOTERO_STORAGE_DIR") or default_storage)

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

    def resolve_attachment_pdf(
        self, attachment_key: str, auto_download_cloud: bool = True
    ) -> Optional[Path]:
        """
        Resolves local PDF attachment path. If missing on disk and auto_download_cloud is True,
        downloads the attachment file directly from Zotero Cloud Storage into the local cache.
        """
        local_path = self.find_local_pdf(attachment_key)
        if local_path:
            return local_path

        if not auto_download_cloud or not attachment_key:
            return None

        # CloudStorageResolver: Download directly from Zotero Cloud Storage into local cache
        target_file = self.storage_dir / attachment_key / f"{attachment_key}.pdf"
        return self.client.download_item_file(attachment_key, target_file)

    def get_or_create_collection(self, collection_name: str) -> ZoteroCollection:
        """Retrieves or creates a Zotero collection in the personal library."""
        return self.client.get_or_create_collection(collection_name)

    def sync_to_collection(
        self,
        collection_name: str,
        candidates: List[PaperCandidate],
        auto_download_oa: bool = True,
    ) -> Tuple[ZoteroCollection, SyncResult]:
        """
        Creates/gets collection and syncs candidates.
        If a paper already exists in the Zotero library (matched by canonical DOI or title),
        it appends the target collection to the existing item without creating duplicates.
        New papers are batch created with OA attachments.
        """
        collection = self.get_or_create_collection(collection_name)
        col_key = collection.key

        new_candidates: List[PaperCandidate] = []
        reused_items: List[Dict[str, Any]] = []

        for c in candidates:
            existing = self.client.find_existing_item(doi=c.doi, title=c.title)
            if existing:
                if self.client.add_item_to_collection(item=existing, collection_key=col_key):
                    reused_items.append(existing)
            else:
                new_candidates.append(c)

        created_items: List[Dict[str, Any]] = []
        if new_candidates:
            created_items = self.sync_candidates(
                collection_name=collection_name,
                candidates=new_candidates,
                auto_download_oa=auto_download_oa,
            )

        sync_result = SyncResult(
            collection_key=col_key,
            collection_name=collection.name,
            collection_url=collection.web_url,
            created_count=len(created_items),
            reused_count=len(reused_items),
            created_items=created_items,
            reused_items=reused_items,
        )
        return collection, sync_result

    def get_collection_candidates(self, collection_name: str) -> List[PaperCandidate]:
        """
        Retrieves all items from a collection and transforms them into domain PaperCandidates.
        Conforms to CODING_STANDARDS.md (encapsulated client access).
        """
        collection = self.client.get_or_create_collection(collection_name)
        items = self.client.get_collection_items(collection.key)
        candidates: List[PaperCandidate] = []
        for it in items:
            data = it.get("data", {})
            title = data.get("title") or "Untitled"
            doi = Deduplicator.clean_doi(data.get("DOI"))
            year_val = None
            date_str = data.get("date") or ""
            if date_str:
                match = re.search(r"\b(19\d\d|20\d\d)\b", date_str)
                if match:
                    year_val = int(match.group(1))
            candidates.append(
                PaperCandidate(
                    paper_id=it.get("key", title[:10]),
                    title=title,
                    year=year_val,
                    venue=data.get("publicationTitle") or "",
                    doi=doi,
                    topological_role="seed",
                )
            )
        return candidates

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

            # Publication type tag
            if c.is_preprint:
                tags.append({"tag": "type/preprint"})
            else:
                tags.append({"tag": "type/peer-reviewed"})

            # Cumulative citation tier tags
            cites = c.citation_count or 0
            if cites >= 10:
                tags.append({"tag": "cites:>10"})
            if cites >= 50:
                tags.append({"tag": "cites:>50"})
            if cites >= 100:
                tags.append({"tag": "cites:>100"})

            # Topological role tags
            if c.topological_role == "foundational":
                tags.append({"tag": "topo/foundational"})
            elif c.topological_role in ("recent_advancement", "sota"):
                tags.append({"tag": "topo/recent-advancement"})

            if c.co_citation_count > 0:
                tags.append({"tag": f"co-cites:>={c.co_citation_count}"})

            inf = c.influential_citation_count or 0
            score = c.composite_score or 0.0
            if c.co_citation_count > 0:
                extra_text = (
                    f"Citations: {cites} | Co-Cites: {c.co_citation_count} | "
                    f"Role: {c.topological_role} | Score: {score:.3f}"
                )
            else:
                extra_text = f"Citations: {cites} | Influential: {inf} | Score: {score:.3f}"

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
                "extra": extra_text,
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

    NON_PAPER_TYPES = frozenset({"attachment", "note", "annotation"})

    def list_fulltext_items(
        self, collection_key: str, auto_download_cloud: bool = True
    ) -> List[ZoteroItem]:
        """
        Lists the collection's papers (every key, no duplicate reconciliation) with their first
        resolvable PDF. Child notes and annotations are not papers.
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
            elif itype not in self.NON_PAPER_TYPES:
                tags = [t.get("tag", "") for t in data.get("tags", [])]
                parent_items[key] = ZoteroItem(
                    key=key,
                    title=data.get("title", "Untitled"),
                    doi=data.get("DOI"),
                    url=data.get("url"),
                    item_type=itype,
                    tags=tags,
                )

        # Associate PDF attachments with parent items (probing disk or resolving from cloud)
        for p_key, item in parent_items.items():
            for att in attachments.get(p_key, []):
                att_key = att.get("key", "")
                att_data = att.get("data", {})
                content_type = att_data.get("contentType", "")

                if "pdf" in content_type.lower() or att_data.get("filename", "").endswith(".pdf"):
                    item.attachment_key = att_key
                    resolved_pdf = self.resolve_attachment_pdf(
                        att_key, auto_download_cloud=auto_download_cloud
                    )
                    if resolved_pdf:
                        item.has_pdf = True
                        item.pdf_path = str(resolved_pdf)
                        break

        return list(parent_items.values())

    def scan_collection_checkpoint(
        self,
        collection_key: str,
        collection_name: str = "",
        auto_download_cloud: bool = True,
    ) -> CheckpointReport:
        """
        Scans a collection for full-text PDF attachments on disk (or resolves from Zotero Cloud)
        and partitions items into ready and missing sets.
        """
        parent_items = self.list_fulltext_items(
            collection_key, auto_download_cloud=auto_download_cloud
        )

        # Reconcile duplicates
        reconciled_items, dup_count = self.reconcile_duplicates(parent_items)

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
