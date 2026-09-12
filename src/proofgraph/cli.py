from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .extract import extract_record
from .validate import SchemaRuntimeError, set_validation_result, validate_record


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _extract(args: argparse.Namespace) -> int:
    try:
        record = extract_record(args.input)
        errors = set_validation_result(record)
    except (OSError, UnicodeError, ValueError, SchemaRuntimeError) as exc:
        print(f"extract failed: {exc}", file=sys.stderr)
        return 2
    _write_json(Path(args.out), record)
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
