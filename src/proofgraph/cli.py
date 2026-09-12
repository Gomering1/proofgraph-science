from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .extract import extract_pmc_record, extract_record
from .pmc import MAX_LOCAL_XML_BYTES, normalize_pmcid, parse_pmc_oai_jats
from .validate import SchemaRuntimeError, set_validation_result, validate_record


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _ensure_distinct_output(output: Path, *protected: Path) -> None:
    output_target = output.resolve(strict=False)
    if any(output_target == path.resolve(strict=False) for path in protected):
        raise ValueError("output path must not overwrite an input or manifest file")


def _extract(args: argparse.Namespace) -> int:
    try:
        input_path = Path(args.input)
        output_path = Path(args.out)
        _ensure_distinct_output(output_path, input_path)
        record = extract_record(input_path)
        errors = set_validation_result(record)
        _write_json(output_path, record)
    except (OSError, UnicodeError, ValueError, SchemaRuntimeError) as exc:
        print(f"extract failed: {exc}", file=sys.stderr)
        return 2
    if errors:
        print(f"wrote invalid record with {len(errors)} error(s) to {args.out}")
        return 1
    print(f"wrote valid unreviewed record to {args.out}")
    return 0


def _validate(args: argparse.Namespace) -> int:
    try:
        path = Path(args.record)
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"validate failed: {exc}", file=sys.stderr)
        return 2
    try:
        if isinstance(record, dict):
            errors = set_validation_result(record)
        else:
            errors = validate_record(record)
    except SchemaRuntimeError as exc:
        print(f"validate failed: {exc}", file=sys.stderr)
        return 2
    if args.write:
        if not isinstance(record, dict):
            print("validate failed: --write requires a top-level JSON object", file=sys.stderr)
            return 2
        _write_json(path, record)
    if errors:
        print("invalid")
        for error in errors:
            print(f"- {error}")
        return 1
    print("valid")
    print(f"review status: {record['review']['status']}")
    return 0


def _manifest_entry(path: Path, pmcid: str) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    papers = manifest.get("papers") if isinstance(manifest, dict) else None
    if not isinstance(papers, list):
        raise ValueError("manifest must contain a papers array")
    matches = [
        paper
        for paper in papers
        if isinstance(paper, dict)
        and isinstance(paper.get("pmcid"), str)
        and paper["pmcid"].upper() == pmcid
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one manifest entry for {pmcid}; found {len(matches)}"
        )
    return matches[0]


def _extract_pmc(args: argparse.Namespace) -> int:
    try:
        input_path = Path(args.input)
        manifest_path = Path(args.manifest)
        output_path = Path(args.out)
        _ensure_distinct_output(output_path, input_path, manifest_path)
        pmcid = normalize_pmcid(args.pmcid)
        entry = _manifest_entry(manifest_path, pmcid)
        license_data = entry.get("license")
        if not isinstance(license_data, dict):
            raise ValueError("manifest entry is missing license metadata")
        doi = entry.get("doi")
        license_spdx = license_data.get("spdx")
        license_url = license_data.get("url")
        if not all(
            isinstance(value, str) and value
            for value in (doi, license_spdx, license_url)
        ):
            raise ValueError("manifest entry has incomplete DOI or license metadata")
        with input_path.open("rb") as source:
            raw_xml = source.read(MAX_LOCAL_XML_BYTES + 1)
        document = parse_pmc_oai_jats(
            raw_xml,
            expected_pmcid=pmcid,
            expected_doi=doi,
            expected_license_spdx=license_spdx,
            expected_license_url=license_url,
        )
        record = extract_pmc_record(
            document,
            manifest_entry=entry,
            element_id=args.element_id,
        )
        errors = set_validation_result(record)
        _write_json(output_path, record)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
        SchemaRuntimeError,
    ) as exc:
        print(f"extract-pmc failed: {exc}", file=sys.stderr)
        return 2
    if errors:
        print(f"wrote invalid record with {len(errors)} error(s) to {args.out}")
        return 1
    print(f"wrote valid unreviewed record to {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proofgraph",
        description="ProofGraph Science pre-alpha evidence-record prototype",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser(
        "extract", help="extract one supported record from an HTML fixture"
    )
    extract.add_argument("input")
    extract.add_argument("--out", required=True)
    extract.set_defaults(func=_extract)

    extract_pmc = subparsers.add_parser(
        "extract-pmc",
        help="extract one record from a user-supplied local PMC OAI/JATS XML file",
    )
    extract_pmc.add_argument(
        "input",
        help="local OAI-PMH GetRecord XML; the command performs no download",
    )
    extract_pmc.add_argument("--pmcid", required=True)
    extract_pmc.add_argument(
        "--manifest",
        required=True,
        help="read-only corpus manifest providing the asserted DOI and license",
    )
    extract_pmc.add_argument("--element-id", required=True)
    extract_pmc.add_argument("--out", required=True)
    extract_pmc.set_defaults(func=_extract_pmc)

    validate = subparsers.add_parser("validate", help="validate a record")
    validate.add_argument("record")
    validate.add_argument(
        "--write", action="store_true", help="write validation results into the file"
    )
    validate.set_defaults(func=_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
