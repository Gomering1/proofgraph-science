# Architecture

The vertical slice has four boundaries:

1. `ingest` reads authored HTML and preserves text under stable element identifiers.
2. `extract` recognizes one narrow claim pattern and writes source, claim, qualifier, run, and review fields.
3. `validate` checks required fields and confirms that the reported subject and value occur in the anchored evidence.
4. `cli` exposes extract and validate commands and returns nonzero exit codes on failure.

The rule-based extractor is replaceable. Future model adapters should produce the same evidence record and must not bypass deterministic validation or source anchoring. Storage can remain ordinary JSON or SQLite during v0.1; a dedicated graph database is unnecessary until a real query workload justifies it.
