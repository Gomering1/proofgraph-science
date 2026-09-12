from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from datetime import datetime
from functools import lru_cache
from hashlib import sha256
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


DEFAULT_SCHEMA_VERSION = "0.1.0"
SCHEMA_FILENAME = "claim-evidence.v0.1.schema.json"
SCHEMA_FILENAMES = {
    "0.1.0": SCHEMA_FILENAME,
    "0.2.0": "claim-evidence.v0.2.schema.json",
}


class SchemaRuntimeError(RuntimeError):
    """Raised when the bundled schema cannot be loaded or is itself invalid."""


@lru_cache(maxsize=2)
def _schema_document(schema_version: str = DEFAULT_SCHEMA_VERSION) -> dict[str, Any]:
    try:
        filename = SCHEMA_FILENAMES[schema_version]
    except KeyError as exc:
        raise SchemaRuntimeError(f"unsupported schema version {schema_version!r}") from exc
    try:
        text = (
            resources.files("proofgraph.schemas")
            .joinpath(filename)
            .read_text(encoding="utf-8")
        )
        schema = json.loads(text)
        Draft202012Validator.check_schema(schema)
    except (
        FileNotFoundError,
        ModuleNotFoundError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        SchemaError,
    ) as exc:
        raise SchemaRuntimeError(f"could not load bundled {filename}: {exc}") from exc
    return schema


