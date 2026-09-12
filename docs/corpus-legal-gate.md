# Five-paper pilot corpus: legal gate

The initial benchmark corpus is defined in
[`benchmark/corpus-manifest.v0.1.json`](../benchmark/corpus-manifest.v0.1.json).
It contains metadata and links for five open-access, primary-research papers on
solid-state electrolytes. It contains no article full text, figures, tables, or
supplementary files.

## What the manifest establishes

Each paper has a canonical DOI, publisher page, PubMed Central record, a CC BY
4.0 license URL, and a human-readable license-evidence location. These fields
make a source eligible for a manual ingestion review; they do not make ingestion
automatic. A reviewer must reconfirm the record and inspect the particular asset
before any text, table, figure, or supplement is processed.

CC BY 4.0 generally permits sharing and adaptation with attribution, a license
link, and an indication of changes. The article notices also preserve a crucial
exception: an image, table, or other third-party item may have a separate credit
line and different rights. ProofGraph therefore uses the most restrictive
applicable notice at the asset level. A paper-level license never overrides an
asset-specific restriction.

This file documents a conservative project gate, not legal advice.

## Pilot redistribution rule

The pilot should publish links, bibliographic metadata, content hashes, precise
source anchors, and ProofGraph's original annotations or derived claim records.
It should not commit copies of article HTML, XML, PDFs, figures, tables, or
supplements. If a later benchmark genuinely needs to redistribute source
excerpts or assets, add an asset-level record containing the observed license,
credit line, attribution, access date, and modification notice before release.

An underlying paper cited by one of the five articles is a separate source. It
must pass the same legal gate and receive its own manifest entry before its text
or assets are ingested or redistributed.

## Special case: the 475-record NASICON compilation

The supplement to *Design principles for NASICON super-ionic conductors*
contains a compilation of experimental conductivity information for 475
reported NASICON compositions drawn from prior literature. The article's CC BY
4.0 notice supports reuse of the authors' original article and supplementary
compilation, subject to attribution and asset-specific notices. It does not prove
that the full text, figures, or tables of every cited source can be reused.

For the first pilot:

1. Treat a row as reported by the 2023 NASICON article, while preserving its
   original cited-source field.
2. Do not attribute a row directly to an underlying paper until that paper's
   evidence and rights have been checked independently.
3. Do not fetch or redistribute any underlying paper merely because the dataset
   cites it.
4. Preserve measurement temperature, preparation and measurement information,
   and explicit missing-condition flags.
5. Do not present the 475 values as uniform or directly comparable ground truth.
   Their preparation and testing conditions vary, and important fields such as
   pellet density or interfacial resistance may be absent.

The manifest deliberately calls this a 475-record or 475-composition
compilation, not “475 independently cleared sources.”

## Review checklist

Before ingesting any asset, record:

- the manifest paper ID and exact asset URL;
- DOI-to-page identity check;
- observed license text, URL, and evidence location;
- access date and content hash;
- authors/title/journal attribution;
- every separate credit line or exclusion;
- whether the stored output is a source copy, excerpt, anchor, or derived record;
- the planned public-release treatment; and
- reviewer name or identifier and review timestamp.

If any field is uncertain, keep the asset link-only and exclude it from the
benchmark until the uncertainty is resolved.

The prototype's local `extract-pmc` command does not alter or satisfy this
checklist. It can compare a user-supplied OAI/JATS file with existing manifest
identity and license metadata and produce an explicitly unreviewed derived
record, but that deterministic processing is neither legal approval nor
scientific review. The command performs no automatic download and does not
persist the supplied source XML. The five-paper software run publishes only
source-text-free outcomes and hashes in
[`benchmark/five-paper-smoke-report.v0.1.json`](../benchmark/five-paper-smoke-report.v0.1.json);
its four records and one abstention do not change this gate.
