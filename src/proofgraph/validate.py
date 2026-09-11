from __future__ import annotations

from typing import Any


def validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if record.get("schema_version") != "0.1.0":
        errors.append("schema_version must be 0.1.0")

    source = record.get("source_artifact") or {}
    for field in ("identifier", "content_sha256", "access_basis"):
        if not source.get(field):
            errors.append(f"source_artifact.{field} is required")

    anchor = record.get("source_anchor") or {}
    evidence = anchor.get("evidence_text") or ""
    if anchor.get("type") != "html_element":
        errors.append("source_anchor.type must be html_element in this prototype")
    if not anchor.get("element_id"):
        errors.append("source_anchor.element_id is required")
    if not evidence:
        errors.append("source_anchor.evidence_text is required")

    claim = record.get("claim") or {}
    for field in ("subject", "property", "reported_value", "reported_unit", "normalized_value", "normalized_unit"):
        if claim.get(field) in (None, ""):
            errors.append(f"claim.{field} is required")
    if claim.get("property") != "ionic_conductivity":
        errors.append("claim.property must be ionic_conductivity in this prototype")
    if claim.get("normalized_unit") != "S/cm":
        errors.append("claim.normalized_unit must be S/cm")
    if claim.get("subject") and claim["subject"] not in evidence:
        errors.append("claim.subject is not supported by evidence_text")
    if claim.get("reported_value") and claim["reported_value"] not in evidence:
        errors.append("claim.reported_value is not supported by evidence_text")

    qualifiers = record.get("qualifiers") or {}
    if not qualifiers.get("temperature_value"):
        errors.append("qualifiers.temperature_value is required")
    if qualifiers.get("temperature_unit") != "°C":
        errors.append("qualifiers.temperature_unit must be °C")

    run = record.get("extraction_run") or {}
    for field in ("extractor", "proofgraph_version", "python_version", "generated_at"):
        if not run.get(field):
            errors.append(f"extraction_run.{field} is required")

    review = record.get("review") or {}
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
