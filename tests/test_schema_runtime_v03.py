from __future__ import annotations

import json
from pathlib import Path
import re
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
PUBLISHED_SCHEMA = ROOT / "schemas" / "claim-evidence.v0.3.schema.json"
BUNDLED_SCHEMA = (
    ROOT / "src" / "proofgraph" / "schemas" / "claim-evidence.v0.3.schema.json"
)
LICENSE = "https://creativecommons.org/licenses/by/4.0/"


def valid_record() -> dict:
    raw = FIXTURE.read_text(encoding="utf-8")
    replacement = (
        "              <p>SYNTHETIC SCHEMA FIXTURE. Subject marker: composite "
        "SSEs. Method marker: joint analysis of CA, EIS, and DS spectra. "
        "Temperature marker: 30 °C. Property marker: the maximum total ionic "
        "conductivity of 3.10×10−5 S cm−1 was obtained at volume fraction of "
        "added TiO2 of 10%. END SYNTHETIC FIXTURE.</p>"
    )
    changed, count = re.subn(
        r'^\s*<p id="Par7">.*</p>$',
        replacement,
        raw,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise AssertionError("could not replace authored fixture paragraph")
    changed = changed.replace(
        '<sec id="Sec2">', '<sec id="advs3904-sec-0030">', 1
    )
    document = parse_pmc_oai_jats(
        changed.encode("utf-8"),
        expected_pmcid="PMC999999999",
        expected_doi="10.0000/proofgraph.synthetic",
        expected_license_spdx="CC-BY-4.0",
        expected_license_url=LICENSE,
    )
    manifest_entry = {
        "id": "synthetic-jats-fixture",
        "pmcid": "PMC999999999",
        "doi": "10.0000/proofgraph.synthetic",
        "license": {"spdx": "CC-BY-4.0", "url": LICENSE},
        "local_smoke_test": {
            "status": "candidate_unreviewed",
            "profile": "composite_tio2_v1",
            "locator": {
                "type": "section_child",
                "section_id": "advs3904-sec-0030",
                "paragraph_position": 1,
            },
        },
    }
    return extract_pmc_record(
        document,
        manifest_entry=manifest_entry,
        element_id=None,
    )


class SchemaRuntimeV03Tests(unittest.TestCase):
    def test_published_and_bundled_schemas_are_byte_identical(self) -> None:
        self.assertEqual(PUBLISHED_SCHEMA.read_bytes(), BUNDLED_SCHEMA.read_bytes())
        self.assertEqual(
            load_claim_evidence_schema("0.3.0"),
            json.loads(PUBLISHED_SCHEMA.read_text(encoding="utf-8")),
        )

    def test_idless_paragraph_record_is_v03_valid_and_scoped(self) -> None:
        record = valid_record()
        self.assertEqual(record["schema_version"], "0.3.0")
        self.assertEqual(set_validation_result(record), [])
        anchor = record["source_anchor"]
        self.assertIsNone(anchor["element_id"])
        self.assertEqual(anchor["ancestor_element_id"], "advs3904-sec-0030")
        self.assertEqual(anchor["locator_scope"], "native_ancestor_plus_xpath")
        self.assertIn("[@id='advs3904-sec-0030']", anchor["xpath"])

    def test_rejects_overloaded_or_unrelated_locator_ids(self) -> None:
        record = valid_record()
        record["source_anchor"]["element_id"] = "advs3904-sec-0030"
        errors = validate_record(record)
        self.assertTrue(any("element_id" in error for error in errors))

        record = valid_record()
        record["source_anchor"]["ancestor_element_id"] = "unrelated-section"
        errors = validate_record(record)
        self.assertIn(
            "source_anchor.xpath does not contain ancestor_element_id", errors
        )


if __name__ == "__main__":
    unittest.main()
