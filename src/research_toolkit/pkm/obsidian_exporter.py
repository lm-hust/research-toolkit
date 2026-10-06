"""
src/research_toolkit/pkm/obsidian_exporter.py
Obsidian PKM Vault export adapter conforming to 50-meta/conversation-memory-protocol.md
and ADR-0002.
"""

from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

DEFAULT_VAULT_DIR = Path("/home/ling/vault/PKM")


@dataclass
class PaperScreenData:
    title: str
    authors: List[str]
    year: Optional[int]
    doi: Optional[str]
    zotero_key: str
    zotero_pdf_key: Optional[str]
    abstract: str
    is_review: bool
    user_id: str
    project_slug: Optional[str] = None
    tags: List[str] = field(default_factory=lambda: ["visibility/internal"])


@dataclass
class MemoryCandidateData:
    title: str
    candidate_conclusion: str
    worth_saving_for: str
    confirmed_facts: List[str]
    user_decisions: List[str]
    inferred_items: List[str]
    unconfirmed_items: List[str]
    evidences: List[Tuple[str, str]]  # List of (source_title, verbatim_quote)
    source_description: str
    suggested_target: str = "30-projects/..."
    project_slug: Optional[str] = None


class ObsidianExporter:
    """
    Exports paper cards and distilled evidence candidates into the local Obsidian Vault.
    Strictly uses Zotero Personal Library (users/<user_id>) URIs.
    """

    def __init__(self, vault_dir: Optional[Path] = None, user_id: Optional[str] = None):
        self.vault_dir = Path(vault_dir or os.getenv("OBSIDIAN_VAULT_DIR") or DEFAULT_VAULT_DIR).expanduser()
        self.user_id = user_id or os.getenv("ZOTERO_USER_ID", "default_user")

    @staticmethod
    def slugify_short_title(title: str, max_words: int = 4) -> str:
        """Create clean short title for YYYY-Author-ShortTitle.md filename."""
        clean = re.sub(r"[^\w\s-]", "", title)
        words = clean.strip().split()
        short = " ".join(words[:max_words])
        return short[:30].strip()

    @staticmethod
    def extract_first_author_lastname(authors: List[str]) -> str:
        if not authors:
            return "Anonymous"
        first = authors[0].strip()
        # Handle "Last, First" or "First Last"
        if "," in first:
            return first.split(",")[0].strip()
        parts = first.split()
        return parts[-1].strip() if parts else "Anonymous"

    def build_paper_filename(self, year: Optional[int], authors: List[str], title: str) -> str:
        y = str(year) if year else "ND"
        author = self.extract_first_author_lastname(authors)
        short_title = self.slugify_short_title(title)
        return f"{y}-{author}-{short_title}.md"

    def export_paper_screen(self, data: PaperScreenData, dry_run: bool = False) -> Path:
        """
        Exports a paper-screen card into 10-wiki/References/papers/YYYY-FirstAuthor-ShortTitle.md
        """
        dest_dir = self.vault_dir / "10-wiki" / "References" / "papers"
        filename = self.build_paper_filename(data.year, data.authors, data.title)
        target_path = dest_dir / filename

        today = datetime.date.today().strftime("%Y-%m-%d")
        method_type = "review" if data.is_review else "statistical"

        # Format authors block
        authors_yaml = "\n".join(f"  - {a}" for a in data.authors) if data.authors else "  - Anonymous"

        # Format projects block
        projects_yaml = ""
        if data.project_slug:
            projects_yaml = f'\nprojects:\n  - "[[30-projects/{data.project_slug}/project-overview|{data.project_slug}]]"'
        else:
            projects_yaml = "\nprojects: []"

        # Zotero personal library links (STRICTLY users/<user_id>)
        uid = data.user_id or self.user_id
        zotero_item_link = f"zotero://select/users/{uid}/items/{data.zotero_key}"
        zotero_pdf_link = (
            f"zotero://open-pdf/users/{uid}/items/{data.zotero_pdf_key}"
            if data.zotero_pdf_key
            else "尚未获取全文"
        )

        content = f"""---
schema_version: 1
title: "{data.title}"
aliases: []
citekey: ""
type: paper
read_depth: screen
screen_verdict: ""           # 纳入精读 / 备用 / 排除
processed_by: research-toolkit
processed_at: {today}
zotero_key: {data.zotero_key}
zotero_pdf_key: {data.zotero_pdf_key or ""}
year: {data.year or ""}
doi: "{data.doi or ''}"
authors:
{authors_yaml}
facility: []
climate: []
mechanism: []
method: "{method_type}"
has_quant:
tags:
  - visibility/internal
sources: []
related: []{projects_yaml}
confidence: low
review_after:
---

# {data.title}

> [!summary] 筛选级摘要
> 【核心内容】{data.abstract[:400] if data.abstract else "暂无摘要"}
> 【数据类型】实测 / 统计 / 仿真 / 综述二手
> 【筛选判定】待精读
> 【存疑/局限】^[ambiguous]

## Zotero 原文（个人库）
- [PDF 全文]({zotero_pdf_link})
- [条目详情]({zotero_item_link})

## 相关页面
"""

        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            self._append_audit_log(f"Created paper-screen card: `10-wiki/References/papers/{filename}`")

        return target_path

    def export_memory_candidate(self, data: MemoryCandidateData, dry_run: bool = False) -> Path:
        """
        Exports synthesized takeaways and verbatim quotes into 90-staging/<slug>.md
        """
        dest_dir = self.vault_dir / "90-staging"
        slug = re.sub(r"[^\w-]", "", data.title.lower().replace(" ", "-"))[:40]
        filename = f"{slug}.md"
        target_path = dest_dir / filename

        today = datetime.date.today().strftime("%Y-%m-%d")

        facts_md = "\n".join(f"- {f}" for f in data.confirmed_facts) if data.confirmed_facts else "- 暂无"
        decisions_md = "\n".join(f"- {d}" for d in data.user_decisions) if data.user_decisions else "- 暂无"
        inferred_md = "\n".join(f"- {i} ^[inferred]" for i in data.inferred_items) if data.inferred_items else "- 暂无"
        unconfirmed_md = (
            "\n".join(f"- {u} ^[ambiguous]" for u in data.unconfirmed_items)
            if data.unconfirmed_items
            else "- 暂无"
        )

        evidences_md = ""
        if data.evidences:
            evidences_md = "\n### 逐字引文与证据 (Grounding)\n"
            for src, quote in data.evidences:
                evidences_md += f"> \"{quote}\"\n> — 摘自《{src}》\n\n"

        project_link = (
            f"[[30-projects/{data.project_slug}/project-overview|{data.project_slug}]]"
            if data.project_slug
            else ""
        )

        content = f"""---
schema_version: 1
title: "{data.title}"
type: source
status: draft
summary: "由 Research Toolkit (NotebookLM) 提取的候选知识包；确认前不进入正式知识层。"
created: "{today}"
updated: "{today}"
tags: [visibility/internal]
sources: []
related: [{f'"{project_link}"' if project_link else ""}]
origin: "research-toolkit"
candidate_for: []
confidence: medium
review_after:
---

# {data.title}

## 一句话候选结论
{data.candidate_conclusion}

## 为什么值得保存
{data.worth_saving_for}

## 已确认事实
{facts_md}
{evidences_md}
## 用户决策
{decisions_md}

## 推断与未确认项
{inferred_md}
{unconfirmed_md}

## 来源
{data.source_description}

## 建议去向
- [ ] Hermes 内置 Memory
- [x] `{data.suggested_target}`
- [ ] `10-wiki/...`

## 用户确认
- 状态：待确认
- 确认日期：
- 确认动作：写入 / 修改后写入 / 删除
"""

        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            self._append_audit_log(f"Created memory-candidate packet: `90-staging/{filename}`")

        return target_path

    def _append_audit_log(self, action_msg: str) -> None:
        """Appends action line to /home/ling/vault/PKM/log.md."""
        log_file = self.vault_dir / "log.md"
        if not log_file.exists():
            return
        today = datetime.date.today().strftime("%Y-%m-%d")
        now = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"\n- `{today} {now}` [research-toolkit] {action_msg}"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass
