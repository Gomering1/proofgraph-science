from __future__ import annotations

from pathlib import Path
import unittest

from proofgraph.jats import iter_body_paragraphs
from proofgraph.pmc import (
    PmcIdentityError,
    PmcParseError,
    PmcRightsError,
    normalize_pmcid,
    parse_pmc_oai_jats,
    pmc_oai_url,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic-pmc-oai.xml"
PMCID = "PMC999999999"
DOI = "10.0000/proofgraph.synthetic"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"


def parse_fixture(raw: bytes | None = None):
    return parse_pmc_oai_jats(
        FIXTURE.read_bytes() if raw is None else raw,
        expected_pmcid=PMCID,
        expected_doi=DOI,
        expected_license_spdx="CC-BY-4.0",
        expected_license_url=LICENSE,
    )


class PmcJatsTests(unittest.TestCase):
    def test_normalizes_pmcid_and_builds_only_fixed_oai_url(self) -> None:
        self.assertEqual(normalize_pmcid("pmc999999999"), PMCID)
        self.assertEqual(
            pmc_oai_url(PMCID),
            "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
            "?verb=GetRecord&identifier=oai%3Apubmedcentral.nih.gov%3A999999999"
            "&metadataPrefix=pmc",
        )
        for invalid in ("9990001", "PMC", "PMC1/../x", "https://example.test/PMC1"):
            with self.subTest(invalid=invalid), self.assertRaises(PmcIdentityError):
                normalize_pmcid(invalid)

    def test_parses_identity_rights_attribution_and_stable_article_hash(self) -> None:
        first = parse_fixture()
        changed_wrapper = FIXTURE.read_bytes().replace(
            b"2026-09-11T18:30:00Z", b"2026-09-11T18:31:00Z"
        )
        second = parse_fixture(changed_wrapper)

        self.assertEqual(first.pmcid, PMCID)
        self.assertEqual(first.pmcid_version, f"{PMCID}.1")
        self.assertEqual(first.doi, DOI)
        self.assertEqual(first.authors, ("Ada Fixture", "Lin Example"))
        self.assertEqual(first.content_sha256, second.content_sha256)
        self.assertNotEqual(first.retrieved_at, second.retrieved_at)

    def test_emits_native_id_path_and_flattens_only_paragraph_prose(self) -> None:
        document = parse_fixture()
        paragraphs = iter_body_paragraphs(document.article)

        self.assertEqual([paragraph.element_id for paragraph in paragraphs], ["Par7"])
        paragraph = paragraphs[0]
        self.assertEqual(
            paragraph.xpath,
            "article/body/sec[@id='Sec2']/p[@id='Par7']",
        )
        self.assertIn("Li2ZrCl6", paragraph.text)
        self.assertIn("10−4 S cm−1", paragraph.text)
        self.assertIn("Figure-tail prose remains.", paragraph.text)
        self.assertNotIn("Excluded caption", paragraph.text)
        self.assertNotIn("Excluded table", paragraph.text)

    def test_fails_closed_on_structure_identity_and_rights_mismatches(self) -> None:
        raw = FIXTURE.read_bytes()
        cases = (
            (
                raw.replace(b"<setSpec>pmc-open</setSpec>", b"<setSpec>other</setSpec>"),
                PmcRightsError,
            ),
            (
                raw.replace(b"<meta-value>yes</meta-value>", b"<meta-value>no</meta-value>", 1),
                PmcRightsError,
            ),
            (
                raw.replace(
                    b"<meta-value>no</meta-value>", b"<meta-value>yes</meta-value>", 1
                ),
                PmcRightsError,
            ),
            (
                raw.replace(b"10.0000/proofgraph.synthetic", b"10.0000/wrong"),
                PmcIdentityError,
            ),
            (
                raw.replace(
                    b"https://creativecommons.org/licenses/by/4.0/",
                    b"https://example.test/license",
                ),
                PmcRightsError,
            ),
            (b"<not-xml", PmcParseError),
        )
        for changed, error in cases:
            with self.subTest(error=error.__name__), self.assertRaises(error):
                parse_fixture(changed)

    def test_rejects_oai_errors_multiple_articles_and_unsafe_declarations(self) -> None:
        oai_error = (
            b'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
            b'<error code="idDoesNotExist">missing</error></OAI-PMH>'
        )
        with self.assertRaisesRegex(PmcParseError, "idDoesNotExist"):
            parse_fixture(oai_error)

        raw = FIXTURE.read_bytes()
        article_start = raw.index(b'<article xmlns="https://jats.nlm.nih.gov/ns/archiving/1.4/"')
        article_end = raw.index(b"</article>", article_start) + len(b"</article>")
        duplicate = raw[:article_end] + raw[article_start:article_end] + raw[article_end:]
        with self.assertRaisesRegex(PmcParseError, "found 2"):
            parse_fixture(duplicate)

        with self.assertRaisesRegex(PmcParseError, "DTD"):
            parse_fixture(b"<!DOCTYPE x><x />")

    def test_rejects_nonfixed_retrieval_url_and_oversized_input(self) -> None:
        with self.assertRaises(PmcIdentityError):
            parse_pmc_oai_jats(
                FIXTURE.read_bytes(),
                expected_pmcid=PMCID,
                expected_doi=DOI,
                expected_license_spdx="CC-BY-4.0",
                expected_license_url=LICENSE,
                retrieval_url="https://example.test/article.xml",
            )
        with self.assertRaisesRegex(PmcParseError, "exceeds"):
            parse_pmc_oai_jats(
                FIXTURE.read_bytes(),
                expected_pmcid=PMCID,
                expected_doi=DOI,
                expected_license_spdx="CC-BY-4.0",
                expected_license_url=LICENSE,
                max_xml_bytes=10,
            )


if __name__ == "__main__":
    unittest.main()
