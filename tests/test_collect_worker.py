import json
import os
import tempfile
import unittest
import zipfile
import io
from datetime import datetime, timezone

import infra
from api_client import ApiError
from collect_worker import COLLECT_TOPIC, PARSE_TOPIC, handle_collect
from observability import CollectOutcome, SectionResult

JOB_ID = "3ed143b7-c006-4884-aa5c-7bf3161bf278"
URL = "https://www.linkedin.com/in/fulano/"
WHEN = datetime(2026, 10, 18, 3, 26, 7, tzinfo=timezone.utc)


def message(**overrides):
    body = {"schema_version": 1, "job_id": JOB_ID, "linkedin_url": URL, "account_id": ""}
    body.update(overrides)
    return json.dumps(body).encode()


class FakeApi:
    def __init__(self, status="queued"):
        self.status = status
        self.calls = []          # ("get",) / ("set", status, error), em ordem
        self.get_error = None
        self.set_errors = {}     # status -> ApiError a lançar

    def get_job(self, job_id):
        self.calls.append(("get",))
        if self.get_error:
            raise self.get_error
        return {"job_id": job_id, "status": self.status}

    def set_status(self, job_id, status, error=""):
        self.calls.append(("set", status, error))
        if status in self.set_errors:
            raise self.set_errors[status]
        self.status = status
        return {"job_id": job_id, "status": status}

    def statuses_set(self):
        return [c[1] for c in self.calls if c[0] == "set"]


class RecordingStorage(infra.FsStorage):
    def __init__(self, root, events):
        super().__init__(root)
        self.events = events
        self.fail = None

    def put(self, key, data):
        if self.fail:
            raise self.fail
        super().put(key, data)
        self.events.append("put")


class RecordingQueue(infra.MemoryQueue):
    def __init__(self, events):
        super().__init__()
        self.events = events
        self.failures = 0

    def publish(self, topic, body):
        if self.failures > 0:
            self.failures -= 1
            raise OSError("fila fora do ar")
        super().publish(topic, body)
        self.events.append("publish")


class CollectWorkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "src")
        os.makedirs(self.src)
        for name in ("profile", "experience"):
            with open(os.path.join(self.src, f"{name}.html"), "w") as f:
                f.write(f"<html>{name}</html>")
        self.events = []
        self.api = FakeApi()
        self.storage = RecordingStorage(os.path.join(self.tmp.name, "store"), self.events)
        self.queue = RecordingQueue(self.events)
        self.scrape_calls = []
        self.outcome = self.make_outcome("success")
        self.scrape_error = None

    def make_outcome(self, status, results=None):
        if results is None:
            results = [SectionResult("profile", final_url=URL),
                       SectionResult("experience", final_url=URL + "details/experience/")]
        return CollectOutcome(status=status, results=results, output_dir=self.src, base_url=URL,
                              dir_name="fulano", started_at=WHEN)

    def scrape(self, url, job_id):
        self.scrape_calls.append((url, job_id))
        self.events.append("scrape")
        if self.scrape_error:
            raise self.scrape_error
        return self.outcome

    def run_handler(self, body=None, **kwargs):
        return handle_collect(body or message(), api=self.api, scrape=self.scrape, storage=self.storage,
                              queue=self.queue, sleep=lambda s: None, **kwargs)

    def parse_messages(self):
        out = []
        self.queue.consume(PARSE_TOPIC, lambda m: out.append(json.loads(m.body)))
        return out

    # --- caminho feliz -------------------------------------------------------------------------------

    def test_happy_path_order_and_message(self):
        self.run_handler()
        self.assertEqual(self.api.statuses_set(), ["collecting", "collected"])
        # zip no storage ANTES de collected; collected ANTES de publicar em parse
        self.assertEqual(self.events, ["scrape", "put", "publish"])
        set_collected = self.api.calls.index(("set", "collected", ""))
        self.assertGreater(set_collected, 0)
        msgs = self.parse_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["job_id"], JOB_ID)
        self.assertTrue(msgs[0]["zip_key"].startswith("raw/fulano/") and msgs[0]["zip_key"].endswith(".zip"))
        self.assertEqual(self.scrape_calls, [(URL, JOB_ID)])

    def test_collected_is_set_before_publishing_parse(self):
        order = []
        original_set, original_publish = self.api.set_status, self.queue.publish
        self.api.set_status = lambda j, s, e="": (order.append(f"set:{s}"), original_set(j, s, e))[1]
        self.queue.publish = lambda t, b: (order.append("publish"), original_publish(t, b))[1]
        self.run_handler()
        self.assertEqual(order, ["set:collecting", "set:collected", "publish"])

    def test_zip_contains_manifest_with_the_job_id_and_html(self):
        self.run_handler()
        stored = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(self.tmp.name, "store")) for f in fs]
        self.assertEqual(len(stored), 1)
        with zipfile.ZipFile(stored[0]) as zf:
            self.assertEqual(sorted(zf.namelist()), ["experience.html", "manifest.json", "profile.html"])
            manifest = json.loads(zf.read("manifest.json"))
        self.assertEqual(manifest["job_id"], JOB_ID)
        self.assertEqual(manifest["linkedin_url"], URL)

    def test_partial_outcome_is_still_collected_and_published(self):
        self.outcome = self.make_outcome("partial", [
            SectionResult("profile", final_url=URL),
            SectionResult("experience", collect_status="failed", error="TimeoutException: x")])
        self.run_handler()
        self.assertEqual(self.api.statuses_set(), ["collecting", "collected"])
        self.assertEqual(len(self.parse_messages()), 1)

    # --- idempotência / retomada --------------------------------------------------------------------

    def test_resumes_job_already_collecting(self):
        self.api.status = "collecting"  # tentativa anterior caiu no meio
        self.run_handler()
        self.assertEqual(self.api.statuses_set(), ["collected"])
        self.assertEqual(self.scrape_calls, [(URL, JOB_ID)])

    def test_skips_jobs_that_are_not_queued_or_collecting(self):
        for status in ("collected", "parsing", "done", "parse_failed", "collect_failed", "auth_required"):
            self.api = FakeApi(status)
            self.events.clear()
            self.scrape_calls.clear()
            self.run_handler()
            self.assertEqual(self.scrape_calls, [], status)
            self.assertEqual(self.api.statuses_set(), [], status)
            self.assertEqual(self.events, [], status)

    def test_concurrent_duplicate_conflict_on_collecting_is_skipped(self):
        self.api.set_errors["collecting"] = ApiError("conflito", status=409, current_status="collecting")
        self.run_handler()
        self.assertEqual(self.scrape_calls, [])
        self.assertEqual(self.events, [])

    # --- limite de ritmo (ADR-0005) ------------------------------------------------------------------

    class FakeLimiter:
        def __init__(self, wait=0):
            self.wait, self.calls = wait, []

        def check(self, account):
            self.calls.append(("check", account))
            return self.wait

        def record_start(self, account):
            self.calls.append(("record", account))

    def test_defers_when_account_is_over_the_limit_without_touching_the_job(self):
        limiter = self.FakeLimiter(wait=42)
        with self.assertLogs("scraper.collect", level="INFO") as logs, self.assertRaises(infra.Defer) as ctx:
            self.run_handler(message(account_id="acc1"), limiter=limiter)
        self.assertTrue(any("acc1" in line and "42" in line for line in logs.output), logs.output)
        self.assertEqual(ctx.exception.delay, 42)
        self.assertEqual(limiter.calls, [("check", "acc1")])
        self.assertEqual(self.api.statuses_set(), [])  # o job continua queued
        self.assertEqual(self.scrape_calls, [])

    def test_records_start_before_scraping_when_allowed(self):
        limiter = self.FakeLimiter()
        self.run_handler(message(account_id="acc1"), limiter=limiter)
        self.assertEqual(limiter.calls, [("check", "acc1"), ("record", "acc1")])
        self.assertEqual(self.events[0], "scrape")

    def test_account_defaults_when_message_has_none(self):
        limiter = self.FakeLimiter()
        self.run_handler(limiter=limiter)
        self.assertEqual(limiter.calls[0], ("check", "default"))

    def test_job_that_needs_no_collection_is_skipped_without_deferring(self):
        self.api.status = "done"
        limiter = self.FakeLimiter(wait=99)
        self.run_handler(limiter=limiter)  # não levanta Defer: nada a coletar, a mensagem é confirmada
        self.assertEqual(limiter.calls, [])

    def test_resumed_collecting_job_also_respects_the_limit(self):
        self.api.status = "collecting"
        with self.assertRaises(infra.Defer):
            self.run_handler(limiter=self.FakeLimiter(wait=10))

    def test_conflict_on_collecting_does_not_consume_a_slot(self):
        self.api.set_errors["collecting"] = ApiError("conflito", status=409, current_status="collecting")
        limiter = self.FakeLimiter()
        self.run_handler(limiter=limiter)
        self.assertNotIn(("record", "default"), limiter.calls)

    # --- resultados que não geram zip ---------------------------------------------------------------

    def test_auth_required(self):
        self.outcome = self.make_outcome("auth_required", [])
        self.run_handler()
        self.assertEqual(self.api.statuses_set(), ["collecting", "auth_required"])
        self.assertNotIn("put", self.events)
        self.assertNotIn("publish", self.events)
        self.assertTrue(self.api.calls[-1][2])  # com motivo

    def test_not_found_marks_collect_failed_with_reason(self):
        self.outcome = self.make_outcome("not_found", [])
        self.run_handler()
        self.assertEqual(self.api.statuses_set(), ["collecting", "collect_failed"])
        self.assertIn("não encontrado", self.api.calls[-1][2])
        self.assertEqual(self.parse_messages(), [])

    def test_failed_without_any_html_marks_collect_failed(self):
        self.outcome = self.make_outcome("failed", [
            SectionResult("profile", collect_status="failed", error="TimeoutException: x"),
            SectionResult("experience", collect_status="failed", error="não processada")])
        self.run_handler()
        self.assertEqual(self.api.statuses_set(), ["collecting", "collect_failed"])
        self.assertIn("TimeoutException", self.api.calls[-1][2])
        self.assertNotIn("put", self.events)

    def test_unexpected_scrape_exception_marks_collect_failed_and_acks(self):
        self.scrape_error = RuntimeError("driver morreu")
        with self.assertLogs("scraper.collect", level="ERROR"):
            self.run_handler()  # não propaga: a mensagem é confirmada, a falha fica no job
        self.assertEqual(self.api.statuses_set(), ["collecting", "collect_failed"])
        self.assertIn("RuntimeError", self.api.calls[-1][2])
        self.assertIn("driver morreu", self.api.calls[-1][2])

    # --- falhas de infraestrutura: propagam para reentrega -------------------------------------------

    def test_storage_failure_propagates_without_marking_collected(self):
        self.storage.fail = OSError("disco cheio")
        with self.assertRaises(OSError):
            self.run_handler()
        self.assertEqual(self.api.statuses_set(), ["collecting"])
        self.assertNotIn("publish", self.events)

    def test_api_failure_on_collected_propagates_without_publishing(self):
        self.api.set_errors["collected"] = ApiError("API fora do ar")
        with self.assertRaises(ApiError):
            self.run_handler()
        self.assertNotIn("publish", self.events)

    def test_publish_is_retried_then_succeeds(self):
        self.queue.failures = 2
        self.run_handler()
        self.assertEqual(len(self.parse_messages()), 1)

    def test_publish_gives_up_after_attempts_and_raises(self):
        self.queue.failures = 99
        with self.assertRaises(OSError):
            self.run_handler(publish_attempts=3)
        self.assertEqual(self.api.statuses_set(), ["collecting", "collected"])  # zip já guardado; lacuna documentada

    def test_unknown_job_raises(self):
        self.api.get_error = ApiError("job não encontrado", status=404)
        with self.assertRaises(ApiError):
            self.run_handler()
        self.assertEqual(self.scrape_calls, [])

    # --- mensagem inválida ---------------------------------------------------------------------------

    def test_invalid_messages_raise_before_touching_anything(self):
        for body in (b"lixo", message(schema_version=2), message(job_id=""), message(linkedin_url=""),
                     json.dumps({"schema_version": 1}).encode()):
            with self.assertRaises(ValueError, msg=body):
                self.run_handler(body)
        self.assertEqual(self.api.calls, [])
        self.assertEqual(self.scrape_calls, [])

    def test_topics_are_the_documented_ones(self):
        self.assertEqual((COLLECT_TOPIC, PARSE_TOPIC), ("collect", "parse"))


if __name__ == "__main__":
    unittest.main()
