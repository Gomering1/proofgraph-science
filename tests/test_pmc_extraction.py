from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import unittest

from proofgraph.extract import PmcExtractionAbstention, extract_pmc_record
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

NASICON_SYNTHETIC_TEXT = (
    "SYNTHETIC NASICON FIXTURE. Method marker: EIS. Electrode marker: Na metal "
    "as electrodes. Ordered material tokens: Na3.2Hf0.8Sc0.2ZrSi2PO12 and "
    "Na3.4Hf0.6Sc0.4ZrSi2PO12. Parser-only property marker: total ionic "
    "conductivity of 0.480 and 1.20 mS cm−1, respectively. Temperature marker: "
    "~ 25 °C. END SYNTHETIC FIXTURE."
)
HALIDE_SYNTHETIC_TEXT = (
    "SYNTHETIC HALIDE FIXTURE. Method marker: electrochemical impedance "
    "spectroscopy (EIS). State marker: as-prepared. Relation marker: HE-SE "
    "exhibits a higher ionic conductivity of around 2.130 mS cm−1; temperature "
    "marker: 25 °C. END SYNTHETIC FIXTURE."
)
COMPOSITE_SYNTHETIC_TEXT = (
    "SYNTHETIC COMPOSITE FIXTURE. Subject marker: composite SSEs. Method marker: "
    "joint analysis of CA, EIS, and DS spectra. Temperature marker: 30 °C. "
    "Property marker: the maximum total ionic conductivity of 3.10×10−5 S cm−1 "
    "was obtained at volume fraction of added TiO2 of 10%. END SYNTHETIC FIXTURE."
)


def parse_fixture(raw: bytes | None = None):
    return parse_pmc_oai_jats(
        FIXTURE.read_bytes() if raw is None else raw,
        expected_pmcid="PMC999999999",
        expected_doi="10.0000/proofgraph.synthetic",
        expected_license_spdx="CC-BY-4.0",
        expected_license_url=LICENSE,
    )


