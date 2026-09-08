"""
Assert the built distributions are shippable.

Wheel: credit-memo 0.1.0 shipped a top-level `tests` package into site-packages,
so `import tests` in any environment with credit-memo installed resolved to this
project's test suite. 0.1.0 also declared setuptools>=42, a floor below the
version that can read [project]; built with such a setuptools the wheel's
Summary, License and Requires-Python all come out UNKNOWN, and pip will then
install it on an unsupported interpreter. (The published 0.1.0 wheel does not
carry that defect — `python -m build` resolves the floor to a current setuptools
under build isolation — but anything building from that sdist without isolation
does.) This checks all three fields, plus the version, plus the contents.

Sdist: MANIFEST.in exists because the default sdist sweeps up tests/test_*.py
but not conftest.py or tests/__init__.py, which leaves the sdist's test suite
unrunnable. Nothing gated that, so this checks that the files MANIFEST.in adds
are actually in the tarball.

    python scripts/check_wheel.py dist/*.whl dist/*.tar.gz

Argument order does not matter; each path is dispatched on its suffix.
"""
import io
import re
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Files that must be in the sdist. Everything below the first blank group is
#: there because MANIFEST.in puts it there; without them the sdist ships a test
#: suite that cannot run and a build that cannot reproduce CI.
SDIST_REQUIRED = [
    "PKG-INFO",
    "pyproject.toml",
    "setup.py",
    "creditmemo/__init__.py",
    "creditmemo/tables.py",
    "creditmemo/renderers/docx.py",

    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "MANIFEST.in",
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/test_docx.py",
    "tests/test_tables.py",
    "scripts/check_wheel.py",
    "scripts/smoke_installed_wheel.py",
    ".github/workflows/ci.yml",
]


def source_version() -> str:
    text = io.open(ROOT / "creditmemo" / "__init__.py", encoding="utf-8").read()
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def metadata_field(meta: str, field: str):
    """The value of a single METADATA/PKG-INFO header, or None if unusable."""
    match = re.search(r"^%s: (.*)$" % re.escape(field), meta, flags=re.M)
    if not match:
        return None
    value = match.group(1).strip()
    return None if value in ("", "UNKNOWN") else value


def check_wheel(path, failures) -> None:
    zf = zipfile.ZipFile(path)
    names = zf.namelist()
    name = Path(path).name

    stray = sorted({n.split("/")[0] for n in names
                    if "/" in n and not n.split("/")[0].endswith(".dist-info")}
                   - {"creditmemo"})
    if stray:
        failures.append("%s installs unexpected top-level package(s): %s"
                        % (name, stray))

    top = [n for n in names if n.endswith("dist-info/top_level.txt")]
    if top:
        declared = zf.read(top[0]).decode().split()
        if declared != ["creditmemo"]:
            failures.append("%s top_level.txt is %s" % (name, declared))

    meta = zf.read(
        [n for n in names if n.endswith("dist-info/METADATA")][0]
    ).decode()
    for field in ("Summary", "Requires-Python"):
        if metadata_field(meta, field) is None:
            failures.append(
                "%s METADATA %s is missing or UNKNOWN — the build backend "
                "could not read [project] (setuptools too old?)"
                % (name, field)
            )
    # PEP 639 renamed the field; accept either spelling so a setuptools upgrade
    # does not read as a missing license.
    if not any(metadata_field(meta, f)
               for f in ("License", "License-Expression")):
        failures.append(
            "%s METADATA carries neither License nor License-Expression — the "
            "build backend could not read [project] (setuptools too old?)"
            % name
        )

    version = metadata_field(meta, "Version")
    if version != source_version():
        failures.append("%s is version %s but creditmemo.__version__ is %s"
                        % (name, version, source_version()))

    if not any(n == "creditmemo/__init__.py" for n in names):
        failures.append("%s contains no creditmemo package modules" % name)


def check_sdist(path, failures) -> None:
    name = Path(path).name
    tf = tarfile.open(path)
    names = tf.getnames()
    roots = {n.split("/")[0] for n in names}
    if len(roots) != 1:
        failures.append("%s has %d top-level entries: %s"
                        % (name, len(roots), sorted(roots)))
        return
    root = roots.pop()
    present = {n[len(root) + 1:] for n in names if n.startswith(root + "/")}

    missing = [m for m in SDIST_REQUIRED if m not in present]
    if missing:
        failures.append("%s is missing %s — MANIFEST.in is not doing its job, "
                        "and the sdist's test suite will not run" % (name, missing))

    if "PKG-INFO" in present:
        meta = tf.extractfile(root + "/PKG-INFO").read().decode()
        version = metadata_field(meta, "Version")
        if version != source_version():
            failures.append("%s is version %s but creditmemo.__version__ is %s"
                            % (name, version, source_version()))
        if metadata_field(meta, "Requires-Python") is None:
            failures.append("%s PKG-INFO has no Requires-Python" % name)


def main(paths) -> int:
    failures = []
    if not paths:
        print("FAIL: no wheel given", file=sys.stderr)
        return 1

    for path in paths:
        if path.endswith(".whl"):
            check_wheel(path, failures)
        elif path.endswith((".tar.gz", ".tgz")):
            check_sdist(path, failures)
        else:
            failures.append("%s is neither a wheel nor an sdist" % Path(path).name)

    if failures:
        for f in failures:
            print("FAIL:", f, file=sys.stderr)
        return 1
    print("OK: %s" % ", ".join(Path(p).name for p in paths))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
