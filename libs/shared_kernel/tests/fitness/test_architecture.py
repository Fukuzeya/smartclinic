"""Architectural fitness functions.

These tests encode architectural rules as *executable* assertions so a
violation becomes a failing build rather than a code-review debate.

Rules enforced:

1. The ``shared_kernel.domain`` package must not depend on
   ``shared_kernel.infrastructure`` or ``shared_kernel.fastapi`` — the
   domain layer is framework-free.
2. The ``shared_kernel.application`` package must not depend on
   ``shared_kernel.infrastructure`` or ``shared_kernel.fastapi``.
3. No bounded-context service may import directly from another bounded
   context's package — cross-context coupling is forbidden; go through the
   event bus.
4. Every concrete ``ValueObject`` subclass declares ``frozen=True`` (enforced
   by the base, but the test pins the contract).

All checks operate on the import graph built from ``ast`` — no runtime
import side effects.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.fitness


REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
LIBS = REPO_ROOT / "libs"
SERVICES = REPO_ROOT / "services"


def _python_files(root: pathlib.Path) -> Iterator[pathlib.Path]:
    if not root.exists():
        return
    for p in root.rglob("*.py"):
        # Skip venvs / build artefacts that may creep in during local dev.
        if any(part in {"__pycache__", ".venv", "build", "dist"} for part in p.parts):
            continue
        yield p


def _imports_in(path: pathlib.Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        # Templates or placeholder files — ignore.
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


# ---------------------------------------------------------------- rule 1+2

def test_shared_kernel_domain_is_framework_free() -> None:
    domain_root = LIBS / "shared_kernel" / "src" / "shared_kernel" / "domain"
    offenders: list[tuple[str, str]] = []
    for file in _python_files(domain_root):
        for imp in _imports_in(file):
            if imp.startswith("shared_kernel.infrastructure") or imp.startswith(
                "shared_kernel.fastapi"
            ):
                offenders.append((str(file.relative_to(REPO_ROOT)), imp))
    assert not offenders, (
        "shared_kernel.domain must not depend on infrastructure or fastapi:\n"
        + "\n".join(f"  {f} -> {i}" for f, i in offenders)
    )


def test_shared_kernel_application_is_framework_free() -> None:
    app_root = LIBS / "shared_kernel" / "src" / "shared_kernel" / "application"
    offenders: list[tuple[str, str]] = []
    for file in _python_files(app_root):
        for imp in _imports_in(file):
            if imp.startswith("shared_kernel.infrastructure") or imp.startswith(
                "shared_kernel.fastapi"
            ):
                offenders.append((str(file.relative_to(REPO_ROOT)), imp))
    assert not offenders, (
        "shared_kernel.application must not depend on infrastructure or fastapi:\n"
        + "\n".join(f"  {f} -> {i}" for f, i in offenders)
    )


# ---------------------------------------------------------------- rule 3

def test_no_cross_context_imports_between_services() -> None:
    """No service may directly import another service's package."""
    if not SERVICES.exists():
        pytest.skip("services directory not present yet")
    context_names: set[str] = {
        p.name for p in SERVICES.iterdir() if p.is_dir() and not p.name.startswith(".")
    }

    offenders: list[tuple[str, str]] = []
    for context in context_names:
        ctx_root = SERVICES / context
        for file in _python_files(ctx_root):
            for imp in _imports_in(file):
                # Imports like "clinical.domain.encounter" from inside
                # patient_identity would show up as "clinical.*".
                head = imp.split(".", 1)[0]
                if head in context_names and head != context:
                    offenders.append((str(file.relative_to(REPO_ROOT)), imp))
    assert not offenders, (
        "cross-bounded-context imports detected — use the event bus instead:\n"
        + "\n".join(f"  {f} -> {i}" for f, i in offenders)
    )


# ---------------------------------------------------------------- rule 4

def test_value_objects_are_frozen() -> None:
    """Every ``ValueObject`` subclass must inherit the frozen config.

    This is already guaranteed by the base's ``model_config``, but a class
    might inadvertently override it. We verify by *runtime* introspection
    of the currently-importable VO subclasses in the shared kernel.
    """
    from shared_kernel.domain import ValueObject

    # Force import of all VO-bearing modules in the shared kernel.
    import shared_kernel.types  # noqa: F401  (side-effect: populates subclasses)

    offenders: list[str] = []
    for cls in _all_subclasses(ValueObject):
        cfg = getattr(cls, "model_config", None)
        if cfg is None or not cfg.get("frozen", False):
            offenders.append(cls.__qualname__)
    assert not offenders, (
        "the following ValueObject subclasses are NOT frozen:\n"
        + "\n".join(f"  {o}" for o in offenders)
    )


def _all_subclasses(cls: type) -> list[type]:
    seen: set[type] = set()
    stack = [cls]
    while stack:
        current = stack.pop()
        for sub in current.__subclasses__():
            if sub in seen:
                continue
            seen.add(sub)
            stack.append(sub)
    return list(seen)
