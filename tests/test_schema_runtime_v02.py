from __future__ import annotations

import json
from pathlib import Path
import unittest

from proofgraph.extract import extract_pmc_record
from proofgraph.pmc import parse_pmc_oai_jats
from proofgraph.validate import (
    load_claim_evidence_schema,
    set_validation_result,
    validate_record,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic-pmc-oai.xml"
PUBLISHED_SCHEMA = ROOT / "schemas" / "claim-evidence.v0.2.schema.json"
BUNDLED_SCHEMA = (
    ROOT / "src" / "proofgraph" / "schemas" / "claim-evidence.v0.2.schema.json"
)
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
MANIFEST_ENTRY = {
    "id": "synthetic-jats-fixture",
    "pmcid": "PMC999999999",
    "doi": "10.0000/proofgraph.synthetic",
    "license": {"spdx": "CC-BY-4.0", "url": LICENSE},
}


def valid_record():
    document = parse_pmc_oai_jats(
        FIXTURE.read_bytes(),
        expected_pmcid="PMC999999999",
        expected_doi="10.0000/proofgraph.synthetic",
        expected_license_spdx="CC-BY-4.0",
        expected_license_url=LICENSE,
    )
    return extract_pmc_record(
        document, manifest_entry=MANIFEST_ENTRY, element_id="Par7"
    )


class SchemaRuntimeV02Tests(unittest.TestCase):
    def test_published_and_bundled_schemas_are_byte_identical(self) -> None:
        self.assertEqual(PUBLISHED_SCHEMA.read_bytes(), BUNDLED_SCHEMA.read_bytes())
        self.assertEqual(
            load_claim_evidence_schema("0.2.0"),
            json.loads(PUBLISHED_SCHEMA.read_text(encoding="utf-8")),
        )

    def test_extracted_record_is_v02_valid_and_unreviewed(self) -> None:
        record = valid_record()
        self.assertEqual(set_validation_result(record), [])
        self.assertEqual(record["validation"]["status"], "valid")
        self.assertEqual(record["review"]["status"], "unreviewed")

    def test_rejects_html_anchor_and_missing_provenance_objects(self) -> None:
        record = valid_record()
        record["source_anchor"]["type"] = "html_element"
        del record["source_artifact"]["attribution"]
        del record["source_artifact"]["retrieval"]

        errors = validate_record(record)

        self.assertTrue(any("attribution" in error for error in errors))
        self.assertTrue(any("retrieval" in error for error in errors))
        self.assertTrue(any("jats_element_text_span" in error for error in errors))

    def test_rejects_hash_span_evidence_and_identity_tampering(self) -> None:
        record = valid_record()
        record["source_anchor"]["evidence_text_sha256"] = "0" * 64
        record["source_anchor"]["character_end"] += 1
        record["source_artifact"]["identifier"] = "https://doi.org/10.0000/wrong"
        record["claim"]["reported_value"] = "9.9"

        errors = validate_record(record)

        self.assertIn(
            "source_anchor.evidence_text_sha256 does not match evidence_text", errors
        )
        self.assertIn(
            "source_anchor character span length does not match evidence_text", errors
        )
        self.assertIn(
            "source_artifact.identifier must be the canonical DOI URL", errors
        )
        self.assertIn("claim.reported_value is not supported by evidence_text", errors)

    def test_rejects_unknown_properties_and_review_states(self) -> None:
        record = valid_record()
        record["source_artifact"]["unknown"] = True
        record["review"]["status"] = "verified"

        errors = validate_record(record)

        self.assertTrue(any("Additional properties" in error for error in errors))
        self.assertIn("review.status is invalid", errors)

    def test_v01_default_schema_api_is_preserved(self) -> None:
        self.assertEqual(
            load_claim_evidence_schema()["properties"]["schema_version"]["const"],
            "0.1.0",
        )


if __name__ == "__main__":
    unittest.main()
