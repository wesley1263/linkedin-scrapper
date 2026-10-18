import io
import json
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone

import bundle
from observability import SectionResult

URL = "https://www.linkedin.com/in/fulano/"
WHEN = datetime(2026, 10, 15, 14, 2, 11, tzinfo=timezone.utc)


class SectionStatusTest(unittest.TestCase):
    def test_ok(self):
        r = SectionResult("experience", final_url=URL + "details/experience/?locale=pt_BR")
        self.assertEqual(bundle.section_status(r, URL + "details/experience/"), bundle.OK)

    def test_redirected(self):
        r = SectionResult("languages", final_url="https://www.linkedin.com/login")
        self.assertEqual(bundle.section_status(r, URL + "details/languages/"), bundle.REDIRECTED)

    def test_percent_encoding_and_case_do_not_count_as_redirect(self):
        r = SectionResult("profile", final_url="https://www.linkedin.com/in/jos%C3%A9/")
        self.assertEqual(bundle.section_status(r, "https://www.linkedin.com/in/josé/"), bundle.OK)

    def test_timeout_and_not_collected(self):
        t = SectionResult("profile", collect_status="failed", error="TimeoutException: x")
        n = SectionResult("profile", collect_status="failed", error="não processada")
        self.assertEqual(bundle.section_status(t, URL), bundle.TIMEOUT)
        self.assertEqual(bundle.section_status(n, URL), bundle.NOT_COLLECTED)


class ManifestTest(unittest.TestCase):
    def manifest(self, **sections):
        return bundle.build_manifest("abc", None, URL, WHEN, sections)

    def test_build_is_valid_and_drops_file_without_html(self):
        m = self.manifest(profile=("profile.html", "ok", URL),
                          languages=("languages.html", "redirected", "https://x/login"),
                          education=("education.html", "timeout", None))
        self.assertEqual(bundle.validate_manifest(m), [])
        self.assertEqual(m["collected_at"], "2026-10-15T14:02:11Z")
        self.assertIsNone(m["sections"]["education"]["file"])
        self.assertEqual(m["sections"]["languages"]["final_url"], "https://x/login")
        self.assertNotIn("final_url", m["sections"]["profile"])

    def test_validate_rejects_bad_manifests(self):
        good = self.manifest(profile=("profile.html", "ok", URL))
        for mutate in (
            lambda m: m.update(schema_version=2),
            lambda m: m.update(job_id=""),
            lambda m: m["collector"].update(type="bot"),
            lambda m: m["sections"]["profile"].update(status="done"),
            lambda m: m["sections"]["profile"].update(file=None),
            lambda m: m["sections"]["profile"].update(status="redirected"),
            lambda m: m.update(sections={}),
        ):
            m = json.loads(json.dumps(good))
            mutate(m)
            self.assertTrue(bundle.validate_manifest(m), m)

    def test_no_credentials_fields(self):
        text = json.dumps(self.manifest(profile=("profile.html", "ok", URL))).lower()
        for word in ("password", "cookie", "token", "li_at"):
            self.assertNotIn(word, text)


class BuildZipTest(unittest.TestCase):
    def test_zip_has_manifest_and_only_collected_html(self):
        with tempfile.TemporaryDirectory() as src:
            for name in ("profile.html", "education.html"):
                with open(os.path.join(src, name), "w") as f:
                    f.write("<html>" + name + "</html>")
            m = bundle.build_manifest("abc", "acc1", URL, WHEN, {
                "profile": ("profile.html", "ok", URL),
                "education": ("education.html", "timeout", None),  # HTML parcial no disco não entra no zip
            })
            with zipfile.ZipFile(io.BytesIO(bundle.build_zip(src, m))) as zf:
                self.assertEqual(sorted(zf.namelist()), ["manifest.json", "profile.html"])
                self.assertEqual(json.loads(zf.read("manifest.json"))["account_id"], "acc1")
                self.assertEqual(zf.read("profile.html"), b"<html>profile.html</html>")

    def test_invalid_manifest_is_refused(self):
        with self.assertRaises(ValueError):
            bundle.build_zip(".", {"schema_version": 9})

    def test_key_and_parse_message_are_small(self):
        m = bundle.build_manifest("abc", None, URL, WHEN, {"profile": ("profile.html", "ok", URL)})
        key = bundle.bundle_key("fulano", m)
        self.assertEqual(key, "raw/fulano/20261015T140211Z.zip")
        msg = json.loads(bundle.parse_message(m, key))
        self.assertEqual(msg, {"schema_version": 1, "job_id": "abc", "linkedin_url": URL, "zip_key": key})


class StoreBundleTest(unittest.TestCase):
    def test_expected_urls(self):
        urls = bundle.expected_urls(URL)
        self.assertEqual(urls["profile"], URL)
        self.assertEqual(urls["experience"], URL + "details/experience/")
        self.assertEqual(set(urls), {"profile", "experience", "education", "languages"})

    def test_stores_zip_and_returns_key_and_manifest(self):
        import infra
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as root:
            with open(os.path.join(src, "profile.html"), "w") as f:
                f.write("<html/>")
            storage = infra.FsStorage(root)
            results = [SectionResult("profile", final_url=URL),
                       SectionResult("education", collect_status="failed", error="TimeoutException: x")]
            key, manifest = bundle.store_bundle(storage, "job1", "acc", URL, "fulano", src, WHEN, results)
            self.assertEqual(key, "raw/fulano/20261015T140211Z.zip")
            self.assertEqual(manifest["sections"]["education"]["status"], "timeout")
            with zipfile.ZipFile(io.BytesIO(storage.get(key))) as zf:
                self.assertEqual(sorted(zf.namelist()), ["manifest.json", "profile.html"])

    def test_returns_none_when_no_html_was_collected(self):
        import infra
        with tempfile.TemporaryDirectory() as root:
            results = [SectionResult("profile", collect_status="failed", error="x")]
            self.assertIsNone(bundle.store_bundle(infra.FsStorage(root), "j", None, URL, "fulano", root, WHEN, results))

    def test_storage_errors_propagate(self):
        class Broken:
            def put(self, key, data):
                raise OSError("disco cheio")
        with tempfile.TemporaryDirectory() as src:
            with open(os.path.join(src, "profile.html"), "w") as f:
                f.write("<html/>")
            with self.assertRaises(OSError):
                bundle.store_bundle(Broken(), "j", None, URL, "fulano", src, WHEN, [SectionResult("profile", final_url=URL)])


if __name__ == "__main__":
    unittest.main()
