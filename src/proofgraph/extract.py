from __future__ import annotations

import os
import platform
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import __version__
from .ingest import IngestedDocument, SourceElement, ingest_html


CONDUCTIVITY_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<prefix>[mµu]?)S\s*cm(?:\^?[-−]1|⁻¹)",
    re.IGNORECASE,
)
TEMPERATURE_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*°\s*C", re.IGNORECASE)
MATERIAL_RE = re.compile(r"\b(?P<material>(?:Li|Na)[A-Za-z0-9().+\-]{2,})\b")


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def _normalize_conductivity(value: str, prefix: str) -> tuple[str, str]:
    multiplier = {
        "": Decimal("1"),
        "m": Decimal("0.001"),
        "µ": Decimal("0.000001"),
        "u": Decimal("0.000001"),
    }[prefix.lower()]
    return _decimal_text(Decimal(value) * multiplier), "S/cm"


def _find_candidate(document: IngestedDocument) -> tuple[SourceElement, re.Match[str]]:
    for element in document.elements:
        match = CONDUCTIVITY_RE.search(element.text)
        if match:
            return element, match
    raise ValueError("No supported ionic-conductivity statement was found")


def _generated_at() -> str:
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch is not None:
        return datetime.fromtimestamp(int(source_date_epoch), timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def extract_record(path: str | Path) -> dict[str, Any]:
    document = ingest_html(path)
    element, conductivity = _find_candidate(document)
    material = MATERIAL_RE.search(element.text)
    temperature = TEMPERATURE_RE.search(element.text)
    if not material or not temperature:
        raise ValueError("The statement is missing a supported material or temperature")

    normalized_value, normalized_unit = _normalize_conductivity(
        conductivity.group("value"), conductivity.group("prefix")
    )
    method = None
    if "electrochemical impedance spectroscopy" in element.text.lower():
        method = "electrochemical impedance spectroscopy"

    return {
        "schema_version": "0.1.0",
        "source_artifact": {
            "identifier": f"urn:sha256:{document.sha256}",
            "title": document.title,
            "content_sha256": document.sha256,
            "access_basis": "authored_fixture" if document.license == "CC0-1.0" else "user_supplied",
            "license": document.license,
        },
        "source_anchor": {
            "type": "html_element",
            "element_id": element.element_id,
            "evidence_text": element.text,
            "character_start": conductivity.start(),
            "character_end": conductivity.end(),
        },
        "claim": {
            "subject": material.group("material"),
            "property": "ionic_conductivity",
            "reported_value": conductivity.group("value"),
            "reported_unit": f"{conductivity.group('prefix')}S cm−1",
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "claim_type": "measured",
        },
        "qualifiers": {
            "temperature_value": temperature.group("value"),
            "temperature_unit": "°C",
            "measurement_method": method,
        },
        "uncertainty": {
            "reported": None,
            "extraction_confidence": None,
        },
        "extraction_run": {
            "extractor": "proofgraph.rules.ionic_conductivity.v1",
            "proofgraph_version": __version__,
            "python_version": platform.python_version(),
            "generated_at": _generated_at(),
            "model": None,
            "prompt_hash": None,
        },
        "validation": {
            "status": "not_run",
            "errors": [],
        },
        "review": {
            "status": "unreviewed",
            "reviewer": None,
            "reviewed_at": None,
        },
        "relations": [],
    }
