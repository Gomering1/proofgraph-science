from __future__ import annotations

import os
import platform
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

from . import __version__
from .ingest import IngestedDocument, SourceElement, ingest_html
from .jats import JatsTextElement, iter_body_paragraphs
from .pmc import PmcIdentityError, PmcJatsDocument


CONDUCTIVITY_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<prefix>[mµu]?)S\s*cm(?:\^?[-−]1|⁻¹)",
    re.IGNORECASE,
)
TEMPERATURE_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*°\s*C", re.IGNORECASE)
MATERIAL_RE = re.compile(r"\b(?P<material>(?:Li|Na)[A-Za-z0-9().+\-]{2,})\b")

PMC_MATERIAL_ALIAS_RE = re.compile(
    r"(?P<formula>Li\s*2\s*Zr\s*Cl\s*6)\s*\(\s*(?P<alias>LZC)\s*\)",
    re.IGNORECASE,
)
PMC_METHOD_RE = re.compile(r"electrochemical impedance spectroscopy", re.IGNORECASE)
PMC_SAMPLE_CONDITION_RE = re.compile(r"\bas[\s\-‐‑‒–—]*milled\b", re.IGNORECASE)
PMC_IONIC_PHRASE_RE = re.compile(r"\bionic conductivity\b", re.IGNORECASE)
PMC_ELECTRONIC_PHRASE_RE = re.compile(r"\belectronic conductivity\b", re.IGNORECASE)
PMC_TEMPERATURE_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*°\s*C", re.IGNORECASE)
_EXPONENT = r"(?:[+\-−–—]?\d+|[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)"
PMC_CONDUCTIVITY_RE = re.compile(
    rf"(?P<reported>(?P<coefficient>\d+(?:\.\d+)?)"
    rf"(?:\s*(?:×|[xX])\s*10\s*(?:\^\s*)?(?P<exponent>{_EXPONENT}))?)"
    r"\s*(?P<unit>(?P<prefix>[mµμu]?)S\s*"
    r"(?:cm\s*(?:[\-−–—]\s*1|\^\s*[\-−–—]\s*1|⁻¹)|/\s*cm))",
    re.IGNORECASE,
)

PMC_ATTRIBUTION_CHANGE_NOTICE = (
    "JATS inline markup flattened and whitespace normalized; "
    "claim record derived by ProofGraph"
)


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


def _normalize_exponent(value: str | None) -> int:
    if value is None:
        return 0
    translated = value.translate(
        str.maketrans(
            {
                "⁰": "0",
                "¹": "1",
                "²": "2",
                "³": "3",
                "⁴": "4",
                "⁵": "5",
                "⁶": "6",
                "⁷": "7",
                "⁸": "8",
                "⁹": "9",
                "⁺": "+",
                "⁻": "-",
                "−": "-",
                "–": "-",
                "—": "-",
            }
        )
    )
    return int(translated)


def _normalize_pmc_conductivity(match: re.Match[str]) -> tuple[str, str]:
    prefix = match.group("prefix").lower()
    multiplier = {
        "": Decimal("1"),
        "m": Decimal("0.001"),
        "µ": Decimal("0.000001"),
        "μ": Decimal("0.000001"),
        "u": Decimal("0.000001"),
    }[prefix]
    exponent = _normalize_exponent(match.group("exponent"))
    normalized = Decimal(match.group("coefficient")) * (Decimal(10) ** exponent)
    return _decimal_text(normalized * multiplier), "S/cm"


def _nearest_match(
    matches: list[re.Match[str]],
    target_start: int,
    target_end: int,
) -> re.Match[str]:
    if not matches:
        raise ValueError("required PMC evidence field is absent")

    def distance(match: re.Match[str]) -> tuple[int, int]:
        if match.end() <= target_start:
            gap = target_start - match.end()
        elif match.start() >= target_end:
            gap = match.start() - target_end
        else:
            gap = 0
        return gap, match.start()

    return min(matches, key=distance)


