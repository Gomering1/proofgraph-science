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
from .jats import (
    JatsTextElement,
    body_paragraph_by_section_position,
    iter_body_paragraphs,
)
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

PMC_NASICON_SUBJECT_RE = re.compile(r"Na3\.4Hf0\.6Sc0\.4ZrSi2PO12")
PMC_NASICON_OTHER_SUBJECT_RE = re.compile(r"Na3\.2Hf0\.8Sc0\.2ZrSi2PO12")
PMC_NASICON_IONIC_PHRASE_RE = re.compile(
    r"\btotal ionic conductivity\b", re.IGNORECASE
)
PMC_NASICON_FIRST_VALUE_RE = re.compile(r"(?<![\d.])0\.480?(?!\d)")
PMC_NASICON_RESPECTIVELY_RE = re.compile(r"\brespectively\b", re.IGNORECASE)
PMC_NASICON_SUBJECT_PAIR_BRIDGE_RE = re.compile(r"\s+and\s+", re.IGNORECASE)
PMC_NASICON_VALUE_INTRO_RE = re.compile(r"\s+of\s+", re.IGNORECASE)
PMC_NASICON_VALUE_PAIR_BRIDGE_RE = re.compile(r"\s+and\s+", re.IGNORECASE)
PMC_NASICON_ORDERING_TAIL_RE = re.compile(r"\s*,?\s*")
PMC_NASICON_METHOD_RE = re.compile(r"\bEIS\b")
PMC_NASICON_ELECTRODE_CONFIGURATION_RE = re.compile(
    r"Na metal as electrodes", re.IGNORECASE
)
PMC_HALIDE_SUBJECT_RE = re.compile(r"\bHE-SE\b")
PMC_HALIDE_CONDITION_RE = re.compile(r"\bas-prepared\b", re.IGNORECASE)
PMC_HALIDE_IONIC_PHRASE_RE = re.compile(
    r"\bHE-SE\s+exhibits\s+a\s+higher\s+ionic\s+conductivity\b",
    re.IGNORECASE,
)
PMC_HALIDE_VALUE_BRIDGE_RE = re.compile(r"\s+of\s+around\s+", re.IGNORECASE)
PMC_COMPOSITE_SUBJECT_RE = re.compile(r"\bcomposite SSEs\b", re.IGNORECASE)
PMC_COMPOSITE_IONIC_PHRASE_RE = re.compile(
    r"\bthe\s+maximum\s+total\s+ionic\s+conductivity\b", re.IGNORECASE
)
PMC_COMPOSITE_VALUE_BRIDGE_RE = re.compile(r"\s+of\s+", re.IGNORECASE)
PMC_COMPOSITE_RESULT_BRIDGE_RE = re.compile(
    r"\s+was\s+obtained(?:\s+at)?(?:\s+a)?\s+", re.IGNORECASE
)
PMC_COMPOSITE_METHOD_RE = re.compile(
    r"joint analysis of CA, EIS, and DS spectra", re.IGNORECASE
)
PMC_COMPOSITE_CONDITION_RE = re.compile(
    r"volume fraction of added TiO2 of 10%", re.IGNORECASE
)
PMC_CLAUSE_NEGATION_RE = re.compile(
    r"\b(?:no|not|never|neither|without)\b", re.IGNORECASE
)


class PmcExtractionAbstention(ValueError):
    """Raised when a checked article cannot support a single-anchor record."""


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


def _match_gap(first: re.Match[str], second: re.Match[str]) -> int:
    """Return the symmetric gap between two half-open match intervals."""

    if first.end() <= second.start():
        return second.start() - first.end()
    if second.end() <= first.start():
        return first.start() - second.end()
    return 0


def _relation_is_negated(text: str, relation_start: int) -> bool:
    """Detect an explicit negation earlier in the same short clause."""

    prefix = text[max(0, relation_start - 96) : relation_start]
    clause = re.split(r"[.!?;]", prefix)[-1]
    return PMC_CLAUSE_NEGATION_RE.search(clause) is not None


