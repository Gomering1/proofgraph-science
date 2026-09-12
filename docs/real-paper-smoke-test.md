# Five-paper local smoke test

Run date: 2026-09-11 PDT (official OAI responses: 2026-09-12 UTC)

This is a reproducibility note for a local software smoke test, not a
scientific benchmark. Three schema v0.2 records and one locator-only schema
v0.3 record were emitted with review status `unreviewed`; the fifth article
produced a documented abstention. No record in this run was checked by a domain
reviewer. Schema v0.3 changes only source-locator representation for a
paragraph without a native ID; v0.1 and v0.2 remain unchanged.

## Input and controls

- Source: official NCBI PMC OAI-PMH `GetRecord` responses for the five entries
  in [`benchmark/corpus-manifest.v0.1.json`](../benchmark/corpus-manifest.v0.1.json)
- Rights gate: the parser rechecked the expected PMCID, DOI, `pmc-open` set,
  open-access flag, no-embargo flag, and exact `CC-BY-4.0` license URL
- Source handling: XML inputs and emitted records remained in temporary local
  directories; neither is included in this repository
- Anchor handling: figures, tables, media, supplementary objects, references,
  and boxed text were excluded while normalizing paragraph text
- Hashing: article hashes cover the canonicalized JATS `article` subtree, not
  the changing OAI wrapper

## Derived outcomes

### `PMC10457403` — record emitted

- DOI: `10.1038/s41467-023-40669-0`
- Anchor: `article/body/sec[@id='Sec2']/sec[@id='Sec5']/p[@id='Par13']`
- Record schema: `0.2.0`
- Derived candidate: `Na3.4Hf0.6Sc0.4ZrSi2PO12`, `0.0012 S/cm`, `25 °C`,
  method token `EIS`
- Normalized paragraph span: `[1013, 1402)`
- Canonical article SHA-256:
  `337d2f12aca563a7be842f4bb3ed62305a530f3a716e0d622a40e1a23f4501e6`
- Normalized paragraph SHA-256:
  `2ce2bf1214bd132588cb3e45a04c0318ee42c296971c066164700a8f9fdb52b1`
- Evidence-span SHA-256:
  `cbbb7b689cbd1c26d91dc275a9b8d8ed245978c63c4b8f3d4fc84e7d58e52a75`

The rule checks the source's paired materials and values together with its
ordering word. It does not imply that the two measurements are otherwise
comparable or that omitted experimental context is unimportant.
An earlier occurrence of the target formula is outside the selected relation
and does not widen the evidence span.
The source's approximate-temperature marker and Na-metal electrode
configuration are observed inside the anchor but are not encoded as generic
uncertainty or `sample_condition`; the current schema has no typed fields for
those semantics.

### `PMC8292426` — record emitted

- DOI: `10.1038/s41467-021-24697-2`
- Record schema: `0.2.0`
- Anchor: `article/body/sec[@id='Sec2']/p[@id='Par7']`
- Derived candidate: `Li2ZrCl6` (`LZC`), `0.000808 S/cm`, `25 °C`,
  electrochemical impedance spectroscopy, condition `as-milled`
- Normalized paragraph span: `[0, 404)`
- Canonical article SHA-256:
  `8bed2089e9abd69ec18a31afc78291c1e50d7eefcf7afd1bb816dd93ac1dda76`
- Normalized paragraph SHA-256:
  `9333592a609b0fe37c3bcfa4751d0526367abacd60aed989c5b1142bfb4fda12`
- Evidence-span SHA-256:
  `78505e50ec21dc91e0b588d57afa056aadd9fec766edb9191ad1283d2e5023ea`

The bounded span stops before the later annealed-sample and electronic-
conductivity values in the same paragraph.

### `PMC11696013` — abstained

- DOI: `10.1038/s41467-024-55634-8`
- Inspected anchor:
  `article/body/sec[@id='Sec2']/sec[@id='Sec5']/p[@id='Par18']`
- Reason code: `cross_paragraph_qualifiers_not_supported`
- Canonical article SHA-256:
  `b04310feb565141e7ca56e6402d9395c567e025cb9529094b0f361d12db6f326`
- Normalized paragraph SHA-256:
  `9bf189f929be0c0407af5b7fac48235a64fa70e341ada4b0193505b2fe846f27`

The inspected paragraph contains an air-exposure value and duration, but the
measurement method and temperature are stated elsewhere. Neither current PMC
record schema represents a cross-paragraph evidence join without hiding a
coreference decision, so, when `--out` does not yet exist, the command returns
exit code `3` and creates no record. A pre-existing `--out` is rejected before
extraction with exit code `2` and remains byte-identical. A future multi-anchor
schema and human review are required.

### `PMC9218661` — record emitted

- DOI: `10.1002/advs.202200213`
- Record schema: `0.3.0` (source-locator extension only)
- Anchor: `article/body/sec[@id='advs3904-sec-0030']/p`
- Native stable ID: ancestor section `advs3904-sec-0030`; the section has one
  direct paragraph in the processed JATS version
- Derived candidate: `composite SSEs`, `0.000031 S/cm`, `30 °C`, joint analysis
  of CA, EIS, and DS spectra, condition `volume fraction of added TiO2 of 10%`
- Normalized paragraph span: `[95, 381)`
- Canonical article SHA-256:
  `b9f939648ccb9acd267645a6bcbcf0a24f33f1b559d0c76acb1807fe968a375f`
- Normalized paragraph SHA-256:
  `73bd7c568be77756026a5cae7eac310c120ad0acf97e3a635a7be2f332277919`
- Evidence-span SHA-256:
  `bdc8cc7697fd8985e68de8d1a0c70266c0bc6cc31632c7bff4263fb594b60962`

The paragraph does not carry its own JATS ID. Its `element_id` is therefore
null; `ancestor_element_id` records the native section ID and `locator_scope`
is `native_ancestor_plus_xpath`. Together with the exact article-relative
paragraph path, these fields identify what the paragraph hash and offsets refer
to without pretending the ancestor ID belongs to the paragraph. The generic
subject is preserved rather than silently resolving a more specific sample
label from another paragraph.

### `PMC10844219` — record emitted

- DOI: `10.1038/s41467-024-45258-3`
- Record schema: `0.2.0`
- Anchor: `article/body/sec[@id='Sec2']/sec[@id='Sec4']/p[@id='Par12']`
- Derived candidate: source alias `HE-SE`, `0.00213 S/cm`, approximately
  `25 °C`, electrochemical impedance spectroscopy, condition `as-prepared`
- Normalized paragraph span: `[27, 277)`
- Canonical article SHA-256:
  `e58c478a96bb1d64462b4e9182bc17b8cb54f85a38fb0184fc57b6aff0e8bc4f`
- Normalized paragraph SHA-256:
  `793ccd2990095f9d0000281fe9f9e9aaedd6e98cfdd7fadc67079da29b4cd2c1`
- Evidence-span SHA-256:
  `b39b8bfd619f531f89403cdf634370fc0ed60df3c14f78a9878d8418293e9738`

The record intentionally keeps `HE-SE` as the subject. Expanding it to the full
composition would require a cross-paragraph coreference link that the current
single-anchor record schemas do not represent.

## What the run establishes

All four emitted records passed their bundled Draft 2020-12 schema and
deterministic semantic checks. This establishes only that the local parser,
rights/identity gate, anchor selection, unit normalization, hashing, and
abstention boundary behaved as specified on these JATS versions. It does not
establish scientific truth, extraction accuracy, cross-paper comparability, or
legal clearance for figures, tables, supplements, or third-party material.