def _find_pmc_candidate(
    text: str,
    conditions: list[re.Match[str]],
) -> tuple[re.Match[str], re.Match[str], re.Match[str]]:
    candidates: list[tuple[int, int, re.Match[str], re.Match[str], re.Match[str]]] = []
    for conductivity in PMC_CONDUCTIVITY_RE.finditer(text):
        preceding = text[max(0, conductivity.start() - 320) : conductivity.start()]
        window_start = max(0, conductivity.start() - 320)
        ionic_phrases = list(PMC_IONIC_PHRASE_RE.finditer(preceding))
        if not ionic_phrases:
            continue
        ionic_phrase = ionic_phrases[-1]
        electronic_phrases = list(PMC_ELECTRONIC_PHRASE_RE.finditer(preceding))
        if electronic_phrases and electronic_phrases[-1].start() > ionic_phrase.start():
            continue
        absolute_ionic = PMC_IONIC_PHRASE_RE.search(
            text,
            window_start + ionic_phrase.start(),
            window_start + ionic_phrase.end(),
        )
        assert absolute_ionic is not None
        preceding_conditions = [
            condition
            for condition in conditions
            if condition.end() <= conductivity.start()
            and conductivity.start() - condition.end() <= 320
        ]
        if not preceding_conditions:
            continue
        condition = preceding_conditions[-1]
        condition_gap = conductivity.start() - condition.end()
        phrase_gap = conductivity.start() - absolute_ionic.end()
        candidates.append(
            (condition_gap, phrase_gap, conductivity, absolute_ionic, condition)
        )
    if not candidates:
        raise ValueError(
            "No ionic-conductivity value tied to an as-milled condition was found"
        )
    _, _, conductivity, ionic_phrase, condition = min(
        candidates, key=lambda candidate: candidate[2].start()
    )
    return conductivity, ionic_phrase, condition


def _manifest_value(manifest_entry: Mapping[str, Any], field: str) -> str:
    value = manifest_entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PmcIdentityError(f"manifest entry is missing {field}")
    return value.strip()


