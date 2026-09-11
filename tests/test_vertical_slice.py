from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from proofgraph.extract import extract_record
from proofgraph.validate import set_validation_result, validate_record


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "authored-electrolyte-example.html"


class VerticalSliceTests(unittest.TestCase):
    def test_extracts_source_linked_claim(self) -> None:
        record = extract_record(FIXTURE)
        errors = set_validation_result(record)
        self.assertEqual(errors, [])
        self.assertEqual(record["validation"]["status"], "valid")
        self.assertEqual(record["source_anchor"]["element_id"], "conductivity-claim")
        self.assertEqual(record["claim"]["subject"], "Li6PS5Cl")
        self.assertEqual(record["claim"]["normalized_value"], "0.0012")
        self.assertEqual(record["claim"]["normalized_unit"], "S/cm")
        self.assertEqual(record["qualifiers"]["temperature_value"], "25")
        self.assertEqual(record["review"]["status"], "unreviewed")

    def test_fails_when_evidence_does_not_support_value(self) -> None:
        record = extract_record(FIXTURE)
        record["claim"]["reported_value"] = "9.9"
        errors = validate_record(record)
        self.assertIn("claim.reported_value is not supported by evidence_text", errors)

    def test_output_is_json_serializable(self) -> None:
        record = extract_record(FIXTURE)
        set_validation_result(record)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "record.json"
            target.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            loaded = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema_version"], "0.1.0")


if __name__ == "__main__":
    unittest.main()
