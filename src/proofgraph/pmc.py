from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import re
from urllib.parse import urlencode
import xml.etree.ElementTree as ET


PMC_OAI_ENDPOINT = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
OAI_NAMESPACE = "http://www.openarchives.org/OAI/2.0/"
JATS_14_NAMESPACE = "https://jats.nlm.nih.gov/ns/archiving/1.4/"
CONTENT_HASH_METHOD = "sha256-xml-c14n2-article"
SUPPORTED_LICENSE_SPDX = "CC-BY-4.0"
MAX_LOCAL_XML_BYTES = 20_000_000
_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})$"
)


class PmcParseError(ValueError):
    """Raised when a local PMC OAI/JATS document is structurally invalid."""


class PmcIdentityError(ValueError):
    """Raised when asserted and embedded article identities disagree."""


class PmcRightsError(ValueError):
    """Raised when the narrow open-access rights gate is not satisfied."""


@dataclass(frozen=True)
class PmcJatsDocument:
    article: ET.Element
    content_sha256: str
    content_hash_method: str
    pmcid: str
    pmcid_version: str
    pmid: str | None
    doi: str
    title: str
    journal: str
    authors: tuple[str, ...]
    license_spdx: str
    license_url: str
    retrieval_url: str
    retrieved_at: str


def normalize_pmcid(value: str) -> str:
    match = re.fullmatch(r"PMC([0-9]+)", value.strip(), re.IGNORECASE)
    if not match:
        raise PmcIdentityError("PMCID must match PMC followed by decimal digits")
    return f"PMC{match.group(1)}"


def pmc_oai_url(pmcid: str) -> str:
    normalized = normalize_pmcid(pmcid)
    query = urlencode(
        {
            "verb": "GetRecord",
            "identifier": f"oai:pubmedcentral.nih.gov:{normalized[3:]}",
            "metadataPrefix": "pmc",
        }
    )
    return f"{PMC_OAI_ENDPOINT}?{query}"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str | None:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return None


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _descendants(element: ET.Element, local_name: str) -> list[ET.Element]:
    return [node for node in element.iter() if _local_name(node.tag) == local_name]


def _first_descendant(element: ET.Element, local_name: str) -> ET.Element | None:
    return next(
        (node for node in element.iter() if _local_name(node.tag) == local_name),
        None,
    )


def _single_text(
    values: list[str],
    *,
    field: str,
    error_type: type[ValueError] = PmcParseError,
) -> str:
    distinct = tuple(dict.fromkeys(value for value in values if value))
    if len(distinct) != 1:
        raise error_type(f"expected exactly one {field}; found {len(distinct)}")
    return distinct[0]


def _article_ids(article: ET.Element) -> dict[str, list[str]]:
    identifiers: dict[str, list[str]] = {}
    for node in _descendants(article, "article-id"):
        kind = (node.get("pub-id-type") or "").strip().lower()
        value = _text(node)
        if kind and value:
            identifiers.setdefault(kind, []).append(value)
    return identifiers


def _id_value(
    identifiers: dict[str, list[str]],
    kinds: tuple[str, ...],
    *,
    field: str,
) -> str:
    values = [value for kind in kinds for value in identifiers.get(kind, [])]
    return _single_text(values, field=field, error_type=PmcIdentityError)


def _custom_metadata(article: ET.Element) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for custom_meta in _descendants(article, "custom-meta"):
        name_node = next(
            (child for child in custom_meta if _local_name(child.tag) == "meta-name"),
            None,
        )
        value_node = next(
            (child for child in custom_meta if _local_name(child.tag) == "meta-value"),
            None,
        )
        name = _text(name_node).lower()
        value = _text(value_node)
        if name and value:
            result.setdefault(name, []).append(value)
    return result


def _metadata_value(metadata: dict[str, list[str]], name: str) -> str:
    return _single_text(
        metadata.get(name, []),
        field=f"JATS custom metadata {name}",
        error_type=PmcRightsError,
    )


