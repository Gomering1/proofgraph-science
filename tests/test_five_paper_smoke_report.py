from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmark" / "corpus-manifest.v0.1.json"
REPORT = ROOT / "benchmark" / "five-paper-smoke-report.v0.1.json"
REPORT_NOTE = ROOT / "docs" / "real-paper-smoke-test.md"


class FivePaperSmokeReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_report_covers_manifest_once_with_honest_outcomes(self) -> None:
        expected = {paper["pmcid"] for paper in self.manifest["papers"]}
        outcomes = self.report["outcomes"]
        self.assertEqual({outcome["pmcid"] for outcome in outcomes}, expected)
        self.assertEqual(len(outcomes), len(expected))
        self.assertEqual(
            self.report["summary"],
            {
                "papers_checked": 5,
                "unreviewed_records_emitted": 4,
                "documented_abstentions": 1,
            },
        )
        self.assertFalse(self.report["source_files_committed"])
        self.assertFalse(self.report["generated_records_committed"])
        self.assertFalse(self.report["scientifically_reviewed"])

    def test_report_contains_hashes_and_no_evidence_passages(self) -> None:
        serialized = REPORT.read_text(encoding="utf-8")
        self.assertNotIn('"evidence_text":', serialized)
        for outcome in self.report["outcomes"]:
            self.assertRegex(outcome["article_sha256"], r"^[a-f0-9]{64}$")
            anchor = outcome.get("anchor") or outcome["inspected_anchor"]
            self.assertRegex(anchor["element_text_sha256"], r"^[a-f0-9]{64}$")
            if outcome["outcome"] == "record_emitted_unreviewed":
                self.assertRegex(anchor["evidence_text_sha256"], r"^[a-f0-9]{64}$")
                self.assertLess(anchor["character_start"], anchor["character_end"])
                self.assertIn("derived_claim", outcome)
            else:
                self.assertEqual(outcome["outcome"], "documented_abstention")
                self.assertEqual(
                    outcome["reason_code"],
                    "cross_paragraph_qualifiers_not_supported",
                )
                self.assertNotIn("derived_claim", outcome)

    def test_schema_and_locator_metadata_do_not_overstate_semantics(self) -> None:
        by_pmcid = {outcome["pmcid"]: outcome for outcome in self.report["outcomes"]}

        nasicon = by_pmcid["PMC10457403"]
        self.assertEqual(nasicon["schema_version"], "0.2.0")
        self.assertNotIn("sample_condition", nasicon["derived_claim"])
        self.assertNotIn("temperature_qualifier", nasicon["derived_claim"])
        self.assertEqual(
            nasicon["derived_claim"]["observed_not_encoded"],
            [
                "approximate-temperature marker",
                "Na metal electrode configuration",
            ],
        )

        composite = by_pmcid["PMC9218661"]
        self.assertEqual(composite["schema_version"], "0.3.0")
        anchor = composite["anchor"]
        self.assertIsNone(anchor["element_id"])
        self.assertEqual(anchor["ancestor_element_id"], "advs3904-sec-0030")
        self.assertEqual(anchor["locator_scope"], "native_ancestor_plus_xpath")

        for pmcid in ("PMC8292426", "PMC10844219"):
            self.assertEqual(by_pmcid[pmcid]["schema_version"], "0.2.0")

    def test_human_readable_note_carries_every_article_hash(self) -> None:
        note = REPORT_NOTE.read_text(encoding="utf-8")
        for outcome in self.report["outcomes"]:
            self.assertIn(outcome["article_sha256"], note)


if __name__ == "__main__":
    unittest.main()
