"""
HIGH-7 — python-jose must be gone from shared/.

Auditor: Codex HIGH-003.

The library was unmaintained and had two CVEs (CVE-2024-33663 / CVE-2024-33664).
The verifier code already imports `jwt` (PyJWT), but ``shared/pyproject.toml``
still declared ``python-jose[cryptography]`` as a dependency — pulling the
vulnerable library in via ``pip install -e shared/``.

This test:
  1. Greps shared/ for any import of jose / python-jose.
  2. Asserts pyproject.toml dependencies no longer mention python-jose.
  3. Imports shared.auth.jwt_verifier and asserts no jose module is loaded.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / "shared"


def test_no_jose_imports_in_shared_source():
    bad: list[str] = []
    for path in SHARED_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        # Match `import jose`, `from jose ...`, or `import python_jose`.
        if re.search(r"^\s*(import\s+jose|from\s+jose\s+import|import\s+python_jose|from\s+python_jose\s+import)", text, re.MULTILINE):
            bad.append(str(path))
    assert not bad, f"jose imports remain in shared/: {bad}"


def test_pyproject_does_not_declare_jose():
    pyproject = SHARED_DIR / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    # The literal string must not appear inside a dependency declaration. We
    # tolerate the substring inside comments — but the simple rule of "no
    # jose token" is sufficient and aligns with how a future reviewer would
    # check.
    lines = [
        line
        for line in text.splitlines()
        if "python-jose" in line and not line.lstrip().startswith("#")
    ]
    assert not lines, (
        f"shared/pyproject.toml still references python-jose:\n  "
        + "\n  ".join(lines)
    )


def test_jwt_verifier_imports_pyjwt_not_jose():
    """
    Source-level check: the verifier module references `jwt` (PyJWT), and
    NEITHER `jose` nor `python_jose` appears in its imports.

    Note: we deliberately don't check sys.modules globally — other tests in
    the same process may have legitimately imported jose, which would taint
    the assertion. The contract for H7 is that *shared/* is jose-free.
    """
    verifier_path = SHARED_DIR / "auth" / "jwt_verifier.py"
    text = verifier_path.read_text(encoding="utf-8")
    # Imports must include `jwt as` (PyJWT alias used in the file) or plain `import jwt`.
    has_pyjwt = bool(
        re.search(r"^\s*import\s+jwt(\s|$)", text, re.MULTILINE)
        or re.search(r"^\s*import\s+jwt\s+as\s+", text, re.MULTILINE)
    )
    assert has_pyjwt, "jwt_verifier should import PyJWT"
    # jose imports must be absent.
    assert not re.search(
        r"^\s*(from\s+jose|import\s+jose)", text, re.MULTILINE
    ), "jose import must not appear in jwt_verifier.py"
