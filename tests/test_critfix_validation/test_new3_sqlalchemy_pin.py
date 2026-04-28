"""
NEW-3 — Python 3.14 + SQLAlchemy 2.0.36 incompatibility.

`Mapped[T | None]` with T = uuid.UUID raises TypeError on Python 3.14 when the
installed SQLAlchemy is < 2.0.40 (PEP 695 / typing module changes).

Fix: pin SQLAlchemy >= 2.0.40 in requirements.txt, document supported Python
versions, and ensure the model module imports cleanly on the running interpreter.
"""
from pathlib import Path

import pytest
import sqlalchemy


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_sqlalchemy_runtime_version_at_least_2_0_40():
    """The installed SQLAlchemy must be >= 2.0.40 to support Python 3.14."""
    parts = sqlalchemy.__version__.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2].split("+")[0])
    assert (major, minor, patch) >= (2, 0, 40), (
        f"SQLAlchemy {sqlalchemy.__version__} is too old; need >= 2.0.40 "
        f"for Python 3.14 compatibility."
    )


def test_requirements_txt_pins_sqlalchemy_at_least_2_0_40():
    """requirements.txt must declare a version >= 2.0.40."""
    req = _read(REPO_ROOT / "requirements.txt")
    assert "sqlalchemy" in req.lower(), "requirements.txt must include SQLAlchemy"
    # Look for a >= or == pin that is at least 2.0.40
    import re

    pattern = re.compile(
        r"sqlalchemy\b[^\n]*[>=]=\s*(?P<ver>\d+\.\d+\.\d+)",
        re.IGNORECASE,
    )
    matches = pattern.findall(req)
    assert matches, (
        "requirements.txt must pin SQLAlchemy with a version specifier "
        "(>= or ==) — none found"
    )
    pinned = matches[0]
    parts = [int(x) for x in pinned.split(".")]
    assert tuple(parts) >= (2, 0, 40), (
        f"requirements.txt SQLAlchemy pin {pinned!r} is < 2.0.40; "
        f"Python 3.14 needs >= 2.0.40"
    )


def test_pyproject_toml_pins_sqlalchemy_compatible_version():
    """compliance/backend/pyproject.toml must require SQLAlchemy >= 2.0.40."""
    pyp = REPO_ROOT / "compliance" / "backend" / "pyproject.toml"
    content = _read(pyp)
    assert "sqlalchemy" in content.lower(), (
        "pyproject.toml must declare a SQLAlchemy dependency"
    )
    import re

    pattern = re.compile(
        r"sqlalchemy[^\"']*[>=]=\s*(?P<ver>\d+\.\d+\.\d+)",
        re.IGNORECASE,
    )
    matches = pattern.findall(content)
    assert matches, "pyproject.toml must pin SQLAlchemy with a version"
    parts = [int(x) for x in matches[0].split(".")]
    assert tuple(parts) >= (2, 0, 40), (
        f"pyproject.toml SQLAlchemy pin {matches[0]!r} < 2.0.40; "
        f"Python 3.14 needs >= 2.0.40"
    )


def test_risk_model_imports_cleanly_on_current_python():
    """
    The Risk model uses `Mapped[uuid.UUID | None]` — this is the exact pattern
    that triggers TypeError on Python 3.14 + SQLA 2.0.36. If imports succeed
    here, the runtime SQLAlchemy version is compatible with the running
    interpreter.
    """
    from backend.models.risk import Risk  # noqa: F401
    from backend.models.user import User  # noqa: F401
    from backend.models.tenant import Tenant  # noqa: F401
    # If we reach this line, none of the model modules raised TypeError.
