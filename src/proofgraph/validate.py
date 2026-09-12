from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


SCHEMA_FILENAME = "claim-evidence.v0.1.schema.json"


class SchemaRuntimeError(RuntimeError):
    """Raised when the bundled schema cannot be loaded or is itself invalid."""


@lru_cache(maxsize=1)
def _schema_document() -> dict[str, Any]:
    try:
        text = (
            resources.files("proofgraph.schemas")
            .joinpath(SCHEMA_FILENAME)
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
        raise SchemaRuntimeError(f"could not load bundled {SCHEMA_FILENAME}: {exc}") from exc
    return schema


def load_claim_evidence_schema() -> dict[str, Any]:
    """Return an isolated copy of the exact schema used by runtime validation."""

    return copy.deepcopy(_schema_document())


@lru_cache(maxsize=1)
def _schema_validator() -> Draft202012Validator:
    return Draft202012Validator(_schema_document())


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


def _schema_errors(record: Any) -> list[str]:
    failures = sorted(
        _schema_validator().iter_errors(record),
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


def validate_record(record: Any) -> list[str]:
    """Run the published JSON Schema, then the prototype's evidence checks."""

    errors = _schema_errors(record)
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


def set_validation_result(record: dict[str, Any]) -> list[str]:
    errors = validate_record(record)
    record["validation"] = {
        "status": "valid" if not errors else "invalid",
        "errors": errors,
    }
    return errors
