"""
tests/test_cli_suite.py
Integration tests for CLI suite: doctor, mcp-schema, and help outputs.
"""

import json
import os
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from research_toolkit.cli import cli


class TestCliSuite(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_cli_help(self):
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("scout", result.output)
        self.assertIn("search", result.output)
        self.assertIn("checkpoint", result.output)
        self.assertIn("sync-notebook", result.output)
        self.assertIn("doctor", result.output)
        self.assertIn("mcp-schema", result.output)

    def test_ask_command_removed(self):
        result = self.runner.invoke(cli, ["--help"])
        listed = {line.split()[0] for line in result.output.splitlines() if line.startswith("  ") and line.split()}
        self.assertNotIn("ask", listed)
        self.assertNotEqual(self.runner.invoke(cli, ["ask", "anything"]).exit_code, 0)

    def test_doctor_ignores_gemini_api_key(self):
        result = self._doctor(env_extra={"GEMINI_API_KEY": "AIza123"})
        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("GEMINI", result.output)
        self.assertNotIn("Gemini fallback", result.output)

    def test_cli_doctor_runs(self):
        result = self._doctor()
        self.assertEqual(result.exit_code, 0)
        self.assertIn("System Diagnostics", result.output)

    def _doctor(self, env_extra=None, auth=None):
        env = {k: v for k, v in os.environ.items() if k != "NOTEBOOKLM_AUTH_JSON"}
        env["COLUMNS"] = "400"  # keep each rich table row on one line
        env.update(env_extra or {})
        auth = auth or (lambda: "Authenticated (3 notebooks)")
        with patch.dict(os.environ, env, clear=True), patch("research_toolkit.cli.check_notebook_auth", side_effect=auth):
            return self.runner.invoke(cli, ["doctor"], terminal_width=400)

    def test_doctor_reports_gemini_notebook_auth_pass(self):
        result = self._doctor()
        self.assertEqual(result.exit_code, 0)
        row = next(line for line in result.output.splitlines() if "Gemini Notebook" in line)
        self.assertIn("PASS", row)
        self.assertIn("Authenticated (3 notebooks)", row)

    def test_doctor_reports_gemini_notebook_auth_failure(self):
        def broken():
            raise RuntimeError("master token rejected")

        result = self._doctor(auth=broken)
        self.assertEqual(result.exit_code, 0)
        row = next(line for line in result.output.splitlines() if "Gemini Notebook" in line)
        self.assertIn("FAIL", row)
        self.assertIn("master token rejected", row)

    def test_doctor_warns_when_auth_json_env_shadows_master_token(self):
        result = self._doctor(env_extra={"NOTEBOOKLM_AUTH_JSON": '{"cookies": []}'})
        self.assertEqual(result.exit_code, 0)
        rows = [line for line in result.output.splitlines() if "NOTEBOOKLM_AUTH_JSON" in line]
        self.assertTrue(rows, result.output)
        self.assertIn("WARN", rows[0])
        self.assertIn("master token", rows[0])

    def test_doctor_omits_auth_json_warning_when_unset(self):
        result = self._doctor()
        self.assertNotIn("NOTEBOOKLM_AUTH_JSON", result.output)

    def test_cli_mcp_schema_outputs_valid_json(self):
        result = self.runner.invoke(cli, ["mcp-schema"])
        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.output)
        self.assertIsInstance(data, list)
        tool_names = [t["name"] for t in data]
        self.assertIn("search_literature", tool_names)
        self.assertIn("verify_checkpoint", tool_names)

    def test_cli_generate_key(self):
        result = self.runner.invoke(cli, ["generate-key"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("🔑 Generated API Key: rtk_", result.output)


if __name__ == "__main__":
    unittest.main()