def _author_names(article: ET.Element) -> tuple[str, ...]:
    authors: list[str] = []
    for contrib in _descendants(article, "contrib"):
        if (contrib.get("contrib-type") or "author").lower() != "author":
            continue
        name = next(
            (child for child in contrib if _local_name(child.tag) == "name"),
            None,
        )
        collab = next(
            (child for child in contrib if _local_name(child.tag) == "collab"),
            None,
        )
        if name is not None:
            given = _text(_first_descendant(name, "given-names"))
            surname = _text(_first_descendant(name, "surname"))
            rendered = " ".join(part for part in (given, surname) if part)
        else:
            rendered = _text(collab)
        if rendered:
            authors.append(rendered)
    if not authors:
        raise PmcParseError("JATS article has no author attribution")
    return tuple(authors)


def _validate_rfc3339(value: str, *, field: str) -> str:
    candidate = value.strip()
    if not _RFC3339_RE.fullmatch(candidate):
        raise PmcParseError(f"{field} is not an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PmcParseError(f"{field} is not an RFC 3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise PmcParseError(f"{field} is not an RFC 3339 timestamp")
    return candidate


def parse_pmc_oai_jats(
    raw_xml: bytes,
    *,
    expected_pmcid: str,
    expected_doi: str,
    expected_license_spdx: str,
    expected_license_url: str,
    retrieval_url: str | None = None,
    max_xml_bytes: int = MAX_LOCAL_XML_BYTES,
) -> PmcJatsDocument:
    """Parse one user-supplied PMC OAI/JATS response and fail closed.

    This function never performs network I/O or persists the supplied XML.
    The expected values are assertions supplied by a caller or a read-only
    manifest; they are checked against metadata embedded in the XML.
    """

    normalized_pmcid = normalize_pmcid(expected_pmcid)
    expected_url = pmc_oai_url(normalized_pmcid)
    if retrieval_url is not None and retrieval_url != expected_url:
        raise PmcIdentityError("retrieval URL is not the fixed PMC OAI-PMH GetRecord URL")
    if not raw_xml:
        raise PmcParseError("PMC OAI/JATS XML is empty")
    if len(raw_xml) > max_xml_bytes:
        raise PmcParseError(
            f"PMC OAI/JATS XML exceeds the {max_xml_bytes}-byte local input limit"
        )
    upper_xml = raw_xml.upper()
    if b"<!DOCTYPE" in upper_xml or b"<!ENTITY" in upper_xml:
        raise PmcParseError("DTD and entity declarations are not supported")
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        raise PmcParseError(f"malformed PMC OAI/JATS XML: {exc}") from exc

    if root.tag != f"{{{OAI_NAMESPACE}}}OAI-PMH":
        raise PmcParseError("document root is not an OAI-PMH 2.0 response")

    oai_errors = root.findall(f".//{{{OAI_NAMESPACE}}}error")
    if oai_errors:
        code = (oai_errors[0].get("code") or "unknown").strip()
        message = _text(oai_errors[0]) or "unspecified error"
        raise PmcParseError(f"PMC OAI-PMH error {code}: {message}")

    metadata_nodes = root.findall(f".//{{{OAI_NAMESPACE}}}metadata")
    articles = [
        child
        for metadata in metadata_nodes
        for child in metadata
        if child.tag == f"{{{JATS_14_NAMESPACE}}}article"
    ]
    if len(articles) != 1:
        raise PmcParseError(f"expected exactly one JATS article; found {len(articles)}")
    article = articles[0]
    if _namespace(article.tag) != JATS_14_NAMESPACE or article.get("dtd-version") != "1.4":
        raise PmcParseError("only namespaced JATS Archiving 1.4 articles are supported")

    headers = root.findall(f".//{{{OAI_NAMESPACE}}}header")
    if len(headers) != 1:
        raise PmcParseError(f"expected exactly one OAI header; found {len(headers)}")
    header = headers[0]
    set_specs = [
        _text(node) for node in header.findall(f"{{{OAI_NAMESPACE}}}setSpec")
    ]
    if "pmc-open" not in set_specs:
        raise PmcRightsError("OAI header is missing the pmc-open set")
    oai_identifier = _single_text(
        [
            _text(node)
            for node in header.findall(f"{{{OAI_NAMESPACE}}}identifier")
        ],
        field="OAI identifier",
        error_type=PmcIdentityError,
    )
    expected_oai_identifier = f"oai:pubmedcentral.nih.gov:{normalized_pmcid[3:]}"
    if oai_identifier != expected_oai_identifier:
        raise PmcIdentityError(
            f"OAI identifier {oai_identifier!r} does not match {normalized_pmcid}"
        )

    article_meta = _first_descendant(article, "article-meta")
    if article_meta is None:
        raise PmcParseError("JATS article is missing article-meta")
    identifiers = _article_ids(article_meta)
    article_pmcid = normalize_pmcid(
        _id_value(identifiers, ("pmcid", "pmc"), field="JATS PMCID")
    )
    if article_pmcid != normalized_pmcid:
        raise PmcIdentityError(
            f"JATS PMCID {article_pmcid} does not match {normalized_pmcid}"
        )
    pmcid_version = _id_value(
        identifiers,
        ("pmcid-ver", "pmc-version"),
        field="JATS PMCID version",
    )
    if not re.fullmatch(re.escape(normalized_pmcid) + r"\.[0-9]+", pmcid_version):
        raise PmcIdentityError(
            f"JATS PMCID version {pmcid_version!r} does not belong to {normalized_pmcid}"
        )

    article_doi = _id_value(identifiers, ("doi",), field="JATS DOI").lower()
    asserted_doi = expected_doi.strip().lower()
    if article_doi != asserted_doi:
        raise PmcIdentityError(
            f"JATS DOI {article_doi!r} does not match expected DOI {asserted_doi!r}"
        )
    pmid_values = identifiers.get("pmid", [])
    pmid = _single_text(pmid_values, field="JATS PMID") if pmid_values else None

    if expected_license_spdx != SUPPORTED_LICENSE_SPDX:
        raise PmcRightsError(
            f"only {SUPPORTED_LICENSE_SPDX} is supported by this extraction slice"
        )
    custom_metadata = _custom_metadata(article_meta)
    if _metadata_value(custom_metadata, "pmc-prop-open-access").lower() != "yes":
        raise PmcRightsError("JATS does not assert pmc-prop-open-access=yes")
    if _metadata_value(custom_metadata, "pmc-status-embargo").lower() != "no":
        raise PmcRightsError("JATS does not assert pmc-status-embargo=no")
    license_urls = [
        _text(node) for node in _descendants(article_meta, "license_ref")
    ]
    article_license_url = _single_text(
        license_urls,
        field="JATS license_ref",
        error_type=PmcRightsError,
    )
    if article_license_url != expected_license_url:
        raise PmcRightsError("JATS license_ref does not match the expected license URL")

    response_dates = [
        _text(node)
        for node in root.findall(f"{{{OAI_NAMESPACE}}}responseDate")
    ]
    retrieved_at = _validate_rfc3339(
        _single_text(response_dates, field="OAI responseDate"),
        field="OAI responseDate",
    )
    title = _text(_first_descendant(article_meta, "article-title"))
    journal = _text(_first_descendant(article, "journal-title"))
    if not title or not journal:
        raise PmcParseError("JATS article is missing its title or journal attribution")

    serialized_article = ET.tostring(article, encoding="unicode")
    try:
        canonical_article = ET.canonicalize(xml_data=serialized_article)
    except (ET.ParseError, ValueError) as exc:
        raise PmcParseError(f"could not canonicalize JATS article: {exc}") from exc

    return PmcJatsDocument(
        article=article,
        content_sha256=sha256(canonical_article.encode("utf-8")).hexdigest(),
        content_hash_method=CONTENT_HASH_METHOD,
        pmcid=normalized_pmcid,
        pmcid_version=pmcid_version,
        pmid=pmid,
        doi=article_doi,
        title=title,
        journal=journal,
        authors=_author_names(article_meta),
        license_spdx=expected_license_spdx,
        license_url=article_license_url,
        retrieval_url=expected_url,
        retrieved_at=retrieved_at,
    )
