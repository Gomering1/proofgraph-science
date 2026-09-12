# Architecture

The vertical slice has four boundaries:

1. `ingest` reads authored HTML and preserves text under stable element identifiers;
   `pmc` parses one local PMC OAI response and checks identity and rights metadata;
   and `jats` emits normalized body paragraphs without floating content. JATS
   anchors use either a native paragraph ID or an exact paragraph path under a
   native-ID section when the publisher omitted paragraph IDs.
2. `extract` recognizes one narrow HTML rule or one of four manifest-selected
   PMC smoke-test profiles and writes source, claim, qualifier, run, and
   explicitly unreviewed fields. A fifth profile deliberately abstains because
   the current single-anchor schemas cannot represent its cross-paragraph
   qualifiers without hiding a coreference decision.
3. `validate` selects the byte-identical published/bundled v0.1, v0.2, or v0.3
   Draft 2020-12 schema, then runs version-specific deterministic evidence
   checks. v0.3 is a locator-only extension for an ID-less paragraph: it keeps
   `element_id` null and records `ancestor_element_id`, `locator_scope`, and the
   exact XPath. Published v0.1 and v0.2 remain unchanged. Offline PMC-record
   validation can verify the evidence hash and internal span length, but cannot
   re-prove source offsets without the original local XML.
4. `cli` exposes `extract`, local-only `extract-pmc`, and `validate` commands.
   It distinguishes successful extraction, validation failure, operational or
   gate failure, and documented abstention. `extract-pmc` reads the manifest
   without changing it and neither downloads nor persists source XML. Both
   extract commands reject an existing `--out` before parsing or extraction;
   they never overwrite or remove a stale result.

The rule-based extractor is replaceable. Future model adapters should produce the same evidence record and must not bypass deterministic validation or source anchoring. Storage can remain ordinary JSON or SQLite during v0.1; a dedicated graph database is unnecessary until a real query workload justifies it.
