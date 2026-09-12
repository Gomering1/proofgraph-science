# Real-paper local smoke test

Run date: 2026-09-11 PDT

This is a reproducibility note for one local software smoke test. It is not a
scientific benchmark, a human-reviewed record, or permission to redistribute
the source article.

## Input and controls

- Source: official PMC OAI-PMH `GetRecord` response for `PMC8292426`
- DOI: `10.1038/s41467-021-24697-2`
- Manifest entry: `humidity-tolerant-li2zrcl6-2021`
- Rights assertions observed at processing time: `pmc-open`, open access,
  no embargo, and `CC-BY-4.0`
- JATS target: `article/body/sec[@id='Sec2']/p[@id='Par7']`
- Source handling: the XML remained a temporary local input and is not included
  in this repository

## Derived result

The local command emitted a schema v0.2 record with:

- subject `Li2ZrCl6`, alias `LZC`;
- property `ionic_conductivity`;
- normalized value `0.000808 S/cm`;
- measurement temperature `25 °C`;
- method `electrochemical impedance spectroscopy`;
- sample condition `as-milled`; and
- review status `unreviewed`.

The evidence text itself is intentionally not reproduced here. The record used
the normalized paragraph span `[0, 404)` and emitted these reproducibility
hashes:

- canonical JATS article SHA-256:
  `8bed2089e9abd69ec18a31afc78291c1e50d7eefcf7afd1bb816dd93ac1dda76`
- normalized paragraph SHA-256:
  `9333592a609b0fe37c3bcfa4751d0526367abacd60aed989c5b1142bfb4fda12`
- evidence-span SHA-256:
  `78505e50ec21dc91e0b588d57afa056aadd9fec766edb9191ad1283d2e5023ea`

The generated record passed the bundled Draft 2020-12 schema and deterministic
semantic checks. Those checks establish internal consistency and source-span
support only. They do not establish that the reported measurement is true,
comparable to another experiment, or scientifically validated.
