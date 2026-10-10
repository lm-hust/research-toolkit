"""
tests/test_skim_notebook_cli.py
skim-notebook through the CLI, with the in-memory notebook client and fake Zotero library.
"""

import datetime
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import notebooklm
from click.testing import CliRunner, Result
from notebook_fakes import OPEN_CLIENT, FakeNotebookClient
from notebooklm import ChatReference
from zotero_fakes import FakeZoteroLibrary

from research_toolkit.cli import cli

NOTEBOOK = "intelligence-per-kwh"
ANSWER = """## 研究问题与动机
训练大模型的能耗被低估 [1]。

## 方法与数据
- 测量 GPU 功耗
- 估算碳排放 [2]

## 主要结论
训练一次 BERT 排放约 1438 lbs CO2 [2]。

## 局限
只测了少数模型。

## 复现或深读价值
值得深读。"""


class SkimNotebookCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.zotero = FakeZoteroLibrary(self.tmp / "storage")
        self.fake = FakeNotebookClient()
        self.nb_id = self.fake.add_notebook(
            NOTEBOOK,
            ["[K1] Energy and Policy Considerations", "[K2] Green AI", "Hand-added notes"],
        )
        self.k1_source, self.k2_source = (s.id for s in self.fake.state[self.nb_id].sources[:2])

    def run_skim(self, *args: str) -> Result:
        with patch(OPEN_CLIENT, self.fake.open), patch(
            "research_toolkit.cli.ZoteroManager", self.zotero.manager
        ):
            return CliRunner().invoke(cli, ["skim-notebook", *args])

    def report(self, result: Result) -> dict[str, Any]:
        self.assertEqual(result.exit_code, 0, result.output)
        return json.loads(result.stdout)

    def test_skim_writes_a_tagged_zotero_note_with_metadata_and_cited_text(self) -> None:
        self.fake.answers[self.k1_source] = (
            ANSWER,
            [
                ChatReference(source_id=self.k1_source, citation_number=1, cited_text="Energy use is <underestimated>."),
                ChatReference(source_id=self.k1_source, citation_number=2, cited_text="BERT emits 1438 lbs.", start_char=5, end_char=25),
                ChatReference(source_id=self.k1_source, citation_number=3, cited_text=None),
            ],
        )

        report = self.report(self.run_skim("--notebook", NOTEBOOK, "--key", "K1"))

        [note] = self.zotero.created_notes
        self.assertEqual(note["parentItem"], "K1")
        self.assertEqual(note["tags"], ["gemini-skim/ai-note"])
        html = note["note"]
        self.assertTrue(html.startswith("<h1>Gemini 初读：Energy and Policy Considerations</h1>"))
        header = html.split("</p>", 1)[0]
        self.assertIn(self.nb_id, header)
        self.assertIn(self.k1_source, header)
        self.assertIn(datetime.date.today().isoformat(), header)
        self.assertIn(f"notebooklm-py {notebooklm.__version__}", header)
        self.assertIn("<h2>主要结论</h2>", html)
        self.assertIn("1438 lbs CO2", html)
        self.assertIn("<li>测量 GPU 功耗</li>", html)
        self.assertIn("[1] Energy use is &lt;underestimated&gt;.", html)
        self.assertIn("[2] BERT emits 1438 lbs.", html)
        self.assertNotIn("[3]", html)
        self.assertNotIn("页", html.split("出处", 1)[1])

        self.assertEqual(report["notebook_id"], self.nb_id)
        self.assertEqual(
            report["written"],
            [{"key": "K1", "title": "Energy and Policy Considerations", "source_id": self.k1_source, "note_key": note["key"]}],
        )
        self.assertEqual(report["failed"], [])
        self.assertFalse(report["saved_history_note"])

    def test_nested_bullets_and_inline_code_keep_their_structure(self) -> None:
        self.fake.answers[self.k1_source] = (
            "## 方法与数据\n* **模型**：\n    * 特定任务模型\n    * 通用模型 `bloomz-7b`\n* 硬件：A100",
            [],
        )

        self.report(self.run_skim("--notebook", NOTEBOOK, "--key", "K1"))

        html = self.zotero.created_notes[0]["note"]
        self.assertIn(
            "<ul><li><strong>模型</strong>：<ul><li>特定任务模型</li>"
            "<li>通用模型 <code>bloomz-7b</code></li></ul></li><li>硬件：A100</li></ul>",
            html,
        )

    def test_ask_is_restricted_to_the_paper_and_asks_for_the_five_sections(self) -> None:
        self.report(self.run_skim("--notebook", NOTEBOOK, "--key", "K1"))

        [ask] = [w for w in self.fake.writes if w[0] == "ask"]
        self.assertEqual(ask[2], (self.k1_source,))
        [(question, _)] = self.fake.history(self.nb_id)
        for section in ["研究问题与动机", "方法与数据", "主要结论", "局限", "复现或深读价值"]:
            self.assertIn(section, question)

    # --- the user's existing conversation must never be lost ---------------
    def test_existing_conversation_is_saved_as_a_note_before_it_is_deleted(self) -> None:
        original = self.fake.start_conversation(
            self.nb_id, [("What is PUE?", "Power usage effectiveness."), ("And WUE?", "Water.")]
        )

        report = self.report(self.run_skim("--notebook", NOTEBOOK, "--key", "K1"))

        self.assertTrue(report["saved_history_note"])
        [saved] = self.fake.state[self.nb_id].notes
        self.assertIn("**Q:** What is PUE?", saved.content)
        self.assertIn("**A:** Water.", saved.content)
        self.assertLess(saved.content.index("PUE"), saved.content.index("WUE"))
        kinds = [w[0] for w in self.fake.writes]
        self.assertLess(kinds.index("create_note"), kinds.index("delete_conversation"))
        self.assertIn(("delete_conversation", self.nb_id, original), self.fake.writes)
        self.assertNotIn("What is PUE?", [q for q, _ in self.fake.history(self.nb_id)])

    def test_when_saving_fails_nothing_is_deleted_or_asked(self) -> None:
        original = self.fake.start_conversation(self.nb_id, [("Keep me", "Please")])
        self.fake.note_errors = RuntimeError("notes API down")

        result = self.run_skim("--notebook", NOTEBOOK, "--key", "K1")

        self.assertEqual(result.exit_code, 1)
        self.assertIn("nothing was deleted", result.stderr)
        self.assertEqual(self.fake.conversation_id(self.nb_id), original)
        self.assertEqual(self.fake.history(self.nb_id), [("Keep me", "Please")])
        self.assertEqual([w[0] for w in self.fake.writes], ["create_note"])
        self.assertEqual(self.zotero.created_notes, [])

    def test_a_history_too_long_to_save_whole_is_not_deleted(self) -> None:
        self.fake.start_conversation(self.nb_id, [(f"q{i}", f"a{i}") for i in range(1000)])

        result = self.run_skim("--notebook", NOTEBOOK, "--key", "K1")

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(len(self.fake.history(self.nb_id)), 1000)
        self.assertEqual(self.fake.writes, [])

    def test_each_paper_gets_a_fresh_conversation_and_only_the_original_is_saved(self) -> None:
        self.fake.start_conversation(self.nb_id, [("old", "turn")])

        report = self.report(self.run_skim("--notebook", NOTEBOOK, "--key", "K1", "--key", "K2"))

        self.assertEqual([e["key"] for e in report["written"]], ["K1", "K2"])
        self.assertEqual(len(self.fake.state[self.nb_id].notes), 1)
        asks = [w for w in self.fake.writes if w[0] == "ask"]
        self.assertEqual([a[2] for a in asks], [(self.k1_source,), (self.k2_source,)])
        self.assertEqual([a[3] for a in asks], [None, None])
        self.assertEqual(len([w for w in self.fake.writes if w[0] == "delete_conversation"]), 2)
        self.assertEqual(len(self.fake.history(self.nb_id)), 1)  # only K2's turn remains

    def test_no_conversation_means_nothing_saved_or_deleted(self) -> None:
        report = self.report(self.run_skim("--notebook", NOTEBOOK, "--key", "K1"))

        self.assertFalse(report["saved_history_note"])
        self.assertNotIn("delete_conversation", [w[0] for w in self.fake.writes])
        self.assertEqual(self.fake.state[self.nb_id].notes, [])

    # --- failures ------------------------------------------------------------
    def test_failures_are_reported_and_do_not_stop_the_run(self) -> None:
        self.fake.ask_errors[self.k1_source] = RuntimeError("chat timed out")
        self.zotero.note_errors["K2"] = RuntimeError("Zotero 403")

        report = self.report(
            self.run_skim("--notebook", NOTEBOOK, "--key", "NOPE", "--key", "K1", "--key", "K2")
        )

        self.assertEqual(report["written"], [])
        failed = {f["key"]: f["error"] for f in report["failed"]}
        self.assertIn("NOPE", failed["NOPE"])
        self.assertEqual(failed["K1"], "chat timed out")
        self.assertEqual(failed["K2"], "Zotero 403")

    def test_unknown_notebook_is_an_error(self) -> None:
        result = self.run_skim("--notebook", "nope", "--key", "K1")

        self.assertEqual(result.exit_code, 1)
        self.assertIn("nope", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.fake.writes, [])


