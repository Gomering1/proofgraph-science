from __future__ import annotations

import json
import unittest
from pathlib import Path

from proofgraph.extract import extract_record
from proofgraph.validate import load_claim_evidence_schema, validate_record


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "authored-electrolyte-example.html"
PUBLISHED_SCHEMA = ROOT / "schemas" / "claim-evidence.v0.1.schema.json"


class SchemaRuntimeTests(unittest.TestCase):
    def test_runtime_schema_matches_published_schema(self) -> None:
        published = json.loads(PUBLISHED_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(load_claim_evidence_schema(), published)

    def test_rejects_constraint_not_covered_by_semantic_checks(self) -> None:
        record = extract_record(FIXTURE)
        record["claim"]["claim_type"] = "inferred"

        errors = validate_record(record)

        self.assertIn(
            "schema $.claim.claim_type: 'inferred' is not one of ['measured', 'predicted']",
            errors,
        )

    def test_rejects_unknown_property_with_stable_path(self) -> None:
        record = extract_record(FIXTURE)
        record["claim"]["unsupported_field"] = True

        first = validate_record(record)
        second = validate_record(record)

        self.assertEqual(first, second)
        self.assertIn(
            "schema $.claim: Additional properties are not allowed "
            "('unsupported_field' was unexpected)",
            first,
        )

    def test_wrong_container_types_do_not_crash_semantic_checks(self) -> None:
        record = extract_record(FIXTURE)
        record["claim"] = []

        errors = validate_record(record)

        self.assertTrue(any(error.startswith("schema $.claim:") for error in errors))
        self.assertIn("claim.subject is required", errors)


if __name__ == "__main__":
    unittest.main()