def _bind_conductivity_relation(
    text: str,
    conductivities: list[re.Match[str]],
    relation_pattern: re.Pattern[str],
    value_bridge_pattern: re.Pattern[str],
    *,
    field: str,
) -> tuple[re.Match[str], re.Match[str]]:
    """Require exactly one target value syntactically bound to an ionic phrase."""

    relations = list(relation_pattern.finditer(text))
    pairs = [
        (conductivity, relation)
        for conductivity in conductivities
        for relation in relations
        if relation.end() <= conductivity.start()
        and not _relation_is_negated(text, relation.start())
        and value_bridge_pattern.fullmatch(
            text[relation.end() : conductivity.start()]
        )
    ]
    if len(pairs) != 1:
        raise ValueError(
            f"expected exactly one {field} value bound to its explicit ionic "
            f"conductivity phrase; found {len(pairs)}"
        )
    return pairs[0]


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


def _find_nasicon_pair_relation(
    text: str,
) -> tuple[
    re.Match[str],
    re.Match[str],
    re.Match[str],
    re.Match[str],
    re.Match[str],
    re.Match[str],
]:
    """Bind two ordered materials to two ordered values via `respectively`."""

    first_subjects = list(PMC_NASICON_OTHER_SUBJECT_RE.finditer(text))
    second_subjects = list(PMC_NASICON_SUBJECT_RE.finditer(text))
    ionic_phrases = list(PMC_NASICON_IONIC_PHRASE_RE.finditer(text))
    first_values = list(PMC_NASICON_FIRST_VALUE_RE.finditer(text))
    target_values = [
        match
        for match in PMC_CONDUCTIVITY_RE.finditer(text)
        if _normalize_pmc_conductivity(match)[0] == "0.0012"
    ]
    ordering_words = list(PMC_NASICON_RESPECTIVELY_RE.finditer(text))
    candidates: list[
        tuple[
            re.Match[str],
            re.Match[str],
            re.Match[str],
            re.Match[str],
            re.Match[str],
            re.Match[str],
        ]
    ] = []
    for first_subject in first_subjects:
        for second_subject in second_subjects:
            if not PMC_NASICON_SUBJECT_PAIR_BRIDGE_RE.fullmatch(
                text[first_subject.end() : second_subject.start()]
            ):
                continue
            for ionic_phrase in ionic_phrases:
                if not (
                    second_subject.end() <= ionic_phrase.start()
                    and ionic_phrase.start() - second_subject.end() <= 96
                    and not _relation_is_negated(text, ionic_phrase.start())
                ):
                    continue
                for first_value in first_values:
                    if not PMC_NASICON_VALUE_INTRO_RE.fullmatch(
                        text[ionic_phrase.end() : first_value.start()]
                    ):
                        continue
                    for target_value in target_values:
                        if not PMC_NASICON_VALUE_PAIR_BRIDGE_RE.fullmatch(
                            text[first_value.end() : target_value.start()]
                        ):
                            continue
                        for ordering_word in ordering_words:
                            if (
                                target_value.end() <= ordering_word.start()
                                and PMC_NASICON_ORDERING_TAIL_RE.fullmatch(
                                    text[target_value.end() : ordering_word.start()]
                                )
                            ):
                                candidates.append(
                                    (
                                        first_subject,
                                        second_subject,
                                        ionic_phrase,
                                        first_value,
                                        target_value,
                                        ordering_word,
                                    )
                                )
    if len(candidates) != 1:
        raise ValueError(
            "expected exactly one NASICON ordered material/value relation; "
            f"found {len(candidates)}"
        )
    return candidates[0]


def _span_end_with_punctuation(text: str, end: int) -> int:
    if end < len(text) and text[end] in ".?!":
        return end + 1
    return end