def load_claim_evidence_schema(
    schema_version: str = DEFAULT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return an isolated copy of the exact schema used by runtime validation."""

    return copy.deepcopy(_schema_document(schema_version))


@lru_cache(maxsize=2)
def _schema_validator(schema_version: str) -> Draft202012Validator:
    return Draft202012Validator(_schema_document(schema_version))


def _json_path(path: list[Any]) -> str:
    rendered = "$"
    for part in path:
        if isinstance(part, int):
            rendered += f"[{part}]"
        elif isinstance(part, str) and part.isidentifier():
            rendered += f".{part}"
        else:
            rendered += f"[{json.dumps(part, ensure_ascii=False)}]"
    return rendered


def _schema_errors(record: Any, schema_version: str) -> list[str]:
    failures = sorted(
        _schema_validator(schema_version).iter_errors(record),
        key=lambda failure: (
            tuple(f"{type(part).__name__}:{part}" for part in failure.absolute_path),
            tuple(f"{type(part).__name__}:{part}" for part in failure.absolute_schema_path),
            failure.message,
        ),
    )
    return [
        f"schema {_json_path(list(failure.absolute_path))}: {failure.message}"
        for failure in failures
    ]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _semantic_errors_v01(record: Any) -> list[str]:
    errors: list[str] = []
    record_fields = _mapping(record)

    if record_fields.get("schema_version") != "0.1.0":
        errors.append("schema_version must be 0.1.0")

    source = _mapping(record_fields.get("source_artifact"))
    for field in ("identifier", "content_sha256", "access_basis"):
        if not source.get(field):
            errors.append(f"source_artifact.{field} is required")

    anchor = _mapping(record_fields.get("source_anchor"))
    evidence = anchor.get("evidence_text") or ""
    if anchor.get("type") != "html_element":
        errors.append("source_anchor.type must be html_element in this prototype")
    if not anchor.get("element_id"):
        errors.append("source_anchor.element_id is required")
    if not evidence:
        errors.append("source_anchor.evidence_text is required")

    claim = _mapping(record_fields.get("claim"))
    for field in (
        "subject",
        "property",
        "reported_value",
        "reported_unit",
        "normalized_value",
        "normalized_unit",
    ):
        if claim.get(field) in (None, ""):
            errors.append(f"claim.{field} is required")
    if claim.get("property") != "ionic_conductivity":
        errors.append("claim.property must be ionic_conductivity in this prototype")
    if claim.get("normalized_unit") != "S/cm":
        errors.append("claim.normalized_unit must be S/cm")
    if (
        isinstance(claim.get("subject"), str)
        and isinstance(evidence, str)
        and claim["subject"] not in evidence
    ):
        errors.append("claim.subject is not supported by evidence_text")
    if (
        isinstance(claim.get("reported_value"), str)
        and isinstance(evidence, str)
        and claim["reported_value"] not in evidence
    ):
        errors.append("claim.reported_value is not supported by evidence_text")

    qualifiers = _mapping(record_fields.get("qualifiers"))
    if not qualifiers.get("temperature_value"):
        errors.append("qualifiers.temperature_value is required")
    if qualifiers.get("temperature_unit") != "°C":
        errors.append("qualifiers.temperature_unit must be °C")

    run = _mapping(record_fields.get("extraction_run"))
    for field in ("extractor", "proofgraph_version", "python_version", "generated_at"):
        if not run.get(field):
            errors.append(f"extraction_run.{field} is required")

    review = _mapping(record_fields.get("review"))
    if review.get("status") not in {"unreviewed", "human_reviewed", "rejected"}:
        errors.append("review.status is invalid")

    return errors


def _is_rfc3339(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _evidence_contains(evidence: str, value: Any, *, casefold: bool = False) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if casefold:
        return value.casefold() in evidence.casefold()
    return value in evidence


def _semantic_errors_v02(record: Any) -> list[str]:
    errors: list[str] = []
    record_fields = _mapping(record)
    if record_fields.get("schema_version") != "0.2.0":
        errors.append("schema_version must be 0.2.0")

    source = _mapping(record_fields.get("source_artifact"))
    doi = source.get("doi")
    canonical_doi_url = f"https://doi.org/{doi}" if isinstance(doi, str) else None
    if canonical_doi_url and source.get("identifier") != canonical_doi_url:
        errors.append("source_artifact.identifier must be the canonical DOI URL")
    if source.get("content_hash_method") != "sha256-xml-c14n2-article":
        errors.append(
            "source_artifact.content_hash_method must be sha256-xml-c14n2-article"
        )
    if source.get("access_basis") != "open_access":
        errors.append("source_artifact.access_basis must be open_access")
    pmcid = source.get("pmcid")
    pmcid_version = source.get("pmcid_version")
    if (
        isinstance(pmcid, str)
        and isinstance(pmcid_version, str)
        and not pmcid_version.startswith(f"{pmcid}.")
    ):
        errors.append("source_artifact.pmcid_version does not match pmcid")

    retrieval = _mapping(source.get("retrieval"))
    if retrieval.get("provider") != "NCBI PMC OAI-PMH":
        errors.append("source_artifact.retrieval.provider must be NCBI PMC OAI-PMH")
    retrieval_url = retrieval.get("url")
    if not isinstance(retrieval_url, str) or not retrieval_url.startswith("https://"):
        errors.append("source_artifact.retrieval.url must be HTTPS")
    if not _is_rfc3339(retrieval.get("retrieved_at")):
        errors.append("source_artifact.retrieval.retrieved_at must be RFC 3339")

    attribution = _mapping(source.get("attribution"))
    if canonical_doi_url and attribution.get("doi_url") != canonical_doi_url:
        errors.append("source_artifact.attribution.doi_url does not match doi")
    if attribution.get("license_url") != source.get("license_url"):
        errors.append("source_artifact.attribution.license_url does not match license_url")

    anchor = _mapping(record_fields.get("source_anchor"))
    evidence = anchor.get("evidence_text")
    evidence_text = evidence if isinstance(evidence, str) else ""
    if anchor.get("type") != "jats_element_text_span":
        errors.append("source_anchor.type must be jats_element_text_span in schema v0.2")
    expected_evidence_hash = (
        sha256(evidence_text.encode("utf-8")).hexdigest() if evidence_text else None
    )
    if expected_evidence_hash and anchor.get("evidence_text_sha256") != expected_evidence_hash:
        errors.append("source_anchor.evidence_text_sha256 does not match evidence_text")
    start = anchor.get("character_start")
    end = anchor.get("character_end")
    if type(start) is int and type(end) is int:
        if start >= end:
            errors.append("source_anchor character span must be nonempty and half-open")
        elif end - start != len(evidence_text):
            errors.append(
                "source_anchor character span length does not match evidence_text"
            )

    claim = _mapping(record_fields.get("claim"))
    for field in (
        "subject",
        "reported_value",
        "reported_unit",
        "normalized_value",
        "normalized_unit",
    ):
        if claim.get(field) in (None, ""):
            errors.append(f"claim.{field} is required")
    if claim.get("property") != "ionic_conductivity":
        errors.append("claim.property must be ionic_conductivity in this prototype")
    if claim.get("normalized_unit") != "S/cm":
        errors.append("claim.normalized_unit must be S/cm")
    for field in ("subject", "subject_alias", "reported_value", "reported_unit"):
        value = claim.get(field)
        if value not in (None, "") and not _evidence_contains(evidence_text, value):
            errors.append(f"claim.{field} is not supported by evidence_text")

    qualifiers = _mapping(record_fields.get("qualifiers"))
    temperature_value = qualifiers.get("temperature_value")
    if not temperature_value:
        errors.append("qualifiers.temperature_value is required")
    elif not _evidence_contains(evidence_text, temperature_value):
        errors.append("qualifiers.temperature_value is not supported by evidence_text")
    if qualifiers.get("temperature_unit") != "°C":
        errors.append("qualifiers.temperature_unit must be °C")
    elif not _evidence_contains(evidence_text, "°C"):
        errors.append("qualifiers.temperature_unit is not supported by evidence_text")
    method = qualifiers.get("measurement_method")
    if not method:
        errors.append("qualifiers.measurement_method is required for schema v0.2")
    elif not _evidence_contains(evidence_text, method, casefold=True):
        errors.append("qualifiers.measurement_method is not supported by evidence_text")
    sample_condition = qualifiers.get("sample_condition")
    if sample_condition not in (None, "") and not _evidence_contains(
        evidence_text, sample_condition, casefold=True
    ):
        errors.append("qualifiers.sample_condition is not supported by evidence_text")

    run = _mapping(record_fields.get("extraction_run"))
    for field in ("extractor", "proofgraph_version", "python_version", "generated_at"):
        if not run.get(field):
            errors.append(f"extraction_run.{field} is required")
    review = _mapping(record_fields.get("review"))
    if review.get("status") not in {"unreviewed", "human_reviewed", "rejected"}:
        errors.append("review.status is invalid")
    return errors


def validate_record(
    record: Any,
    *,
    schema_version: str | None = None,
) -> list[str]:
    """Run the matching published schema, then version-specific evidence checks."""

    record_fields = _mapping(record)
    detected = record_fields.get("schema_version")
    selected = schema_version or (
        detected if isinstance(detected, str) else DEFAULT_SCHEMA_VERSION
    )
    if selected not in SCHEMA_FILENAMES:
        return [f"schema_version {selected!r} is unsupported"]
    errors = _schema_errors(record, selected)
    if selected == "0.1.0":
        errors.extend(_semantic_errors_v01(record))
    else:
        errors.extend(_semantic_errors_v02(record))
    return errors


def set_validation_result(
    record: dict[str, Any],
    *,
    schema_version: str | None = None,
) -> list[str]:
    errors = validate_record(record, schema_version=schema_version)
    record["validation"] = {
        "status": "valid" if not errors else "invalid",
        "errors": errors,
    }
    return errors
