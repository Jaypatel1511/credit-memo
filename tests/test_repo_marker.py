"""The `repo` marker is pinned in BOTH directions, by collection.

WHY THIS FILE EXISTS. release.yml's test-wheel and test-sdist jobs run the
suite from a directory holding only tests/, pyproject.toml and README.md, with
the package supplied by the installed wheel or sdist -- deliberately, because
that exclusion is what makes them prove the artifact rather than the checkout.
Eight gates here resolve `Path(__file__).resolve().parent.parent` as the repo
root and read setup.py or creditmemo/*.py. Reproduced in that layout before
they were marked (built wheel, fresh venv, CPython 3.11):

  * 2 FAILED -- test_setup_py_declares_no_duplicate_version (setup.py absent)
    and test_the_declared_dependency_gate_is_not_vacuous (no source to scan);
  * the other six PASSED ON ZERO FILES: `PACKAGE.rglob("*.py")` on a path that
    does not exist returns nothing without raising, so every "no shipped module
    does X" loop ran no iterations. Green, and certifying nothing.

This is the same failure class as nmtc-mapper release run #9 for 0.6.0, plus a
silent half nmtc-mapper did not have. The fix is to mark these gates `repo` and
have release.yml deselect them with `-m "not repo"`; `_package_sources()` now
also asserts it found files, so the silent half becomes loud if the
deselection is ever dropped.

A marker is a deselection, and a deselection can quietly become "deselect
everything" -- a module-level `pytestmark = pytest.mark.repo` on the wrong
file would leave the release jobs green having tested nothing. So the marked
set is pinned as an EXACT set here, and every module that computes the repo
root must be either marked or allow-listed with its reason.

WHAT IS AND IS NOT `repo`. README.md and pyproject.toml ship beside tests/ in
every layout -- the checkout, the sdist (MANIFEST.in), and the test-wheel job,
which copies both -- so a gate reading only those two is a gate about the
artifact and stays unmarked. setup.py and creditmemo/*.py are NOT in the run
directory of either release job.

HOW THE SET IS READ. `pytest --collect-only -q -m repo` in a subprocess from
the directory above tests/: the exact selection release.yml's `-m` expression
acts on, independent of how THIS test was invoked.

NOT `repo` ITSELF: this file reads only tests/, pyproject.toml and pytest's own
collection, so it runs in every layout -- including the release jobs, where it
proves the deselected set is exactly the pinned one.
"""
import pathlib
import re
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent  # the directory pytest is run from in every layout

# module -> the gates in it that read a repo-only path. Function names, not
# nodeids, so parametrisation does not move this list.
EXPECTED_REPO_GATES = {
    "test_input_fidelity.py": {
        # _package_sources(): creditmemo/**/*.py
        "test_g5_no_shipped_module_asserts_that_risks_do_not_exist",
        "test_g7_no_shipped_module_mentions_a_501_status",
        "test_g13_no_shipped_module_asks_word_for_a_number",
        "test_g10b_no_shipped_module_renders_the_old_sentence",
        "test_g16_no_shipped_module_writes_the_version_as_a_literal",
        # _package_source() -> _package_sources(), plus pyproject.toml
        "test_every_declared_runtime_dependency_is_actually_imported",
        "test_the_declared_dependency_gate_is_not_vacuous",
    },
    "test_packaging.py": {
        # setup.py
        "test_setup_py_declares_no_duplicate_version",
    },
}

# Derived from EXPECTED_REPO_GATES as it stands today (8 functions). Re-derive
# when the list resizes; a floor at zero would let the marks and the list
# vanish together.
REPO_GATE_FLOOR = 8

# Modules that compute the repo root and carry NO repo mark, with the reason.
ROOT_READERS_THAT_ONLY_READ_SHIPPED_FILES = {
    "test_docx.py": "reads README.md only (the Table Grid / bold-header and prepared_date README gates)",
    "test_repo_marker.py": "this file: reads tests/, pyproject.toml and pytest's own collection only",
}