def fixture_with_paragraph(
    text: str,
    *,
    element_id: str | None = "Par7",
    section_id: str = "Sec2",
):
    raw = FIXTURE.read_text(encoding="utf-8")
    identifier = f' id="{element_id}"' if element_id is not None else ""
    replacement = f"              <p{identifier}>{text}</p>"
    changed, count = re.subn(
        r'^\s*<p id="Par7">.*</p>$',
        replacement,
        raw,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise AssertionError("could not replace authored fixture paragraph")
    changed = changed.replace('<sec id="Sec2">', f'<sec id="{section_id}">', 1)
    return parse_fixture(changed.encode("utf-8"))


def profile_manifest(
    profile: str,
    locator: dict,
    *,
    status: str = "candidate_unreviewed",
) -> dict:
    return {
        **MANIFEST_ENTRY,
        "local_smoke_test": {
            "status": status,
            "profile": profile,
            "locator": locator,
        },
    }


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

    def test_extracts_nasicon_profile_without_treating_pair_as_one_material(self) -> None:
        document = fixture_with_paragraph(NASICON_SYNTHETIC_TEXT)
        record = extract_pmc_record(
            document,
            manifest_entry=profile_manifest(
                "nasicon_sc04_v1",
                {"type": "native_id", "element_id": "Par7"},
            ),
            element_id=None,
        )

        self.assertEqual(record["claim"]["subject"], "Na3.4Hf0.6Sc0.4ZrSi2PO12")
        self.assertEqual(record["claim"]["normalized_value"], "0.0012")
        self.assertEqual(record["qualifiers"]["measurement_method"], "EIS")
        self.assertEqual(record["qualifiers"]["temperature_value"], "25")
        self.assertNotIn("sample_condition", record["qualifiers"])
        self.assertIsNone(record["uncertainty"]["reported"])

    def test_nasicon_profile_rejects_broken_or_negated_pair_relation(self) -> None:
        cases = {
            "electronic": NASICON_SYNTHETIC_TEXT.replace(
                "total ionic conductivity", "total electronic conductivity"
            ),
            "missing-order-word": NASICON_SYNTHETIC_TEXT.replace(
                "respectively", "jointly"
            ),
            "negated": NASICON_SYNTHETIC_TEXT.replace(
                "total ionic conductivity", "not total ionic conductivity"
            ),
        }
        manifest_entry = profile_manifest(
            "nasicon_sc04_v1",
            {"type": "native_id", "element_id": "Par7"},
        )

        for case, text in cases.items():
            with self.subTest(case=case), self.assertRaisesRegex(
                ValueError, "NASICON ordered material/value relation"
            ):
                extract_pmc_record(
                    fixture_with_paragraph(text),
                    manifest_entry=manifest_entry,
                    element_id=None,
                )

    def test_nasicon_profile_does_not_anchor_an_earlier_subject_decoy(self) -> None:
        decoy = "Na3.4Hf0.6Sc0.4ZrSi2PO12 DECOY PREFIX. "
        record = extract_pmc_record(
            fixture_with_paragraph(decoy + NASICON_SYNTHETIC_TEXT),
            manifest_entry=profile_manifest(
                "nasicon_sc04_v1",
                {"type": "native_id", "element_id": "Par7"},
            ),
            element_id=None,
        )

        self.assertEqual(record["claim"]["subject"], "Na3.4Hf0.6Sc0.4ZrSi2PO12")
        self.assertNotIn("DECOY PREFIX", record["source_anchor"]["evidence_text"])
        self.assertGreater(record["source_anchor"]["character_start"], len(decoy))

    def test_extracts_halide_profile_but_keeps_unresolved_source_alias(self) -> None:
        document = fixture_with_paragraph(HALIDE_SYNTHETIC_TEXT)
        record = extract_pmc_record(
            document,
            manifest_entry=profile_manifest(
                "halide_he_se_v1",
                {"type": "native_id", "element_id": "Par7"},
            ),
            element_id="Par7",
        )

        self.assertEqual(record["claim"]["subject"], "HE-SE")
        self.assertNotIn("subject_alias", record["claim"])
        self.assertEqual(record["claim"]["normalized_value"], "0.00213")
        self.assertEqual(record["uncertainty"]["reported"], "around")
        self.assertIn("ionic conductivity", record["source_anchor"]["evidence_text"])

    def test_halide_profile_rejects_electronic_conductivity_relation(self) -> None:
        document = fixture_with_paragraph(
            HALIDE_SYNTHETIC_TEXT.replace(
                "higher ionic conductivity", "higher electronic conductivity"
            )
        )

        with self.assertRaisesRegex(ValueError, "halide target.*explicit ionic"):
            extract_pmc_record(
                document,
                manifest_entry=profile_manifest(
                    "halide_he_se_v1",
                    {"type": "native_id", "element_id": "Par7"},
                ),
                element_id=None,
            )

    def test_halide_profile_rejects_non_ionic_conductivity_relation(self) -> None:
        document = fixture_with_paragraph(
            HALIDE_SYNTHETIC_TEXT.replace(
                "higher ionic conductivity", "higher non-ionic conductivity"
            )
        )

        with self.assertRaisesRegex(ValueError, "halide target.*explicit ionic"):
            extract_pmc_record(
                document,
                manifest_entry=profile_manifest(
                    "halide_he_se_v1",
                    {"type": "native_id", "element_id": "Par7"},
                ),
                element_id=None,
            )

    def test_halide_profile_rejects_negated_ionic_conductivity_relation(self) -> None:
        document = fixture_with_paragraph(
            HALIDE_SYNTHETIC_TEXT.replace(
                "HE-SE exhibits a higher ionic conductivity",
                "HE-SE does not exhibit an ionic conductivity",
            )
        )

        with self.assertRaisesRegex(ValueError, "halide target.*explicit ionic"):
            extract_pmc_record(
                document,
                manifest_entry=profile_manifest(
                    "halide_he_se_v1",
                    {"type": "native_id", "element_id": "Par7"},
                ),
                element_id=None,
            )

    def test_halide_profile_rejects_far_temperature_on_either_side(self) -> None:
        claim = (
            "SYNTHETIC HALIDE FIXTURE. Method marker: electrochemical impedance "
            "spectroscopy. State marker: as-prepared. Relation marker: HE-SE "
            "exhibits a higher ionic conductivity of around 2.130 mS cm−1."
        )
        cases = (
            (
                "before",
                "Temperature marker: 25 °C. " + ("padding token " * 12) + claim,
            ),
            (
                "after",
                claim + (" padding token" * 12) + " Temperature marker: 25 °C.",
            ),
        )
        manifest_entry = profile_manifest(
            "halide_he_se_v1",
            {"type": "native_id", "element_id": "Par7"},
        )
        for side, text in cases:
            with self.subTest(side=side), self.assertRaisesRegex(
                ValueError, "temperature is not adjacent"
            ):
                extract_pmc_record(
                    fixture_with_paragraph(text),
                    manifest_entry=manifest_entry,
                    element_id=None,
                )

    def test_extracts_composite_profile_from_id_bearing_section_position(self) -> None:
        document = fixture_with_paragraph(
            COMPOSITE_SYNTHETIC_TEXT,
            element_id=None,
            section_id="advs3904-sec-0030",
        )
        record = extract_pmc_record(
            document,
            manifest_entry=profile_manifest(
                "composite_tio2_v1",
                {
                    "type": "section_child",
                    "section_id": "advs3904-sec-0030",
                    "paragraph_position": 1,
                },
            ),
            element_id=None,
        )

        self.assertEqual(record["claim"]["subject"], "composite SSEs")
        self.assertEqual(record["claim"]["normalized_value"], "0.000031")
        self.assertEqual(
            record["source_anchor"]["xpath"],
            "article/body/sec[@id='advs3904-sec-0030']/p[1]",
        )
        self.assertEqual(
            record["source_anchor"]["ancestor_element_id"],
            "advs3904-sec-0030",
        )
        self.assertIsNone(record["source_anchor"]["element_id"])
        self.assertEqual(record["schema_version"], "0.3.0")
        self.assertIn(
            "total ionic conductivity", record["source_anchor"]["evidence_text"]
        )

    def test_composite_profile_rejects_electronic_conductivity_relation(self) -> None:
        document = fixture_with_paragraph(
            COMPOSITE_SYNTHETIC_TEXT.replace(
                "total ionic conductivity", "total electronic conductivity"
            ),
            element_id=None,
            section_id="advs3904-sec-0030",
        )

        with self.assertRaisesRegex(ValueError, "composite target.*explicit ionic"):
            extract_pmc_record(
                document,
                manifest_entry=profile_manifest(
                    "composite_tio2_v1",
                    {
                        "type": "section_child",
                        "section_id": "advs3904-sec-0030",
                        "paragraph_position": 1,
                    },
                ),
                element_id=None,
            )

    def test_composite_profile_rejects_no_ionic_conductivity_relation(self) -> None:
        document = fixture_with_paragraph(
            COMPOSITE_SYNTHETIC_TEXT.replace(
                "the maximum total ionic conductivity",
                "no total ionic conductivity",
            ),
            element_id=None,
            section_id="advs3904-sec-0030",
        )

        with self.assertRaisesRegex(ValueError, "composite target.*explicit ionic"):
            extract_pmc_record(
                document,
                manifest_entry=profile_manifest(
                    "composite_tio2_v1",
                    {
                        "type": "section_child",
                        "section_id": "advs3904-sec-0030",
                        "paragraph_position": 1,
                    },
                ),
                element_id=None,
            )

    def test_composite_profile_rejects_negated_result_predicate(self) -> None:
        document = fixture_with_paragraph(
            COMPOSITE_SYNTHETIC_TEXT.replace(
                "was obtained at", "was not obtained at"
            ),
            element_id=None,
            section_id="advs3904-sec-0030",
        )

        with self.assertRaisesRegex(ValueError, "affirmative result"):
            extract_pmc_record(
                document,
                manifest_entry=profile_manifest(
                    "composite_tio2_v1",
                    {
                        "type": "section_child",
                        "section_id": "advs3904-sec-0030",
                        "paragraph_position": 1,
                    },
                ),
                element_id=None,
            )

    def test_composite_profile_rejects_far_temperature_on_either_side(self) -> None:
        claim = (
            "SYNTHETIC COMPOSITE FIXTURE. Subject marker: composite SSEs. Method "
            "marker: joint analysis of CA, EIS, and DS spectra. Property marker: "
            "the maximum total ionic conductivity of 3.10×10−5 S cm−1 was obtained "
            "at volume fraction of added TiO2 of 10%."
        )
        cases = (
            (
                "before",
                "Temperature marker: 30 °C. " + ("padding token " * 30) + claim,
            ),
            (
                "after",
                claim + (" padding token" * 30) + " Temperature marker: 30 °C.",
            ),
        )
        manifest_entry = profile_manifest(
            "composite_tio2_v1",
            {
                "type": "section_child",
                "section_id": "advs3904-sec-0030",
                "paragraph_position": 1,
            },
        )
        for side, text in cases:
            with self.subTest(side=side), self.assertRaisesRegex(
                ValueError, "temperature is not close enough"
            ):
                extract_pmc_record(
                    fixture_with_paragraph(
                        text,
                        element_id=None,
                        section_id="advs3904-sec-0030",
                    ),
                    manifest_entry=manifest_entry,
                    element_id=None,
                )

    def test_air_exposure_profile_abstains_on_cross_paragraph_qualifiers(self) -> None:
        document = fixture_with_paragraph(
            "SYNTHETIC ABSTENTION FIXTURE. Subject token: UDSH@LPSC. Value token: "
            "0.8 ± 0.27 mS cm-1. Duration token: 3 days. END SYNTHETIC FIXTURE."
        )
        manifest_entry = profile_manifest(
            "air_exposure_abstain_v1",
            {"type": "native_id", "element_id": "Par7"},
            status="documented_abstention",
        )

        with self.assertRaisesRegex(
            PmcExtractionAbstention, "cross_paragraph_qualifiers_not_supported"
        ):
            extract_pmc_record(
                document,
                manifest_entry=manifest_entry,
                element_id=None,
            )

    def test_manifest_locator_is_an_assertion_not_a_silent_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match manifest locator"):
            extract_pmc_record(
                parse_fixture(),
                manifest_entry=profile_manifest(
                    "lzc_as_milled_v1",
                    {"type": "native_id", "element_id": "Par7"},
                ),
                element_id="Wrong",
            )


if __name__ == "__main__":
    unittest.main()
