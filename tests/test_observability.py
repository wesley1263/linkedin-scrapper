import json
import logging
import os
import stat
import tempfile
import unittest
from datetime import datetime, timezone

import observability as obs


def section(name, collect="ok", parse="ok"):
    return obs.SectionResult(section=name, collect_status=collect, parse_status=parse)


class JobStatusTest(unittest.TestCase):
    def test_all_ok_or_empty_is_success(self):
        self.assertEqual(obs.job_status([section("a"), section("b", parse="empty")]), obs.SUCCESS)

    def test_some_failed_is_partial(self):
        self.assertEqual(obs.job_status([section("a"), section("b", parse="failed")]), obs.PARTIAL)

    def test_collect_failure_counts_as_failed_section(self):
        self.assertEqual(obs.job_status([section("a"), section("b", collect="failed", parse=None)]), obs.PARTIAL)

    def test_all_failed_is_failed(self):
        self.assertEqual(obs.job_status([section("a", parse="failed"), section("b", parse="failed")]), obs.FAILED)

    def test_no_sections_is_failed(self):
        self.assertEqual(obs.job_status([]), obs.FAILED)

    def test_auth_and_not_found_take_precedence(self):
        self.assertEqual(obs.job_status([section("a")], auth_ok=False), obs.AUTH_REQUIRED)
        self.assertEqual(obs.job_status([section("a")], found=False), obs.NOT_FOUND)

    def test_exit_codes(self):
        self.assertEqual(
            [obs.exit_code(s) for s in (obs.SUCCESS, obs.PARTIAL, obs.FAILED, obs.AUTH_REQUIRED, obs.NOT_FOUND)],
            [0, 2, 1, 1, 1],
        )


class ParseStatusLineTest(unittest.TestCase):
    def test_takes_last_json_line_with_status(self):
        out = 'ruído\n{"other": 1}\n{"section":"x","status":"empty","items":0}\n'
        self.assertEqual(obs.parse_status_line(out)["status"], "empty")

    def test_none_without_status(self):
        self.assertIsNone(obs.parse_status_line("panic: boom\n"))
        self.assertIsNone(obs.parse_status_line(""))


class RunParserTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def fake_binary(self, script):
        path = os.path.join(self.dir.name, "fake-parser")
        with open(path, "w") as f:
            f.write("#!/bin/sh\n" + script)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def run_fake(self, script):
        return obs.run_parser(self.fake_binary(script), "in.html", "out.json", "experience")

    def test_reads_status_line(self):
        r = self.run_fake('echo \'{"section":"experience","status":"ok","items":4,"duration_ms":7}\'\n')
        self.assertEqual((r.parse_status, r.items, r.duration_ms, r.error), ("ok", 4, 7, None))
        self.assertTrue(r.ok)

    def test_failed_status_keeps_error(self):
        r = self.run_fake('echo \'{"section":"experience","status":"failed","error":"layout"}\'\nexit 3\n')
        self.assertEqual((r.parse_status, r.error), ("failed", "layout"))
        self.assertFalse(r.ok)

    def test_crash_without_status_line_is_failed(self):
        r = self.run_fake("echo 'panic: boom' >&2\nexit 2\n")
        self.assertEqual(r.parse_status, "failed")
        self.assertIn("panic: boom", r.error)

    def test_missing_binary_is_failed(self):
        r = obs.run_parser("/nao/existe/parser", "in.html", "out.json", "experience")
        self.assertEqual(r.parse_status, "failed")
        self.assertIn("FileNotFoundError", r.error)


class OutputTest(unittest.TestCase):
    def test_status_json_separates_collect_and_parse(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "status.json")
            sections = [section("profile"), section("languages", parse="empty")]
            obs.write_status_json(path, "abc123", "https://x/in/y/", obs.SUCCESS, sections,
                                  datetime(2026, 10, 17, tzinfo=timezone.utc), 1234)
            with open(path) as f:
                data = json.load(f)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["sections"]["languages"]["parse_status"], "empty")
        self.assertEqual(data["sections"]["profile"]["collect_status"], "ok")
        self.assertNotIn("section", data["sections"]["profile"])

    def test_json_log_line_has_context(self):
        record = logging.LogRecord("scraper", logging.INFO, __file__, 1, "feito %s", ("ok",), None)
        record.job_id, record.section, record.duration_ms = "abc123", "experience", 42
        entry = json.loads(obs.JsonFormatter().format(record))
        self.assertEqual((entry["msg"], entry["job_id"], entry["section"], entry["duration_ms"]),
                         ("feito ok", "abc123", "experience", 42))


class CollectJobStatusTest(unittest.TestCase):
    """Modo worker: só coleta (o parsing é do parser worker), então o status vem do collect_status."""

    def sections(self, *collect):
        return [obs.SectionResult(f"s{i}", collect_status=c) for i, c in enumerate(collect)]

    def test_all_collected_is_success_even_without_parse(self):
        self.assertEqual(obs.collect_job_status(self.sections("ok", "ok")), obs.SUCCESS)

    def test_some_collected_is_partial(self):
        self.assertEqual(obs.collect_job_status(self.sections("ok", "failed")), obs.PARTIAL)

    def test_none_collected_is_failed(self):
        self.assertEqual(obs.collect_job_status(self.sections("failed", "failed")), obs.FAILED)
        self.assertEqual(obs.collect_job_status([]), obs.FAILED)

    def test_auth_and_not_found_take_precedence(self):
        self.assertEqual(obs.collect_job_status(self.sections("ok"), auth_ok=False), obs.AUTH_REQUIRED)
        self.assertEqual(obs.collect_job_status(self.sections("ok"), found=False), obs.NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