FOCUS = "数据中心能效如何影响 AI 碳排放"
RELEVANCE_TAG = "gemini-skim/relevance:"


class SkimRelevanceTest(unittest.TestCase):
    """`--focus` asks for relevance, writes it into the note and tags the Zotero item."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.zotero = FakeZoteroLibrary(self.tmp / "storage")
        self.fake = FakeNotebookClient()
        self.nb_id = self.fake.add_notebook(NOTEBOOK, ["[K1] Energy and Policy Considerations", "[K2] Green AI"])
        self.k1_source, self.k2_source = (s.id for s in self.fake.state[self.nb_id].sources)

    def run_skim(self, *args: str) -> dict[str, Any]:
        with patch(OPEN_CLIENT, self.fake.open), patch(
            "research_toolkit.cli.ZoteroManager", self.zotero.manager
        ):
            result = CliRunner().invoke(cli, ["skim-notebook", "--notebook", NOTEBOOK, *args])
        self.assertEqual(result.exit_code, 0, result.output)
        report: dict[str, Any] = json.loads(result.stdout)
        return report

    def answer_with_relevance(self, source_id: str, relevance_section: str) -> None:
        self.fake.answers[source_id] = (f"{ANSWER}\n\n## 与研究问题的相关性\n{relevance_section}", [])

    def relevance_tags(self, key: str) -> list[str]:
        return [t["tag"] for t in self.zotero.item_tags.get(key, []) if t["tag"].startswith(RELEVANCE_TAG)]

    def test_the_prompt_asks_for_relevance_to_the_focus_question(self) -> None:
        self.run_skim("--key", "K1", "--focus", FOCUS)

        [(question, _)] = self.fake.history(self.nb_id)
        self.assertIn(FOCUS, question)
        self.assertIn("相关性", question)
        for level in ["高", "中", "低"]:
            self.assertIn(level, question)

    def test_each_relevance_level_gets_its_tag(self) -> None:
        cases = [
            ("高\n直接测量了数据中心能耗。", "high"),
            ("**中**：只间接涉及。", "medium"),
            ("相关性：低。讨论的是算法效率。", "low"),
            ("High - measures datacenter energy.", "high"),
            ("Relevance: **medium**", "medium"),
            ("low, only tangential", "low"),
            ("中等相关", "medium"),
            ("**相关性：** 低", "low"),
        ]
        for section, level in cases:
            with self.subTest(section=section):
                self.setUp()
                self.answer_with_relevance(self.k1_source, section)

                report = self.run_skim("--key", "K1", "--focus", FOCUS)

                self.assertEqual(self.relevance_tags("K1"), [f"{RELEVANCE_TAG}{level}"])
                self.assertEqual(report["written"][0]["relevance"], level)
                self.assertEqual(report["relevance"][level], 1)
                html = self.zotero.created_notes[0]["note"]
                self.assertIn("<h2>与研究问题的相关性</h2>", html)
                self.assertIn(FOCUS, html.split("</p>", 1)[0])

    def test_a_level_written_on_the_heading_line_is_read(self) -> None:
        self.fake.answers[self.k1_source] = (f"{ANSWER}\n\n## 相关性：中\n只间接涉及。", [])

        self.run_skim("--key", "K1", "--focus", FOCUS)

        self.assertEqual(self.relevance_tags("K1"), [f"{RELEVANCE_TAG}medium"])

    def test_a_rerun_replaces_the_old_relevance_tag_and_keeps_other_tags(self) -> None:
        self.zotero.item_tags["K1"] = [
            {"tag": "energy"},
            {"tag": f"{RELEVANCE_TAG}low"},
            {"tag": "to-read", "type": 1},
        ]
        self.answer_with_relevance(self.k1_source, "高")

        self.run_skim("--key", "K1", "--focus", FOCUS)

        self.assertEqual(
            self.zotero.item_tags["K1"],
            [{"tag": "energy"}, {"tag": "to-read", "type": 1}, {"tag": f"{RELEVANCE_TAG}high"}],
        )

    def test_without_focus_no_relevance_is_asked_or_tagged(self) -> None:
        self.zotero.item_tags["K1"] = [{"tag": f"{RELEVANCE_TAG}low"}]
        self.answer_with_relevance(self.k1_source, "高")

        report = self.run_skim("--key", "K1")

        [(question, _)] = self.fake.history(self.nb_id)
        self.assertNotIn("相关性", question)
        self.assertEqual(self.zotero.item_tags["K1"], [{"tag": f"{RELEVANCE_TAG}low"}])
        self.assertNotIn("relevance", report["written"][0])
        self.assertEqual(report["relevance"], {"high": 0, "medium": 0, "low": 0, "unparsed": 0})

    def test_unparseable_relevance_is_reported_not_tagged(self) -> None:
        self.zotero.item_tags["K1"] = [{"tag": f"{RELEVANCE_TAG}low"}]
        self.fake.answers[self.k1_source] = (ANSWER, [])  # no relevance section
        self.answer_with_relevance(self.k2_source, "高/中/低 都有可能，难以判断。")

        report = self.run_skim("--key", "K1", "--key", "K2", "--focus", FOCUS)

        self.assertEqual(self.zotero.item_tags["K1"], [{"tag": f"{RELEVANCE_TAG}low"}])
        self.assertNotIn("K2", self.zotero.item_tags)
        self.assertEqual([w["relevance"] for w in report["written"]], ["unparsed", "unparsed"])
        self.assertEqual(report["relevance"], {"high": 0, "medium": 0, "low": 0, "unparsed": 2})

    def test_a_tagging_failure_is_reported_with_the_written_note(self) -> None:
        self.answer_with_relevance(self.k1_source, "高")
        self.zotero.tag_errors["K1"] = RuntimeError("Zotero 412")

        report = self.run_skim("--key", "K1", "--focus", FOCUS)

        self.assertEqual(report["written"], [])
        [failed] = report["failed"]
        self.assertEqual(failed["note_key"], self.zotero.created_notes[0]["key"])
        self.assertIn("Zotero 412", failed["error"])
        self.assertEqual(report["relevance"]["high"], 0)


if __name__ == "__main__":
    unittest.main()
