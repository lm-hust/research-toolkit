"""
tests/test_cli_suite.py
Integration tests for CLI suite: doctor, mcp-schema, and help outputs.
"""

import json
import unittest

from click.testing import CliRunner

from research_toolkit.cli import cli


class TestCliSuite(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_cli_help(self):
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("search", result.output)
        self.assertIn("checkpoint", result.output)
        self.assertIn("sync-notebook", result.output)
        self.assertIn("ask", result.output)
        self.assertIn("doctor", result.output)
        self.assertIn("mcp-schema", result.output)

    def test_cli_doctor_runs(self):
        result = self.runner.invoke(cli, ["doctor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("System Diagnostics", result.output)

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
