"""Shared setup for the Python tests.

Booting `main` is the whole difficulty here: it reaches for panCT, for four
tabix-indexed walk derivatives, and — through `bandage_graph` and
`adaptagrams_converter` — for two natively-compiled layout libraries that only
exist inside the Docker image. None of that is needed to answer "does the app
boot and serve", so this module stands each one up cheaply:

* the walk derivatives become tiny tabix files written into a temp directory,
* the native layout libraries become import stubs,
* panCT is used for real when the machine has it, and stubbed when it does not,
* `tools.path` and `data.path` are supplied through git's environment config,
  so the developer's own `git config --local` values are left alone.

The panCT stub is the one stand-in that costs something: a machine without
panCT boots the app against a placeholder `Region`, so a break in panCT's own
interface would not show up there. CI installs panCT for real and sets
`PANGENOME_TESTS_REQUIRE_ALL`, which turns every stand-in of that kind — and
every skip — into a failure, so the gap is closed where it matters.
"""

import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# CI sets this: there, a missing dependency is a broken workflow rather than a
# developer machine without `vg`, and must fail the build instead of skipping.
REQUIRE_ALL = os.environ.get("PANGENOME_TESTS_REQUIRE_ALL") == "1"

# The four `.walk.gz` derivatives `main` opens at import time (main.py:77-88).
WALK_FILES = (
    "hprc-v1.1-mc-grch38-mapped-flattened.walk.gz",
    "hprc-v2.0-mc-grch38-v2.2.walk.gz",
    "hprc_v1.0_minigraph_filtered_with_id.walk.gz",
    "v1_1_hprc_v2.0_minigraph.sorted.pclai.walk.gz",
)


def _skip_or_fail(reason: str) -> None:
    """Skip for a missing dependency — unless CI said there must not be one."""
    if REQUIRE_ALL:
        pytest.fail(f"{reason} (PANGENOME_TESTS_REQUIRE_ALL is set)")
    pytest.skip(reason)


def _write_walk_stand_ins(data_dir: Path) -> None:
    """Write one bgzipped, tabix-indexed stand-in per walk derivative.

    A few bed rows in place of a multi-gigabyte walk file: enough for
    `pysam.TabixFile` to open, which is all module import requires.
    """
    import pysam

    for name in WALK_FILES:
        plain = data_dir / name[: -len(".gz")]
        plain.write_text("chr1\t0\t100\nchr1\t100\t200\n")
        pysam.tabix_compress(str(plain), str(data_dir / name), force=True)
        plain.unlink()
        pysam.tabix_index(str(data_dir / name), preset="bed", force=True)


def _install_native_stubs() -> None:
    """Stub the layout libraries that are only built inside the Docker image."""
    if "ogdf_python" not in sys.modules:
        ogdf_python = types.ModuleType("ogdf_python")
        ogdf_python.ogdf = types.SimpleNamespace()
        ogdf_python.cppinclude = lambda *args, **kwargs: None
        sys.modules["ogdf_python"] = ogdf_python

    if "adaptagrams" not in sys.modules:
        sys.modules["adaptagrams"] = types.ModuleType("adaptagrams")


def _install_panct_stub() -> None:
    """Stand in for panCT with a placeholder `Region`.

    Only reached on a machine that does not have panCT. `Region` is the one
    name this codebase imports from it, and no test here does anything with a
    region beyond letting `main` import.
    """

    class Region:
        def __init__(self, chrom, start, end):
            self.chrom, self.start, self.end = chrom, start, end

    package = types.ModuleType("panCT")
    package.__path__ = []
    panct = types.ModuleType("panCT.panct")
    panct.__path__ = []
    data = types.ModuleType("panCT.panct.data")
    data.Region = Region
    logging_module = types.ModuleType("panCT.panct.logging")

    def getLogger(name=None, level="ERROR"):
        """panCT's signature: a name and a level, both keyword-friendly."""
        import logging

        logger = logging.getLogger(name)
        logger.setLevel(level)
        return logger

    logging_module.getLogger = getLogger

    sys.modules.update(
        {
            "panCT": package,
            "panCT.panct": panct,
            "panCT.panct.data": data,
            "panCT.panct.logging": logging_module,
        }
    )


def _panct_path() -> str | None:
    """Where panCT lives, or None if this machine does not have it.

    Honours `PANCT_PATH` first, then the `tools.path` the README asks
    developers to set.
    """
    candidates = [os.environ.get("PANCT_PATH")]
    try:
        candidates.append(
            subprocess.check_output(
                ["git", "config", "--get", "tools.path"], text=True
            ).strip()
        )
    except (subprocess.CalledProcessError, OSError):
        # No such config key, no git, or no repository — all mean "not here".
        pass

    for candidate in candidates:
        if candidate and (Path(candidate) / "panCT" / "panct").is_dir():
            return candidate
    return None


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory) -> Path:
    """A stand-in for the graph data directory, holding only the walk files."""
    directory = tmp_path_factory.mktemp("data")
    _write_walk_stand_ins(directory)
    return directory


@pytest.fixture(scope="session")
def main_module(data_dir):
    """The imported `main` module, with its heavy surroundings stood in for."""
    tools_path = _panct_path()
    if tools_path is None:
        if REQUIRE_ALL:
            pytest.fail(
                "panCT is not installed (PANGENOME_TESTS_REQUIRE_ALL is set): "
                "set PANCT_PATH to the directory containing it"
            )
        _install_panct_stub()
        tools_path = str(REPO_ROOT)

    _install_native_stubs()

    with pytest.MonkeyPatch.context() as patch:
        # git reads these ahead of any config file, so `git config --get`
        # inside main and its helpers resolves to the stand-ins without
        # touching .git/config — and they are undone when the session ends.
        patch.setenv("GIT_CONFIG_COUNT", "2")
        patch.setenv("GIT_CONFIG_KEY_0", "tools.path")
        patch.setenv("GIT_CONFIG_VALUE_0", tools_path)
        patch.setenv("GIT_CONFIG_KEY_1", "data.path")
        patch.setenv("GIT_CONFIG_VALUE_1", str(data_dir))
        patch.syspath_prepend(str(REPO_ROOT))

        import main

        yield main


@pytest.fixture(scope="session")
def app(main_module):
    """The booted FastAPI application."""
    return main_module.app


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture(scope="session")
def vg() -> str:
    """The `vg` binary, skipping the test when this machine has none."""
    binary = shutil.which("vg")
    if binary is None:
        _skip_or_fail("vg is not installed on this machine")
    return binary


@pytest.fixture(scope="session")
def node_stage() -> str:
    """The Node stage's prerequisites, skipping the test when they are absent.

    `GenerateSeqTubeMapSvg` shells out to `node seqtubemap/generate-svg.mjs`,
    which imports `jsdom` and `canvas` from the repository's `node_modules`.
    A checkout that has never had `npm ci` run in it cannot render a tube map.
    """
    binary = shutil.which("node")
    if binary is None:
        _skip_or_fail("node is not installed on this machine")
    if not (REPO_ROOT / "node_modules" / "jsdom").is_dir():
        _skip_or_fail("node_modules is not installed — run `npm ci`")
    return binary
