# ProofGraph Science

[![Tests](https://github.com/Gomering1/proofgraph-science/actions/workflows/test.yml/badge.svg)](https://github.com/Gomering1/proofgraph-science/actions/workflows/test.yml)

**Status: runnable pre-alpha vertical slice.**

This directory is a local vertical slice for the proposed open scientific evidence layer. It demonstrates one honest path from an authored HTML fixture to a structured claim-evidence record with an exact source element, content hash, normalized value and unit, experimental conditions, extraction provenance, and deterministic validation.

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

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

## Current implementation

- parses authored HTML into elements with stable `id` anchors;
- recognizes one narrow ionic-conductivity statement pattern;
- normalizes `mS cm−1` to `S/cm`;
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
- ingestion, annotation, or evaluation of the five real papers.

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