def _build_pmc_record(
    document: PmcJatsDocument,
    *,
    manifest_id: str,
    element: JatsTextElement,
    subject: str,
    subject_alias: str | None,
    conductivity: re.Match[str],
    temperature: re.Match[str],
    method: re.Match[str],
    sample_condition: re.Match[str] | None,
    evidence_matches: tuple[re.Match[str], ...],
    extractor: str,
    uncertainty_reported: str | None = None,
    method_value: str | None = None,
    schema_version: str = "0.2.0",
) -> dict[str, Any]:
    text = element.text
    evidence_start = min(match.start() for match in evidence_matches)
    evidence_end = _span_end_with_punctuation(
        text, max(match.end() for match in evidence_matches)
    )
    evidence_text = text[evidence_start:evidence_end]
    evidence_sha256 = sha256(evidence_text.encode("utf-8")).hexdigest()

    if sha256(text.encode("utf-8")).hexdigest() != element.text_sha256:
        raise AssertionError("PMC element text hash changed during extraction")
    if sha256(evidence_text.encode("utf-8")).hexdigest() != evidence_sha256:
        raise AssertionError("PMC evidence hash changed during extraction")
    if subject not in evidence_text:
        raise ValueError("PMC claim subject is not contained in the bounded evidence")

    normalized_value, normalized_unit = _normalize_pmc_conductivity(conductivity)
    doi_url = f"https://doi.org/{document.doi}"
    claim: dict[str, Any] = {
        "subject": subject,
        "property": "ionic_conductivity",
        "reported_value": conductivity.group("reported"),
        "reported_unit": conductivity.group("unit"),
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        "claim_type": "measured",
    }
    if subject_alias is not None:
        claim["subject_alias"] = subject_alias
    qualifiers: dict[str, Any] = {
        "temperature_value": temperature.group("value"),
        "temperature_unit": "°C",
        "measurement_method": method_value or method.group(0),
    }
    if sample_condition is not None:
        qualifiers["sample_condition"] = sample_condition.group(0)

    source_anchor: dict[str, Any] = {
        "type": "jats_element_text_span",
        "element_id": element.element_id,
        "xpath": element.xpath,
        "element_text_sha256": element.text_sha256,
        "character_start": evidence_start,
        "character_end": evidence_end,
        "evidence_text": evidence_text,
        "evidence_text_sha256": evidence_sha256,
    }
    if schema_version == "0.3.0":
        source_anchor["ancestor_element_id"] = element.ancestor_element_id
        source_anchor["locator_scope"] = (
            "native_element_id"
            if element.element_id is not None
            else "native_ancestor_plus_xpath"
        )
    elif schema_version == "0.2.0":
        if element.element_id is None:
            raise ValueError("schema v0.2 requires a native paragraph element_id")
    else:
        raise ValueError(f"unsupported PMC record schema version {schema_version!r}")

    return {
        "schema_version": schema_version,
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
        "source_anchor": source_anchor,
        "claim": claim,
        "qualifiers": qualifiers,
        "uncertainty": {
            "reported": uncertainty_reported,
            "extraction_confidence": None,
        },
        "extraction_run": {
            "extractor": extractor,
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


def _manifest_value(manifest_entry: Mapping[str, Any], field: str) -> str:
    value = manifest_entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PmcIdentityError(f"manifest entry is missing {field}")
    return value.strip()


def extract_pmc_record(
    document: PmcJatsDocument,
    *,
    manifest_entry: Mapping[str, Any],
    element_id: str | None,
) -> dict[str, Any]:
    """Run one manifest-selected, fail-closed PMC smoke-test rule."""

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

    smoke_test = manifest_entry.get("local_smoke_test")
    profile = "lzc_as_milled_v1"
    if smoke_test is None:
        if not element_id:
            raise ValueError("element_id is required when no local_smoke_test is declared")
        elements = [
            element
            for element in iter_body_paragraphs(document.article)
            if element.element_id == element_id
        ]
        if len(elements) != 1:
            raise ValueError(
                f"expected exactly one native-ID body paragraph {element_id!r}; "
                f"found {len(elements)}"
            )
        element = elements[0]
    else:
        if not isinstance(smoke_test, Mapping):
            raise ValueError("local_smoke_test must be an object")
        profile_value = smoke_test.get("profile")
        locator = smoke_test.get("locator")
        if not isinstance(profile_value, str) or not profile_value:
            raise ValueError("local_smoke_test.profile must be a nonempty string")
        if not isinstance(locator, Mapping):
            raise ValueError("local_smoke_test.locator must be an object")
        profile = profile_value
        status = smoke_test.get("status")
        expected_status = (
            "documented_abstention"
            if profile == "air_exposure_abstain_v1"
            else "candidate_unreviewed"
        )
        if status != expected_status:
            raise ValueError(
                f"local_smoke_test status {status!r} does not match profile "
                f"{profile!r}"
            )
        locator_type = locator.get("type")
        if locator_type == "native_id":
            expected_id = locator.get("element_id")
            if not isinstance(expected_id, str) or not expected_id:
                raise ValueError("native_id locator requires element_id")
            if element_id is not None and element_id != expected_id:
                raise ValueError(
                    f"requested element_id {element_id!r} does not match manifest "
                    f"locator {expected_id!r}"
                )
            elements = [
                candidate
                for candidate in iter_body_paragraphs(document.article)
                if candidate.element_id == expected_id
            ]
            if len(elements) != 1:
                raise ValueError(
                    f"expected exactly one native-ID body paragraph {expected_id!r}; "
                    f"found {len(elements)}"
                )
            element = elements[0]
        elif locator_type == "section_child":
            section_id = locator.get("section_id")
            position = locator.get("paragraph_position")
            if not isinstance(section_id, str) or not section_id:
                raise ValueError("section_child locator requires section_id")
            if type(position) is not int:
                raise ValueError("section_child locator requires integer paragraph_position")
            if element_id is not None and element_id != section_id:
                raise ValueError(
                    f"requested element_id {element_id!r} does not match manifest "
                    f"section locator {section_id!r}"
                )
            element = body_paragraph_by_section_position(
                document.article,
                section_id=section_id,
                position=position,
            )
        else:
            raise ValueError(f"unsupported local_smoke_test locator type {locator_type!r}")

    text = element.text
    if profile == "lzc_as_milled_v1":
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
        temperature = _nearest_match(
            temperatures, conductivity.start(), conductivity.end()
        )
        if (
            min(
                abs(temperature.start() - conductivity.end()),
                abs(conductivity.start() - temperature.end()),
            )
            > 160
        ):
            raise ValueError("No explicit temperature is close enough to the ionic claim")
        return _build_pmc_record(
            document,
            manifest_id=manifest_id,
            element=element,
            subject=formula.group("formula"),
            subject_alias=formula.group("alias"),
            conductivity=conductivity,
            temperature=temperature,
            method=method,
            sample_condition=condition,
            evidence_matches=(
                formula,
                method,
                condition,
                ionic_phrase,
                conductivity,
                temperature,
            ),
            extractor="proofgraph.rules.pmc8292426.par7.v1",
            method_value="electrochemical impedance spectroscopy",
        )

    if profile == "nasicon_sc04_v1":
        method = PMC_NASICON_METHOD_RE.search(text)
        electrode_configuration = PMC_NASICON_ELECTRODE_CONFIGURATION_RE.search(
            text
        )
        if not all((method, electrode_configuration)):
            raise ValueError(
                "NASICON profile method or electrode configuration is absent"
            )
        assert method is not None and electrode_configuration is not None
        (
            first_subject,
            paired_subject,
            ionic_phrase,
            first_value,
            conductivity,
            ordering_word,
        ) = _find_nasicon_pair_relation(text)
        following_temperatures = list(
            PMC_TEMPERATURE_RE.finditer(
                text,
                ordering_word.end(),
                min(len(text), ordering_word.end() + 220),
            )
        )
        if len(following_temperatures) != 1:
            raise ValueError("NASICON profile has no unique nearby room temperature")
        temperature = following_temperatures[0]
        return _build_pmc_record(
            document,
            manifest_id=manifest_id,
            element=element,
            subject=paired_subject.group(0),
            subject_alias=None,
            conductivity=conductivity,
            temperature=temperature,
            method=method,
            sample_condition=None,
            evidence_matches=(
                method,
                electrode_configuration,
                first_subject,
                paired_subject,
                ionic_phrase,
                first_value,
                conductivity,
                ordering_word,
                temperature,
            ),
            extractor="proofgraph.rules.pmc10457403.par13.sc04.v1",
        )

    if profile == "halide_he_se_v1":
        subject = PMC_HALIDE_SUBJECT_RE.search(text)
        method = PMC_METHOD_RE.search(text)
        condition = PMC_HALIDE_CONDITION_RE.search(text)
        if not all((subject, method, condition)):
            raise ValueError("halide profile subject, method, or sample condition is absent")
        assert subject is not None and method is not None and condition is not None
        target_conductivities = [
            match
            for match in PMC_CONDUCTIVITY_RE.finditer(text)
            if _normalize_pmc_conductivity(match)[0] == "0.00213"
        ]
        conductivity, ionic_phrase = _bind_conductivity_relation(
            text,
            target_conductivities,
            PMC_HALIDE_IONIC_PHRASE_RE,
            PMC_HALIDE_VALUE_BRIDGE_RE,
            field="halide target",
        )
        temperature = _nearest_match(
            list(PMC_TEMPERATURE_RE.finditer(text)),
            conductivity.start(),
            conductivity.end(),
        )
        if _match_gap(temperature, conductivity) > 40:
            raise ValueError("halide profile target temperature is not adjacent to the value")
        return _build_pmc_record(
            document,
            manifest_id=manifest_id,
            element=element,
            subject=subject.group(0),
            subject_alias=None,
            conductivity=conductivity,
            temperature=temperature,
            method=method,
            sample_condition=condition,
            evidence_matches=(
                subject,
                method,
                condition,
                ionic_phrase,
                conductivity,
                temperature,
            ),
            extractor="proofgraph.rules.pmc10844219.par12.he_se.v1",
            uncertainty_reported="around",
            method_value="electrochemical impedance spectroscopy",
        )

    if profile == "composite_tio2_v1":
        subject = PMC_COMPOSITE_SUBJECT_RE.search(text)
        method = PMC_COMPOSITE_METHOD_RE.search(text)
        condition = PMC_COMPOSITE_CONDITION_RE.search(text)
        if not all((subject, method, condition)):
            raise ValueError("composite profile subject, method, or filler condition is absent")
        assert subject is not None and method is not None and condition is not None
        target_conductivities = [
            match
            for match in PMC_CONDUCTIVITY_RE.finditer(text)
            if _normalize_pmc_conductivity(match)[0] == "0.000031"
        ]
        conductivity, ionic_phrase = _bind_conductivity_relation(
            text,
            target_conductivities,
            PMC_COMPOSITE_IONIC_PHRASE_RE,
            PMC_COMPOSITE_VALUE_BRIDGE_RE,
            field="composite target",
        )
        if not PMC_COMPOSITE_RESULT_BRIDGE_RE.fullmatch(
            text[conductivity.end() : condition.start()]
        ):
            raise ValueError(
                "composite target value is not bound to an affirmative result "
                "and filler condition"
            )
        temperature = _nearest_match(
            list(PMC_TEMPERATURE_RE.finditer(text)),
            conductivity.start(),
            conductivity.end(),
        )
        if _match_gap(temperature, conductivity) > 220:
            raise ValueError("composite profile target temperature is not close enough")
        if not (
            subject.end()
            <= method.start()
            <= temperature.start()
            <= ionic_phrase.start()
            <= conductivity.start()
            <= condition.start()
        ):
            raise ValueError(
                "composite profile fields do not form the expected ordered relation"
            )
        return _build_pmc_record(
            document,
            manifest_id=manifest_id,
            element=element,
            subject=subject.group(0),
            subject_alias=None,
            conductivity=conductivity,
            temperature=temperature,
            method=method,
            sample_condition=condition,
            evidence_matches=(
                subject,
                method,
                condition,
                ionic_phrase,
                conductivity,
                temperature,
            ),
            extractor="proofgraph.rules.pmc9218661.sec0030.p1.tio2.v1",
            schema_version="0.3.0",
        )

    if profile == "air_exposure_abstain_v1":
        expected = (
            re.search(r"UDSH@LPSC", text),
            re.search(r"0\.8\s*±\s*0\.27\s*mS\s*cm[-−]1", text),
            re.search(r"3 days", text),
        )
        if not all(expected):
            raise ValueError("air-exposure abstention target changed; manual review required")
        if (
            PMC_TEMPERATURE_RE.search(text)
            or PMC_METHOD_RE.search(text)
            or PMC_NASICON_METHOD_RE.search(text)
        ):
            raise ValueError(
                "air-exposure abstention assumptions changed; manual review required"
            )
        raise PmcExtractionAbstention(
            "cross_paragraph_qualifiers_not_supported: Par18 contains the reported "
            "air-exposure value and duration, while measurement temperature and method "
            "are stated elsewhere; current schemas require one bounded evidence span"
        )

    raise ValueError(f"unsupported local_smoke_test profile {profile!r}")
