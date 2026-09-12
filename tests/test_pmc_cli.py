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


if __name__ == "__main__":
    unittest.main()
