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

    def run_skim_with_input(self, answer: str, *args: str) -> Result:
        with patch(OPEN_CLIENT, self.fake.open), patch(
            "research_toolkit.cli.ZoteroManager", self.zotero.manager
        ):
            return CliRunner().invoke(cli, ["skim-notebook", *args], input=answer)

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

    # --- batch runs and idempotency (#65) --------------------------------------
    def test_without_keys_every_keyed_source_is_skimmed(self) -> None:
        report = self.report(self.run_skim("--notebook", NOTEBOOK))

        self.assertEqual([e["key"] for e in report["written"]], ["K1", "K2"])
        self.assertEqual([n["parentItem"] for n in self.zotero.created_notes], ["K1", "K2"])
        asks = [w[2] for w in self.fake.writes if w[0] == "ask"]
        self.assertEqual(asks, [(self.k1_source,), (self.k2_source,)])
        self.assertEqual(report["updated"], [])
        self.assertEqual(report["skipped"], [])

    def test_a_paper_with_a_skim_note_is_skipped_without_asking(self) -> None:
        self.zotero.add_note("K1", "<h1>Gemini 初读：old</h1>", ["gemini-skim/ai-note"])
        self.zotero.add_note("K2", "<h1>My own reading</h1>", ["zotero-deep-read/ai-note"])
        self.fake.start_conversation(self.nb_id, [("keep", "me")])

        report = self.report(self.run_skim("--notebook", NOTEBOOK))

        self.assertEqual(
            report["skipped"],
            [{"key": "K1", "title": "Energy and Policy Considerations", "source_id": self.k1_source, "note_key": "N0000000"}],
        )
        self.assertEqual([e["key"] for e in report["written"]], ["K2"])
        self.assertEqual([w[2] for w in self.fake.writes if w[0] == "ask"], [(self.k2_source,)])
        self.assertEqual(self.zotero.created_notes[0]["note"], "<h1>Gemini 初读：old</h1>")

    def test_when_everything_is_skimmed_the_conversation_is_left_alone(self) -> None:
        self.zotero.add_note("K1", "<p>old</p>", ["gemini-skim/ai-note"])
        self.zotero.add_note("K2", "<p>old</p>", ["gemini-skim/ai-note"])
        original = self.fake.start_conversation(self.nb_id, [("keep", "me")])

        report = self.report(self.run_skim("--notebook", NOTEBOOK))

        self.assertEqual([e["key"] for e in report["skipped"]], ["K1", "K2"])
        self.assertFalse(report["saved_history_note"])
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(self.fake.conversation_id(self.nb_id), original)

    def test_refresh_rewrites_the_same_note_instead_of_adding_one(self) -> None:
        note_key = self.zotero.add_note("K1", "<h1>Gemini 初读：old</h1>", ["gemini-skim/ai-note"])
        self.fake.answers[self.k1_source] = (ANSWER, [])

        report = self.report(self.run_skim("--notebook", NOTEBOOK, "--key", "K1", "--refresh"))

        [note] = self.zotero.created_notes
        self.assertEqual(note["key"], note_key)
        self.assertIn("1438 lbs CO2", note["note"])
        self.assertEqual(note["tags"], ["gemini-skim/ai-note"])
        self.assertEqual(self.zotero.updated_notes, [{"key": note_key, "note": note["note"], "version": 1}])
        self.assertEqual(
            report["updated"],
            [{"key": "K1", "title": "Energy and Policy Considerations", "source_id": self.k1_source, "note_key": note_key}],
        )
        self.assertEqual(report["written"], [])

    def test_a_refused_update_is_a_failure_and_the_run_goes_on(self) -> None:
        note_key = self.zotero.add_note("K1", "<p>old</p>", ["gemini-skim/ai-note"])
        self.zotero.update_errors[note_key] = RuntimeError("HTTP 412")

        report = self.report(self.run_skim("--notebook", NOTEBOOK, "--refresh"))

        self.assertEqual([(f["key"], f["error"]) for f in report["failed"]], [("K1", "HTTP 412")])
        self.assertEqual([e["key"] for e in report["written"]], ["K2"])

    # --- quota ----------------------------------------------------------------
    def test_report_carries_quota_before_and_after(self) -> None:
        self.fake.quota_remaining_percent = 50.0
        self.fake.weekly_remaining_percent = 80.0

        report = self.report(self.run_skim("--notebook", NOTEBOOK))

        before, after = report["quota_before"], report["quota_after"]
        self.assertEqual(before["window"], "five_hour")
        self.assertAlmostEqual(before["remaining_percent"], 50.0)
        self.assertAlmostEqual(before["needed_percent"], 0.82)
        self.assertAlmostEqual(after["remaining_percent"], 49.18)

    def test_short_quota_without_a_terminal_aborts_before_any_write(self) -> None:
        self.fake.quota_remaining_percent = 0.5  # two asks need 0.82 %
        self.fake.start_conversation(self.nb_id, [("keep", "me")])

        result = self.run_skim("--notebook", NOTEBOOK)

        self.assertEqual(result.exit_code, 1)
        self.assertIn("0.82", result.stderr)
        self.assertIn("--yes", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(self.zotero.created_notes, [])

    def test_short_quota_asks_for_confirmation_on_a_terminal(self) -> None:
        self.fake.quota_remaining_percent = 0.5
        with patch("research_toolkit.cli.stdin_is_interactive", return_value=True):
            declined = self.run_skim_with_input("n\n", "--notebook", NOTEBOOK)
            self.assertEqual(declined.exit_code, 1)
            self.assertEqual(self.fake.writes, [])

            accepted = self.run_skim_with_input("y\n", "--notebook", NOTEBOOK)
        self.assertEqual(accepted.exit_code, 0, accepted.output)
        self.assertIn("0.82", accepted.stderr)
        self.assertEqual([e["key"] for e in json.loads(accepted.stdout)["written"]], ["K1", "K2"])

    def test_yes_skips_the_quota_confirmation(self) -> None:
        self.fake.quota_remaining_percent = 0.5

        report = self.report(self.run_skim("--notebook", NOTEBOOK, "--yes"))

        self.assertEqual([e["key"] for e in report["written"]], ["K1", "K2"])

    def test_the_weekly_window_counts_when_it_is_the_tighter_one(self) -> None:
        self.fake.weekly_remaining_percent = 0.5

        result = self.run_skim("--notebook", NOTEBOOK)

        self.assertEqual(result.exit_code, 1)
        self.assertIn("weekly", result.stderr)

    def test_quota_only_counts_papers_that_will_be_asked(self) -> None:
        self.zotero.add_note("K1", "<p>old</p>", ["gemini-skim/ai-note"])
        self.fake.quota_remaining_percent = 0.5  # enough for one ask

        report = self.report(self.run_skim("--notebook", NOTEBOOK))

        self.assertAlmostEqual(report["quota_before"]["needed_percent"], 0.41)
        self.assertEqual([e["key"] for e in report["written"]], ["K2"])

    def test_unknown_quota_does_not_block(self) -> None:
        self.fake.usage_errors = RuntimeError("usage RPC failed")

        report = self.report(self.run_skim("--notebook", NOTEBOOK))

        self.assertIsNone(report["quota_before"])
        self.assertIsNone(report["quota_after"])
        self.assertEqual(len(report["written"]), 2)

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


if __name__ == "__main__":
    unittest.main()