def extract_pmc_record(
    document: PmcJatsDocument,
    *,
    manifest_entry: Mapping[str, Any],
    element_id: str,
) -> dict[str, Any]:
    """Extract the first narrow PMC8292426-style rule into schema v0.2."""

    manifest_id = _manifest_value(manifest_entry, "id")
    if _manifest_value(manifest_entry, "pmcid").upper() != document.pmcid:
        raise PmcIdentityError("manifest PMCID does not match the parsed JATS article")
    if _manifest_value(manifest_entry, "doi").lower() != document.doi:
        raise PmcIdentityError("manifest DOI does not match the parsed JATS article")
    license_data = manifest_entry.get("license")
    if not isinstance(license_data, Mapping):
        raise PmcIdentityError("manifest entry is missing license metadata")
    if license_data.get("spdx") != document.license_spdx:
        raise PmcIdentityError("manifest SPDX license does not match the parsed JATS article")
    if license_data.get("url") != document.license_url:
        raise PmcIdentityError("manifest license URL does not match the parsed JATS article")

    elements = [
        element
        for element in iter_body_paragraphs(document.article)
        if element.element_id == element_id
    ]
    if len(elements) != 1:
        raise ValueError(
            f"expected exactly one native-ID body paragraph {element_id!r}; found {len(elements)}"
        )
    element: JatsTextElement = elements[0]
    text = element.text

    formula = PMC_MATERIAL_ALIAS_RE.search(text)
    methods = list(PMC_METHOD_RE.finditer(text))
    conditions = list(PMC_SAMPLE_CONDITION_RE.finditer(text))
    temperatures = list(PMC_TEMPERATURE_RE.finditer(text))
    missing: list[str] = []
    if formula is None:
        missing.append("Li2ZrCl6 (LZC) formula/alias definition")
    if not methods:
        missing.append("electrochemical impedance spectroscopy method")
    if not conditions:
        missing.append("as-milled sample condition")
    if not temperatures:
        missing.append("measurement temperature")
    if missing:
        raise ValueError("PMC evidence is missing " + ", ".join(missing))
    assert formula is not None

    conductivity, ionic_phrase, condition = _find_pmc_candidate(text, conditions)
    method = _nearest_match(methods, conductivity.start(), conductivity.end())
    temperature = _nearest_match(temperatures, conductivity.start(), conductivity.end())
    if (
        min(
            abs(temperature.start() - conductivity.end()),
            abs(conductivity.start() - temperature.end()),
        )
        > 160
    ):
        raise ValueError("No explicit temperature is close enough to the ionic claim")

    normalized_value, normalized_unit = _normalize_pmc_conductivity(conductivity)
    evidence_start = min(
        formula.start(),
        method.start(),
        condition.start(),
        ionic_phrase.start(),
        conductivity.start(),
        temperature.start(),
    )
    evidence_end = max(
        formula.end(),
        method.end(),
        condition.end(),
        ionic_phrase.end(),
        conductivity.end(),
        temperature.end(),
    )
    if evidence_end < len(text) and text[evidence_end] in ".?!":
        evidence_end += 1
    evidence_text = text[evidence_start:evidence_end]
    evidence_sha256 = sha256(evidence_text.encode("utf-8")).hexdigest()

    if text[evidence_start:evidence_end] != evidence_text:
        raise AssertionError("PMC evidence offsets do not reproduce evidence_text")
    if sha256(text.encode("utf-8")).hexdigest() != element.text_sha256:
        raise AssertionError("PMC element text hash changed during extraction")
    if sha256(evidence_text.encode("utf-8")).hexdigest() != evidence_sha256:
        raise AssertionError("PMC evidence hash changed during extraction")

    doi_url = f"https://doi.org/{document.doi}"
    return {
        "schema_version": "0.2.0",
        "source_artifact": {
            "manifest_entry_id": manifest_id,
            "identifier": doi_url,
            "title": document.title,
            "content_sha256": document.content_sha256,
            "content_hash_method": document.content_hash_method,
            "access_basis": "open_access",
            "doi": document.doi,
            "pmcid": document.pmcid,
            "pmcid_version": document.pmcid_version,
            "pmid": document.pmid,
            "license_spdx": document.license_spdx,
            "license_url": document.license_url,
            "retrieval": {
                "provider": "NCBI PMC OAI-PMH",
                "url": document.retrieval_url,
                "retrieved_at": document.retrieved_at,
            },
            "attribution": {
                "authors": list(document.authors),
                "title": document.title,
                "journal": document.journal,
                "doi_url": doi_url,
                "license_url": document.license_url,
                "change_notice": PMC_ATTRIBUTION_CHANGE_NOTICE,
            },
        },
        "source_anchor": {
            "type": "jats_element_text_span",
            "element_id": element.element_id,
            "xpath": element.xpath,
            "element_text_sha256": element.text_sha256,
            "character_start": evidence_start,
            "character_end": evidence_end,
            "evidence_text": evidence_text,
            "evidence_text_sha256": evidence_sha256,
        },
        "claim": {
            "subject": "Li2ZrCl6",
            "subject_alias": formula.group("alias"),
            "property": "ionic_conductivity",
            "reported_value": conductivity.group("reported"),
            "reported_unit": conductivity.group("unit"),
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "claim_type": "measured",
        },
        "qualifiers": {
            "temperature_value": temperature.group("value"),
            "temperature_unit": "°C",
            "measurement_method": "electrochemical impedance spectroscopy",
            "sample_condition": "as-milled",
        },
        "uncertainty": {
            "reported": None,
            "extraction_confidence": None,
        },
        "extraction_run": {
            "extractor": "proofgraph.rules.pmc8292426.par7.v1",
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
