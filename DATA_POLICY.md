# Data policy

The public ProofGraph Science repository may contain only:

- documents published under terms that allow redistribution;
- material for which the project has explicit permission;
- fixtures written specifically for software testing;
- metadata or derived records whose release is compatible with the source terms.

The repository must not contain full copies of paywalled papers, confidential laboratory documents, personal data that is not needed for the benchmark, or source text whose redistribution rights are unknown.

User-provided documents stay local by default. Remote model adapters must require explicit configuration and must explain what data leaves the machine. A source hash and coordinates may be exported without exporting restricted source text.

The current HTML and OAI/JATS fixtures are project-authored, synthetic, and
released under CC0-1.0. Their numerical statements exist only to test software
behavior and must not be cited as scientific results. The local `extract-pmc`
command reads one user-supplied OAI/JATS file in memory, writes only its derived
record, and performs no download or source caching. Successful parsing and
schema validation do not constitute legal or scientific review.

The five-paper pilot manifest stores bibliographic metadata, remote
links, rights evidence, conservative reuse rules, and bounded local-smoke-test
locators only. The public smoke-test report contains derived fields, hashes,
anchors, and an abstention reason, but no evidence passages. The manifest does
not bundle or authorize automatic downloading of article text or supplementary
assets; see [`docs/corpus-legal-gate.md`](docs/corpus-legal-gate.md).
