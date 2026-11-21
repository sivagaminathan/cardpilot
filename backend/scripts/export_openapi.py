"""Export or verify the deterministic FastAPI OpenAPI 3.1 schema (T36, AC-14)."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

# Ensure `backend/` is on sys.path when invoked as `python scripts/export_openapi.py`
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.main import app  # noqa: E402

DEFAULT_OUTPUT = _BACKEND_DIR.parent / "docs" / "openapi.json"


def render_openapi_json() -> str:
    """Generate deterministic OpenAPI 3.1 JSON from the FastAPI application."""
    schema: dict[str, Any] = app.openapi()
    version = str(schema.get("openapi", ""))
    if not version.startswith("3.1"):
        raise ValueError(f"Expected OpenAPI 3.1.x schema, got {version!r}")
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export or verify CardPilot OpenAPI 3.1 schema.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to the committed openapi.json file.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed openapi.json matches the generated schema without writing.",
    )
    args = parser.parse_args(argv)

    rendered = render_openapi_json()
    output_path: Path = args.output

    if args.check:
        if not output_path.exists():
            print(f"ERROR: OpenAPI file missing at {output_path}", file=sys.stderr)
            return 1
        existing = output_path.read_text(encoding="utf-8")
        if existing != rendered:
            diff = "".join(
                difflib.unified_diff(
                    existing.splitlines(keepends=True),
                    rendered.splitlines(keepends=True),
                    fromfile=str(output_path),
                    tofile="generated-openapi.json",
                    n=2,
                )
            )
            print(
                "ERROR: Committed OpenAPI schema is stale. Run 'make openapi' to regenerate.\n"
                + diff[:2000],
                file=sys.stderr,
            )
            return 1
        print(f"OpenAPI 3.1 schema is up to date: {output_path}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(rendered)
    print(f"Exported OpenAPI 3.1 schema to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
