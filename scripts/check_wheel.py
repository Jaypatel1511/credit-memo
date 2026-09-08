"""
Assert the built wheel is shippable.

credit-memo 0.1.0 shipped a top-level `tests` package into site-packages, so
`import tests` in any environment with credit-memo installed resolved to this
project's test suite. It also declared setuptools>=42, a floor below the
version that can read [project], which builds a wheel whose Summary, License
and Requires-Python are all UNKNOWN.

    python scripts/check_wheel.py dist/*.whl
"""
import io
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def source_version() -> str:
    text = io.open(ROOT / "creditmemo" / "__init__.py", encoding="utf-8").read()
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def main(paths) -> int:
    failures = []
    if not paths:
        print("FAIL: no wheel given", file=sys.stderr)
        return 1

    for path in paths:
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
            value = re.search(r"^%s: (.*)$" % field, meta, flags=re.M)
            if not value or value.group(1).strip() in ("", "UNKNOWN"):
                failures.append(
                    "%s METADATA %s is missing or UNKNOWN — the build backend "
                    "could not read [project] (setuptools too old?)"
                    % (name, field)
                )

        version = re.search(r"^Version: (.*)$", meta, flags=re.M).group(1).strip()
        if version != source_version():
            failures.append("%s is version %s but creditmemo.__version__ is %s"
                            % (name, version, source_version()))

        if not any(n == "creditmemo/__init__.py" for n in names):
            failures.append("%s contains no creditmemo package modules" % name)

    if failures:
        for f in failures:
            print("FAIL:", f, file=sys.stderr)
        return 1
    print("OK: %s" % ", ".join(Path(p).name for p in paths))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