def _collect(marker_expr):
    """Node ids pytest selects for `-m marker_expr`, from the directory above
    tests/ -- the cwd of every layout that runs this suite."""
    cmd = [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q",
           "-p", "no:cacheprovider", "-m", marker_expr]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    # exit 5 is "no tests collected" -- a legitimate answer of "none", which
    # the floor below then refuses. Anything else means the collection is not
    # trustworthy.
    assert proc.returncode in (0, 5), (
        "pytest --collect-only -m %r exited %d:\n%s\n%s"
        % (marker_expr, proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:]))
    return [ln.strip() for ln in proc.stdout.splitlines() if "::" in ln]


def _functions(nodeids):
    """{module: {function}} with parametrize ids stripped."""
    out = {}
    for nid in nodeids:
        path, _, rest = nid.partition("::")
        func = re.sub(r"\[.*\]$", "", rest.split("::")[-1])
        out.setdefault(pathlib.Path(path).name, set()).add(func)
    return out


@pytest.fixture(scope="module")
def marked():
    return _functions(_collect("repo"))


@pytest.fixture(scope="module")
def unmarked():
    return _functions(_collect("not repo"))


def test_the_repo_marked_set_clears_its_floor(marked):
    n = sum(len(fns) for fns in marked.values())
    assert n >= REPO_GATE_FLOOR, (
        "only %d functions carry @repo (floor %d); an empty or shrunken set "
        "means release.yml's `not repo` no longer deselects the source-tree "
        "gates, or this floor was not re-derived" % (n, REPO_GATE_FLOOR))
    assert sum(len(v) for v in EXPECTED_REPO_GATES.values()) >= REPO_GATE_FLOOR, (
        "EXPECTED_REPO_GATES shrank below the floor without the floor moving")


@pytest.mark.parametrize("module", sorted(EXPECTED_REPO_GATES))
def test_every_expected_repo_gate_is_marked(marked, module):
    """Direction one: every gate that reads a repo-only path is deselected."""
    missing = EXPECTED_REPO_GATES[module] - marked.get(module, set())
    assert not missing, (
        "%s: %s read a repo-only path but are not marked @repo -- they will "
        "fail, or pass on zero files, in release.yml's packaged layouts"
        % (module, sorted(missing)))


def test_no_gate_is_marked_repo_that_this_file_does_not_name(marked):
    """Direction two: a stray mark silently removes artifact coverage from the
    release jobs while ci.yml stays green."""
    stray = {
        m: sorted(fns - EXPECTED_REPO_GATES.get(m, set()))
        for m, fns in marked.items()
        if fns - EXPECTED_REPO_GATES.get(m, set())
    }
    assert not stray, (
        "marked @repo but not named in EXPECTED_REPO_GATES: %s" % (stray,))


def test_the_two_selections_partition_the_suite(marked, unmarked):
    both = {m: marked[m] & unmarked[m]
            for m in marked if m in unmarked and marked[m] & unmarked[m]}
    assert not both, "functions collected on both sides: %s" % (both,)
    for m in ("test_memo.py", "test_docx.py", "test_tables.py", "test_schema.py",
              "test_sections.py", "test_input_fidelity.py", "test_packaging.py"):
        assert m in unmarked, "%s is entirely deselected by `not repo`" % m


def test_every_module_that_computes_the_repo_root_is_accounted_for(marked):
    readers = sorted(
        p.name for p in HERE.glob("test_*.py")
        if re.search(r"\.parent\.parent\b", p.read_text(encoding="utf-8"))
    )
    assert len(readers) >= 3, "the sweep found only %s; it is not reading the suite" % readers
    unaccounted = [
        m for m in readers
        if m not in marked and m not in ROOT_READERS_THAT_ONLY_READ_SHIPPED_FILES
    ]
    assert not unaccounted, (
        "%s compute the repo root but carry no @repo mark and are not "
        "allow-listed in ROOT_READERS_THAT_ONLY_READ_SHIPPED_FILES" % unaccounted)
    stale = [m for m in ROOT_READERS_THAT_ONLY_READ_SHIPPED_FILES if m not in readers]
    assert not stale, "allow-listed but no longer compute the root: %s" % stale


def test_the_repo_marker_is_registered():
    """release.yml runs with --strict-markers, which turns an unregistered
    marker into a collection error. Read from pyproject.toml, which ships in
    every layout."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^\s*"repo:.*not repo', text, re.M), (
        "pyproject.toml [tool.pytest.ini_options].markers does not register `repo` "
        "with the release expression in its description")
