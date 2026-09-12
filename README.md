# ProofGraph Science

[![Tests](https://github.com/Gomering1/proofgraph-science/actions/workflows/test.yml/badge.svg)](https://github.com/Gomering1/proofgraph-science/actions/workflows/test.yml)

**Status: runnable pre-alpha vertical slice.**

This directory is a local vertical slice for the proposed open scientific evidence layer. It demonstrates one honest path from an authored HTML fixture to a structured claim-evidence record with an exact source element, content hash, normalized value and unit, experimental conditions, extraction provenance, and deterministic validation. It also contains a narrow, offline PMC OAI/JATS parser with manifest-selected rules for a five-paper local smoke test. Four articles emit unreviewed records and one deliberately abstains because its required qualifiers cross paragraph boundaries. No real article XML is bundled.

It is not a scientific truth engine, a battery-discovery model, or a production parser. The first extractor is deliberately small and rule-based. The grant-funded work would replace and compare extractors while keeping the evidence schema, validation, and review boundaries explicit.

## Why this exists

Scientific AI systems can turn papers into fluent answers, but a citation alone does not preserve the exact evidence, units, conditions, uncertainty, or processing history behind each generated claim. ProofGraph treats a source-linked claim-evidence record as the reusable object. The first reference domain is solid-state battery electrolytes, where a conductivity value is not meaningful without its composition, temperature, and measurement method.

## Run the demo

Python 3.10 or newer is required. Install the package so the Draft 2020-12
validator and bundled schema are available:

```bash
git clone https://github.com/Gomering1/proofgraph-science.git
cd proofgraph-science
python3 -m pip install .
proofgraph extract examples/fixtures/authored-electrolyte-example.html --out result.json
proofgraph validate result.json
```

The expected output is committed at `examples/expected/authored-electrolyte-example.json`. The generated timestamp and recorded Python version can differ between runs; the content hash changes if the fixture changes.

The demo produces an explicitly unreviewed record shaped like this:

```json
{
  "source_anchor": {
    "type": "html_element",
    "element_id": "conductivity-claim"
  },
  "claim": {
    "subject": "Li6PS5Cl",
    "property": "ionic_conductivity",
    "normalized_value": "0.0012",
    "normalized_unit": "S/cm"
  },
  "qualifiers": {
    "temperature_value": "25",
    "temperature_unit": "°C",
    "measurement_method": "electrochemical impedance spectroscopy"
  },
  "validation": { "status": "valid", "errors": [] },
  "review": { "status": "unreviewed" }
}
```

## Process a local PMC OAI/JATS response

`extract-pmc` processes one user-supplied local OAI-PMH `GetRecord` XML file.
It performs no network request, writes no cache or source copy, and reads the
corpus manifest only to assert the expected PMCID, DOI, and CC BY 4.0 license:

```bash
proofgraph extract-pmc /path/to/PMC8292426-oai.xml \
  --manifest benchmark/corpus-manifest.v0.1.json \
  --pmcid PMC8292426 \
  --out result.json
proofgraph validate result.json
```

The manifest declares the exact local-smoke-test profile and locator.
`--element-id` remains available as an optional assertion and is required for a
manifest entry without such a locator. The command fails closed on OAI, JATS
version, identity, open-access, embargo, license, anchor, or extraction
mismatches. Exit code `3` is a documented extraction abstention and writes no
record when the requested output path is absent. Both extraction commands
reject a pre-existing `--out` before extraction with exit code `2` and leave it
unchanged; choose a new output path for every attempt. A successful result is
schema-valid and `unreviewed`; it is not a claim that the scientific fact or
legal review has been verified. Supplying a local source remains the operator's
responsibility, and the manifest's documented legal gate remains unchanged.

A local smoke test against all five official PMC OAI/JATS responses has
exercised this path without adding source articles or generated records to the
repository.
See [`docs/real-paper-smoke-test.md`](docs/real-paper-smoke-test.md) for the
derived fields, hashes, and limitations, and
[`benchmark/five-paper-smoke-report.v0.1.json`](benchmark/five-paper-smoke-report.v0.1.json)
for the same outcomes in a source-text-free machine-readable form.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

## Current implementation

- parses authored HTML into elements with stable `id` anchors;
- recognizes one narrow ionic-conductivity statement pattern;
- normalizes `mS cm−1` to `S/cm`;
- parses a local PMC OAI-PMH response containing namespaced JATS 1.4, checks the
  asserted PMCID/DOI/CC BY 4.0 metadata, and hashes the canonicalized `article`
  subtree rather than the changing OAI wrapper;
- runs four narrow, manifest-selected conductivity rules across the five-paper
  corpus and returns a documented abstention for the cross-paragraph case;
- anchors source text either to a native-ID body paragraph or, when publisher
  JATS omits paragraph IDs, to an exact paragraph path under a native-ID
  section, while excluding figure, table, supplementary, reference, and
  boxed-text subtrees;
- emits v0.2 PMC records with attribution, retrieval provenance, exact
  normalized-text offsets and hashes; uses the locator-only v0.3 extension for
  an ID-less paragraph while leaving v0.1 and v0.2 unchanged;
- records source SHA-256, extractor version, Python version, timestamp, and review state;
- executes the published Draft 2020-12 JSON Schema before checking required source and provenance fields, supported property/unit values, temperature, and whether the extracted subject and reported value occur in the anchored evidence;
- declares a link-only five-paper pilot corpus with canonical identifiers,
  license evidence, asset-level review gates, and no redistributed article text;
- fails closed when required evidence is absent.

## Not implemented yet

- PDF geometry, OCR, tables, figures, and supplementary files;
- model adapters or LLM/VLM inference;
- domain reviewer workflow and immutable edits;
- conflict-candidate retrieval;
- JSON-LD, PROV-O, and RO-Crate mappings;
- bundled source copies, automatic download, broad ingestion, human annotation,
  or scientific evaluation of the five real papers.

The funding applications must not describe any item in this list as already working.

## Six-month target

The proposed funded release would add lawful PDF/HTML ingestion, source geometry, tables and figures, open-model adapters, immutable human review, a public benchmark, and reproducible quality/cost comparisons. Large open-weight models would be evaluated on a local reference workstation, while a smaller public profile would remain usable on ordinary hardware. See [`docs/roadmap.md`](docs/roadmap.md) for the milestones.

## Data and safety

The repository contains no article copies, paywalled papers, or private
laboratory documents. The executable fixture is synthetic and released under
CC0-1.0. The link-only pilot list and its legal gate are documented in
[`benchmark/corpus-manifest.v0.1.json`](benchmark/corpus-manifest.v0.1.json) and
[`docs/corpus-legal-gate.md`](docs/corpus-legal-gate.md). See
[`DATA_POLICY.md`](DATA_POLICY.md) and [`SECURITY.md`](SECURITY.md) before adding
any source material.

## License

Code is licensed under Apache-2.0. The synthetic fixture is dedicated to the public domain under CC0-1.0 as stated in the fixture metadata and data policy.
