"""Tests for T36 OpenAPI 3.1 export determinism and stale-artifact detection (AC-14)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_openapi import DEFAULT_OUTPUT, main, render_openapi_json


def test_openapi_export_is_deterministic_and_valid_31() -> None:
    """Generated OpenAPI JSON is deterministic, 3.1.x, and includes all core API routes."""
    first = render_openapi_json()
    second = render_openapi_json()
    assert first == second

    parsed = json.loads(first)
    assert parsed["openapi"].startswith("3.1")
    paths = parsed["paths"]
    for expected_path in (
        "/healthz",
        "/readyz",
        "/api/v1/profiles/{profile_key}/recommendations",
        "/api/v1/profiles/{profile_key}/transactions",
        "/api/v1/profiles/{profile_key}/benefits",
        "/api/v1/profiles/{profile_key}/rewards/summary",
    ):
        assert expected_path in paths


def test_openapi_check_passes_for_committed_and_fails_when_stale(tmp_path: Path) -> None:
    """--check returns 0 for committed docs/openapi.json and 1 when stale or missing."""
    assert main(["--output", str(DEFAULT_OUTPUT), "--check"]) == 0

    missing_path = tmp_path / "missing.json"
    assert main(["--output", str(missing_path), "--check"]) == 1

    stale_path = tmp_path / "stale.json"
    stale_path.write_text('{"openapi": "3.1.0", "paths": {}}\n', encoding="utf-8")
    assert main(["--output", str(stale_path), "--check"]) == 1

    assert main(["--output", str(stale_path)]) == 0
    assert main(["--output", str(stale_path), "--check"]) == 0
