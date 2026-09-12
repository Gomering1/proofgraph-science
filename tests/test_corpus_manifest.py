from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmark" / "corpus-manifest.v0.1.json"
EXPECTED_DOIS = {
    "10.1038/s41467-023-40669-0",
    "10.1038/s41467-021-24697-2",
    "10.1038/s41467-024-55634-8",
    "10.1002/advs.202200213",
    "10.1038/s41467-024-45258-3",
}


class CorpusManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.papers = cls.manifest["papers"]

    def test_manifest_contains_the_five_reviewed_papers(self) -> None:
        self.assertEqual(len(self.papers), 5)
        self.assertEqual({paper["doi"] for paper in self.papers}, EXPECTED_DOIS)
        self.assertEqual(len({paper["id"] for paper in self.papers}), 5)

    def test_every_paper_has_explicit_rights_evidence_and_conservative_policy(self) -> None:
        for paper in self.papers:
            with self.subTest(doi=paper["doi"]):
                self.assertEqual(paper["doi_url"], f"https://doi.org/{paper['doi']}")
                self.assertTrue(paper["authors"])
                self.assertTrue(all(author.strip() for author in paper["authors"]))
                self.assertEqual(paper["pmcid"], urlparse(paper["pmc_url"]).path.split("/")[2])
                self.assertEqual(paper["license"]["spdx"], "CC-BY-4.0")
                self.assertEqual(
                    paper["license"]["url"],
                    "https://creativecommons.org/licenses/by/4.0/",
                )
                self.assertIn("License section", paper["license"]["evidence_location"])
                self.assertTrue(paper["license"]["evidence_url"].startswith("https://"))
                self.assertRegex(paper["license"]["checked_on"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertIn("Open-access", paper["access_basis"])
                self.assertIn("Do not commit article full text", paper["redistribution_policy"])
                self.assertIn("separate credit line", paper["third_party_materials_caveat"])

    def test_manifest_links_only_to_remote_assets(self) -> None:
        for paper in self.papers:
            for asset in paper["source_assets"]:
                with self.subTest(doi=paper["doi"], asset=asset["kind"]):
                    self.assertEqual(asset["status"], "link_only_not_downloaded")
                    self.assertEqual(urlparse(asset["url"]).scheme, "https")
                    self.assertNotIn("local_path", asset)
                    self.assertNotIn("content", asset)

    def test_nasicon_dataset_cannot_imply_underlying_sources_are_cleared(self) -> None:
        nasicon = next(
            paper for paper in self.papers if paper["id"] == "nasicon-design-principles-2023"
        )
        caveat = nasicon["dataset_caveat"]
        self.assertIn("475", caveat["applies_to"])
        self.assertIn("does not establish reuse rights", caveat["license_scope"])
        self.assertIn("independently verified", caveat["underlying_sources_policy"])
        self.assertIn("not uniform ground truth", caveat["scientific_comparability_warning"])
        self.assertIn("rights and evidence check", caveat["public_release_gate"])


if __name__ == "__main__":
    unittest.main()
