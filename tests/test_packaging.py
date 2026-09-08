"""
Gates on release metadata.

credit-memo 0.1.0 carried the version string in three places (pyproject.toml,
setup.py and creditmemo/__init__.py) with nothing keeping them in step.
"""
import io
import re
from pathlib import Path

import creditmemo

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version() -> str:
    """Read [project].version without requiring tomllib (Python 3.11+)."""
    text = io.open(ROOT / "pyproject.toml", encoding="utf-8").read()
    section = re.split(r"^\[", text, flags=re.M)
    project = [s for s in section if s.startswith("project]")]
    assert project, "no [project] table in pyproject.toml"
    match = re.search(r'^version\s*=\s*"([^"]+)"', project[0], flags=re.M)
    assert match, "no version in [project]"
    return match.group(1)


def test_dunder_version_matches_pyproject():
    assert creditmemo.__version__ == _pyproject_version()


def test_setup_py_declares_no_duplicate_version():
    """setup.py is a shim; pyproject.toml is the single source of truth."""
    text = io.open(ROOT / "setup.py", encoding="utf-8").read()
    assert "version=" not in text


def test_build_backend_can_read_pep621_metadata():
    """
    setuptools below 61 cannot read [project]; it builds anyway and emits a
    wheel with Summary/License/Requires-Python all UNKNOWN. Pin the floor.
    """
    text = io.open(ROOT / "pyproject.toml", encoding="utf-8").read()
    match = re.search(r'setuptools>=(\d+)', text)
    assert match, "no setuptools floor declared in [build-system].requires"
    assert int(match.group(1)) >= 61
