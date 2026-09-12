from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest

from proofgraph.extract import extract_pmc_record
from proofgraph.pmc import parse_pmc_oai_jats


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic-pmc-oai.xml"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
MANIFEST_ENTRY = {
    "id": "synthetic-jats-fixture",
    "pmcid": "PMC999999999",
    "doi": "10.0000/proofgraph.synthetic",
    "license": {"spdx": "CC-BY-4.0", "url": LICENSE},
}


def parse_fixture(raw: bytes | None = None):
    return parse_pmc_oai_jats(
        FIXTURE.read_bytes() if raw is None else raw,
        expected_pmcid="PMC999999999",
        expected_doi="10.0000/proofgraph.synthetic",
        expected_license_spdx="CC-BY-4.0",
        expected_license_url=LICENSE,
    )


class PmcExtractionTests(unittest.TestCase):
    def test_extracts_narrow_par7_record_and_normalizes_scientific_notation(self) -> None:
        record = extract_pmc_record(
            parse_fixture(), manifest_entry=MANIFEST_ENTRY, element_id="Par7"
        )

        self.assertEqual(record["schema_version"], "0.2.0")
        self.assertEqual(record["claim"]["subject"], "Li2ZrCl6")
        self.assertEqual(record["claim"]["subject_alias"], "LZC")
        self.assertEqual(record["claim"]["reported_value"], "8.08 × 10−4")
        self.assertEqual(record["claim"]["reported_unit"], "S cm−1")
        self.assertEqual(record["claim"]["normalized_value"], "0.000808")
        self.assertEqual(record["claim"]["normalized_unit"], "S/cm")
        self.assertEqual(record["qualifiers"]["temperature_value"], "25")
        self.assertEqual(
            record["qualifiers"]["measurement_method"],
            "electrochemical impedance spectroscopy",
        )
        self.assertEqual(record["qualifiers"]["sample_condition"], "as-milled")
        self.assertEqual(record["review"]["status"], "unreviewed")

    def test_anchors_exact_half_open_span_and_hashes(self) -> None:
        record = extract_pmc_record(
            parse_fixture(), manifest_entry=MANIFEST_ENTRY, element_id="Par7"
        )
        anchor = record["source_anchor"]
        evidence = anchor["evidence_text"]

        self.assertEqual(anchor["character_start"], 0)
        self.assertEqual(anchor["character_end"], len(evidence))
        self.assertTrue(evidence.endswith("."))
        self.assertEqual(
            anchor["evidence_text_sha256"],
            sha256(evidence.encode("utf-8")).hexdigest(),
        )
        self.assertNotIn("electronic conductivity", evidence)
        self.assertNotIn("Excluded caption", evidence)

    def test_supports_ordinary_si_prefix_form(self) -> None:
        raw = FIXTURE.read_bytes().replace(
            "8.08&#160;×&#160;10<sup>−4</sup> S cm<sup>−1</sup>".encode(),
            "0.808 mS cm<sup>−1</sup>".encode(),
        )
        record = extract_pmc_record(
            parse_fixture(raw), manifest_entry=MANIFEST_ENTRY, element_id="Par7"
        )
        self.assertEqual(record["claim"]["reported_value"], "0.808")
        self.assertEqual(record["claim"]["reported_unit"], "mS cm−1")
        self.assertEqual(record["claim"]["normalized_value"], "0.000808")

    def test_keeps_the_as_milled_link_across_actual_par7_sized_context(self) -> None:
        raw = FIXTURE.read_bytes().replace(
            b"as-milled condition. Electrochemical",
            b"as-milled condition. " + (b"synthetic context " * 10) + b"Electrochemical",
        )
        record = extract_pmc_record(
            parse_fixture(raw), manifest_entry=MANIFEST_ENTRY, element_id="Par7"
        )
        self.assertEqual(record["claim"]["normalized_value"], "0.000808")

    def test_ignores_later_electronic_conductivity(self) -> None:
        record = extract_pmc_record(
            parse_fixture(), manifest_entry=MANIFEST_ENTRY, element_id="Par7"
        )
        self.assertNotEqual(record["claim"]["reported_value"], "2.10 × 10−8")
        self.assertEqual(record["claim"]["reported_value"], "8.08 × 10−4")

    def test_fails_closed_when_required_evidence_is_absent(self) -> None:
        raw = FIXTURE.read_bytes()
        replacements = (
            (b"Li<sub>2</sub>ZrCl<sub>6</sub> (LZC)", b"sample"),
            (b"Electrochemical impedance spectroscopy", b"A measurement"),
            (b"as-milled", b"prepared"),
            (b"ionic conductivity", b"transport property"),
            (b"25 \xc2\xb0C", b"room conditions"),
        )
        for old, new in replacements:
            with self.subTest(missing=old):
                changed = raw.replace(old, new, 1)
                with self.assertRaises(ValueError):
                    extract_pmc_record(
                        parse_fixture(changed),
                        manifest_entry=MANIFEST_ENTRY,
                        element_id="Par7",
                    )

    def test_requires_one_native_id_paragraph_and_matching_manifest(self) -> None:
        document = parse_fixture()
        with self.assertRaisesRegex(ValueError, "found 0"):
            extract_pmc_record(
                document, manifest_entry=MANIFEST_ENTRY, element_id="Missing"
            )
        wrong_manifest = {**MANIFEST_ENTRY, "doi": "10.0000/wrong"}
        with self.assertRaisesRegex(ValueError, "manifest DOI"):
            extract_pmc_record(
                document, manifest_entry=wrong_manifest, element_id="Par7"
            )


if __name__ == "__main__":
    unittest.main()
