"""Automated AST check ensuring zero float usage in app.engine (T08, NFR-1).

Per AGENTS.md Hard Rule 6 and SPEC NFR-1:
No floats for money or rewards. Use integer cents and Decimal.
The engine package must not contain float literals, float type annotations,
or references to the built-in float type.
"""

import ast
from pathlib import Path


def find_engine_files() -> list[Path]:
    """Return all python files in the engine package."""
    engine_dir = Path(__file__).resolve().parents[2] / "app" / "engine"
    assert engine_dir.is_dir(), f"Engine directory not found at {engine_dir}"
    return sorted(engine_dir.glob("**/*.py"))


def check_ast_for_float(tree: ast.AST, filename: str) -> list[str]:
    """Scan an AST tree and return violations where float is used."""
    violations: list[str] = []

    for node in ast.walk(tree):
        # 1. Check for float literal constants (e.g. 1.5, 0.0)
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            violations.append(
                f"{filename}:{node.lineno}:{node.col_offset}: "
                f"Float literal {node.value!r} forbidden. Use Decimal or integer cents."
            )

        # 2. Check for identifiers named 'float' (e.g. x: float, float(x))
        elif isinstance(node, ast.Name) and node.id == "float":
            violations.append(
                f"{filename}:{node.lineno}:{node.col_offset}: "
                f"Reference to 'float' type/function forbidden. Use Decimal or int."
            )

    return violations


def test_no_float_in_engine_package() -> None:
    """Assert zero float literals or references in backend/app/engine/."""
    files = find_engine_files()
    assert len(files) > 0, "No python files found in app.engine"

    all_violations: list[str] = []
    for file_path in files:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        violations = check_ast_for_float(tree, file_path.name)
        all_violations.extend(violations)

    assert not all_violations, (
        f"Found {len(all_violations)} float usage(s) in app.engine:\n" + "\n".join(all_violations)
    )


def test_ast_checker_detects_synthetic_float() -> None:
    """Meta-test verifying that check_ast_for_float reliably flags float usage."""
    code_with_literal = "rate = 0.05"
    violations = check_ast_for_float(ast.parse(code_with_literal), "synthetic.py")
    assert any("Float literal" in v for v in violations)

    code_with_annotation = "def calc(x: float) -> None: pass"
    violations = check_ast_for_float(ast.parse(code_with_annotation), "synthetic.py")
    assert any("Reference to 'float'" in v for v in violations)

    code_with_cast = "val = float('12.34')"
    violations = check_ast_for_float(ast.parse(code_with_cast), "synthetic.py")
    assert any("Reference to 'float'" in v for v in violations)
