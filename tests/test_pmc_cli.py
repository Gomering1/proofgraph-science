from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from proofgraph.cli import main


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic-pmc-oai.xml"
HTML_FIXTURE = ROOT / "examples" / "fixtures" / "authored-electrolyte-example.html"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"


def manifest() -> dict:
    return {
        "manifest_version": "test-only",
        "papers": [
            {
                "id": "synthetic-jats-fixture",
                "pmcid": "PMC999999999",
                "doi": "10.0000/proofgraph.synthetic",
                "license": {"spdx": "CC-BY-4.0", "url": LICENSE},
            }
        ],
    }


def abstention_manifest() -> dict:
    data = manifest()
    data["papers"][0]["local_smoke_test"] = {
        "status": "documented_abstention",
        "profile": "air_exposure_abstain_v1",
        "locator": {"type": "native_id", "element_id": "Par7"},
        "reason_code": "cross_paragraph_qualifiers_not_supported",
    }
    return data


def abstention_fixture() -> bytes:
    raw = FIXTURE.read_text(encoding="utf-8")
    old = next(line for line in raw.splitlines() if '<p id="Par7">' in line)
    new = (
        '              <p id="Par7">SYNTHETIC ABSTENTION FIXTURE. Subject token: '
        "UDSH@LPSC. Value token: 0.8 ± 0.27 mS cm-1. Duration token: 3 days. "
        "END SYNTHETIC FIXTURE.</p>"
    )
    return raw.replace(old, new, 1).encode("utf-8")


class PmcCliTests(unittest.TestCase):
    def test_processes_local_xml_with_read_only_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            output_path = root / "record.json"
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
            original_manifest = manifest_path.read_bytes()
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "extract-pmc",
                        str(FIXTURE),
                        "--manifest",
                        str(manifest_path),
                        "--pmcid",
                        "PMC999999999",
                        "--element-id",
                        "Par7",
                        "--out",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("valid unreviewed record", stdout.getvalue())
            self.assertEqual(manifest_path.read_bytes(), original_manifest)
            record = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(record["claim"]["normalized_value"], "0.000808")
            validate_stdout = StringIO()
            with redirect_stdout(validate_stdout):
                self.assertEqual(main(["validate", str(output_path)]), 0)
            self.assertIn("review status: unreviewed", validate_stdout.getvalue())
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                ["manifest.json", "record.json"],
            )

    def test_identity_failure_writes_no_record_and_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            output_path = root / "record.json"
            data = manifest()
            data["papers"][0]["doi"] = "10.0000/wrong"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            stderr = StringIO()

            with redirect_stderr(stderr):
                exit_code = main(
                    [
                        "extract-pmc",
                        str(FIXTURE),
                        "--manifest",
                        str(manifest_path),
                        "--pmcid",
                        "PMC999999999",
                        "--element-id",
                        "Par7",
                        "--out",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertIn("extract-pmc failed", stderr.getvalue())
            self.assertFalse(output_path.exists())

    def test_refuses_to_overwrite_source_or_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.xml"
            source_path.write_bytes(FIXTURE.read_bytes())
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
            source_before = source_path.read_bytes()
            manifest_before = manifest_path.read_bytes()

            for output_path in (source_path, manifest_path):
                with self.subTest(output=output_path.name), redirect_stderr(StringIO()):
                    exit_code = main(
                        [
                            "extract-pmc",
                            str(source_path),
                            "--manifest",
                            str(manifest_path),
                            "--pmcid",
                            "PMC999999999",
                            "--element-id",
                            "Par7",
                            "--out",
                            str(output_path),
                        ]
                    )
                self.assertEqual(exit_code, 2)
                self.assertEqual(source_path.read_bytes(), source_before)
                self.assertEqual(manifest_path.read_bytes(), manifest_before)

    def test_documented_abstention_returns_three_and_creates_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.xml"
            source_path.write_bytes(abstention_fixture())
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(abstention_manifest()), encoding="utf-8"
            )
            output_path = root / "record.json"
            stderr = StringIO()

            with redirect_stderr(stderr):
                exit_code = main(
                    [
                        "extract-pmc",
                        str(source_path),
                        "--manifest",
                        str(manifest_path),
                        "--pmcid",
                        "PMC999999999",
                        "--out",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 3)
            self.assertIn("extract-pmc abstained", stderr.getvalue())
            self.assertIn(
                "cross_paragraph_qualifiers_not_supported", stderr.getvalue()
            )
            self.assertFalse(output_path.exists())

    def test_abstention_run_refuses_preexisting_output_without_changing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.xml"
            source_path.write_bytes(abstention_fixture())
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(abstention_manifest()), encoding="utf-8"
            )
            output_path = root / "record.json"
            sentinel = b"existing output must remain byte-identical\n"
            output_path.write_bytes(sentinel)
            stderr = StringIO()

            with redirect_stderr(stderr):
                exit_code = main(
                    [
                        "extract-pmc",
                        str(source_path),
                        "--manifest",
                        str(manifest_path),
                        "--pmcid",
                        "PMC999999999",
                        "--out",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertIn("output path already exists", stderr.getvalue())
            self.assertEqual(output_path.read_bytes(), sentinel)

    def test_html_extract_also_refuses_preexisting_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "record.json"
            sentinel = b"keep me\n"
            output_path.write_bytes(sentinel)
            stderr = StringIO()

            with redirect_stderr(stderr):
                exit_code = main(
                    [
                        "extract",
                        str(HTML_FIXTURE),
                        "--out",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertIn("output path already exists", stderr.getvalue())
            self.assertEqual(output_path.read_bytes(), sentinel)


if __name__ == "__main__":
    unittest.main()
