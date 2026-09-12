# Architecture

The vertical slice has four boundaries:

1. `ingest` reads authored HTML and preserves text under stable element identifiers;
   `pmc` parses one local PMC OAI response and checks identity and rights metadata;
   and `jats` emits normalized native-ID body paragraphs without floating content.
2. `extract` recognizes one narrow HTML rule or the PMC8292426-style Par7 rule
   and writes source, claim, qualifier, run, and explicitly unreviewed fields.
3. `validate` selects the byte-identical published/bundled v0.1 or v0.2 Draft
   2020-12 schema, then runs version-specific deterministic evidence checks.
   Offline v0.2 validation can verify the evidence hash and internal span length,
   but cannot re-prove source offsets without the original local XML.
4. `cli` exposes `extract`, local-only `extract-pmc`, and `validate` commands and
   returns nonzero exit codes on failure. `extract-pmc` reads the manifest without
   changing it and neither downloads nor persists source XML.

The rule-based extractor is replaceable. Future model adapters should produce the same evidence record and must not bypass deterministic validation or source anchoring. Storage can remain ordinary JSON or SQLite during v0.1; a dedicated graph database is unnecessary until a real query workload justifies it.
