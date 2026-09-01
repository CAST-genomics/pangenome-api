"""What the endpoint does when a stage of the pipeline does not produce anything.

Written from a live failure. During the `increment-b` trial the server wedged:
a shared `pysam` handle broke (see `test_walk_derivatives.py`), and from then on
every extraction died partway through `GenerateWalksMC`. Two things made that
one hour of guessing rather than one look at a response:

* the half-written subgraph stayed on disk, and the cache took a *file at the
  path* for a finished extraction — so the affected regions kept failing at
  0.3 s, deterministically, long after the wedge was cleared and even across a
  restart, while every other region worked;
* the failure reached the client as a bare 500 from `FileResponse`, over a file
  no stage ever wrote. In the browser that is "Failed to fetch", because an
  unhandled exception is rendered outside the CORS middleware and arrives with
  no CORS headers on it. Nothing in it named a stage.

So: a cache hit means a subgraph with walks in it, an interrupted extraction
leaves nothing behind, and a stage that fails says which stage it was.

None of these tests needs `vg`, Node, or a pangenome: each stands in for the
stage it is not about, the way
`test_endpoints_do_not_block_the_event_loop.py` does.
"""

import os
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "seqtubemap"

# The same 90 bp subgraph the endpoint test uses, and the same reason: the
# endpoint builds exactly this filename from the query below.
CHROM, START, END, VERSION = "chr8", 78771162, 78771252, "v2"
SUBGRAPH = FIXTURES / f"subgraph_{CHROM}_{START}_{END}_{VERSION}_with_walk.gfa"
REQUEST = {"chrom": CHROM, "start": START, "end": END, "version": VERSION}


@pytest.fixture
def cache(main_module, tmp_path):
    """A working directory holding the cache the endpoint reads, and chdir into it.

    Every path the endpoint builds is relative to the process's working
    directory (`main.py:812`), so a test that wants to control the cache has to
    own the working directory too.
    """
    cache_dir = tmp_path / "cache" / "seqtubemap" / "mc"
    cache_dir.mkdir(parents=True)
    (tmp_path / "seqtubemap").symlink_to(REPO_ROOT / "seqtubemap")

    previous = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield cache_dir
    finally:
        os.chdir(previous)


@pytest.fixture
def no_extraction(main_module, monkeypatch):
    """Stand in for the two extraction stages, which need the multi-GB graph.

    They become no-ops, so whatever the test put in the cache is what the rest
    of the pipeline sees.
    """
    monkeypatch.setattr(main_module, "SubgraphMC", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "GenerateWalksMC", lambda *args, **kwargs: None)


def _walkless_copy_of(subgraph: Path) -> str:
    """The fixture subgraph with its `W` lines dropped.

    Exactly the artifact a failed extraction leaves: a structurally valid GFA,
    every `H`, `S` and `L` line present, and no paths in it — because
    `GenerateWalksMC` writes the walks last, after the whole segment section.
    """
    lines = subgraph.read_text().splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith("W\t")]
    assert len(kept) < len(lines), "the fixture has no W lines to drop"
    return "".join(kept)


# --- what counts as an extracted subgraph -----------------------------------


def test_a_subgraph_with_walks_is_cached(main_module):
    assert main_module.subgraph_has_walks(SUBGRAPH)


def test_a_subgraph_with_no_walks_is_not_cached(main_module, tmp_path):
    """The check that tells a finished extraction from an abandoned one."""
    walkless = tmp_path / "no_walks_with_walk.gfa"
    walkless.write_text(_walkless_copy_of(SUBGRAPH))

    assert not main_module.subgraph_has_walks(walkless)


def test_an_absent_subgraph_is_not_cached(main_module, tmp_path):
    assert not main_module.subgraph_has_walks(tmp_path / "not-here.gfa")


def test_an_empty_subgraph_is_not_cached(main_module, tmp_path):
    """The zero-byte case, which is what an extraction that died early leaves."""
    empty = tmp_path / "empty_with_walk.gfa"
    empty.write_bytes(b"")

    assert not main_module.subgraph_has_walks(empty)


def test_walks_are_found_however_large_the_segment_section(main_module, tmp_path):
    """The read is from the end of the file, so size must not decide the answer.

    A megabyte of `S` lines in front of the walks stands in for a real subgraph,
    where the segment section dwarfs everything: a check that read only the head
    of the file, or only a fixed prefix, would call this uncached.
    """
    large = tmp_path / "large_with_walk.gfa"
    large.write_text("H\tVN:Z:1.1\n" + "S\t1\tACGT\n" * 200000 + "W\tHG1\t1\tchr8\t0\t4\t>1\n")
    assert large.stat().st_size > 1 << 20

    assert main_module.subgraph_has_walks(large)


# --- an interrupted extraction leaves nothing behind ------------------------


class _WalkDerivativeFailingAfter:
    """A stand-in walk derivative that breaks partway, as the wedged handle did."""

    def __init__(self, fail_on_call):
        self.fail_on_call = fail_on_call
        self.calls = 0

    def fetch(self, *args, **kwargs):
        self.calls += 1
        if self.calls >= self.fail_on_call:
            raise OSError("could not create iterator for region")
        return iter(())


def test_an_interrupted_extraction_leaves_no_subgraph(main_module, tmp_path):
    """Not a walk-less one, and not a partial file either: nothing.

    This is the defect that outlived the wedge. The `W` lines are written after
    every `S` and `L` line, so a run that fails midway had already written a
    complete-looking segment section — and the next request read that as an
    extraction it did not have to repeat.
    """
    no_walk = tmp_path / "subgraph_no_walk.gfa"
    no_walk.write_text("H\tVN:Z:1.1\n" + "S\t1\tACGT\nS\t2\tGGTC\nS\t3\tTTTA\n")
    destination = tmp_path / "subgraph_with_walk.gfa"

    with pytest.raises(OSError):
        main_module.GenerateWalksMC(
            no_walk, destination, _WalkDerivativeFailingAfter(fail_on_call=2), main_module.api_log
        )

    assert not destination.exists(), "a failed extraction left a subgraph behind"
    assert not list(tmp_path.glob("*.partial-*")), "a failed extraction left its temporary behind"


def test_a_finished_extraction_is_renamed_into_place(main_module, tmp_path):
    """And the successful path still writes the file it is asked for."""
    no_walk = tmp_path / "subgraph_no_walk.gfa"
    no_walk.write_text("H\tVN:Z:1.1\nS\t1\tACGT\n")
    destination = tmp_path / "subgraph_with_walk.gfa"

    class OneWalk:
        def fetch(self, *args, **kwargs):
            return iter(["1\t1\t4\tHG1#1|chr8:0:+\t.\n"])

    main_module.GenerateWalksMC(no_walk, destination, OneWalk(), main_module.api_log)

    assert main_module.subgraph_has_walks(destination)
    assert not list(tmp_path.glob("*.partial-*"))


# --- a stage that fails says which stage it was ------------------------------


def test_a_walkless_cache_entry_is_reported_not_served(client, cache, no_extraction):
    """The live failure, end to end.

    With extraction stubbed out, a walk-less entry cannot be repaired — which is
    the position the server was in — so the request must fail. What is under test
    is *how*: a 502 naming `subgraph_extract`, rather than a 500 from
    `FileResponse` three stages later.
    """
    (cache / SUBGRAPH.name).write_text(_walkless_copy_of(SUBGRAPH))

    response = client.get("/seqtubemap", params=REQUEST)

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "subgraph_extract" in detail
    assert "W lines" in detail
    assert f"{CHROM}:{START}-{END}" in detail


def test_a_walkless_cache_entry_is_re_extracted(client, cache, main_module, monkeypatch):
    """And when extraction *can* run, the bad entry is replaced rather than served.

    Without this the entry is permanent: `path.exists()` was true, so the region
    stayed broken until somebody deleted the file by hand. Extraction is stood in
    for by one that writes the good subgraph, which is what a working server's
    would have done.
    """
    (cache / SUBGRAPH.name).write_text(_walkless_copy_of(SUBGRAPH))
    extractions = []

    def extract(no_walk, with_walk, *args, **kwargs):
        extractions.append(Path(with_walk))
        shutil.copy(SUBGRAPH, with_walk)

    monkeypatch.setattr(main_module, "SubgraphMC", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "GenerateWalksMC", extract)
    # The stage after extraction, so the test stops at the question it is asking.
    monkeypatch.setattr(main_module, "ConvertGfaToVg", lambda *args, **kwargs: False)

    response = client.get("/seqtubemap", params=REQUEST)

    assert extractions, "the walk-less entry was served as a cache hit"
    assert response.status_code == 502
    assert "gfa_to_vg" in response.json()["detail"]


# The renders, stubbed together wherever a test is about some other stage.
RENDERS = ("ConvertGfaToVg", "ConvertVgToJson", "GenerateSeqTubeMapSvg", "GenerateSeqTubeMapBands")


@pytest.mark.parametrize(
    "stage, stubbed, params",
    [
        ("gfa_to_vg", "ConvertGfaToVg", REQUEST),
        ("vg_to_json", "ConvertVgToJson", REQUEST),
        ("generate_svg", "GenerateSeqTubeMapSvg", REQUEST),
        # The band route's render is a different script and can fail for its own
        # reasons — a document too large for a 16-bit strand id, for one — so it
        # has to name itself rather than borrow the document route's name.
        ("generate_bands", "GenerateSeqTubeMapBands", {**REQUEST, "format": "bands"}),
    ],
)
def test_a_failing_stage_names_itself(client, cache, main_module, monkeypatch, stage, stubbed, params):
    """Each stage in turn, because each one used to fail the same anonymous way.

    All of them already returned a boolean nobody read. The response now carries
    the name of the one that returned False, and the tool's own stderr goes to
    the log next to it.
    """
    shutil.copy(SUBGRAPH, cache / SUBGRAPH.name)
    for name in RENDERS:
        monkeypatch.setattr(main_module, name, lambda *args, **kwargs: True)
    monkeypatch.setattr(main_module, stubbed, lambda *args, **kwargs: False)

    response = client.get("/seqtubemap", params=params)

    assert response.status_code == 502
    assert stage in response.json()["detail"]


def test_a_render_that_writes_no_document_is_reported(client, cache, main_module, monkeypatch):
    """A stage can also fail by succeeding quietly and writing nothing.

    `FileResponse` on a file that is not there is the 500 this whole file exists
    to replace, so the document's absence is checked before the response is
    built rather than by it.
    """
    shutil.copy(SUBGRAPH, cache / SUBGRAPH.name)
    for name in RENDERS:
        monkeypatch.setattr(main_module, name, lambda *args, **kwargs: True)

    response = client.get("/seqtubemap", params=REQUEST)

    assert response.status_code == 502
    assert "generate_svg" in response.json()["detail"]


def test_a_stage_failure_carries_cors_headers(client, cache, no_extraction):
    """Why the browser said "Failed to fetch" rather than showing the status.

    Starlette renders an unhandled exception outside the CORS middleware, so a
    bare 500 reaches a cross-origin caller with no `access-control-allow-origin`
    on it and the fetch fails at the network layer, status and body unread. An
    `HTTPException` is a response like any other and goes through the middleware,
    which is what lets the tube map panel show the reason.
    """
    (cache / SUBGRAPH.name).write_text(_walkless_copy_of(SUBGRAPH))

    response = client.get(
        "/seqtubemap", params=REQUEST, headers={"Origin": "https://pgb.example"}
    )

    assert response.status_code == 502
    # The middleware echoes the caller's origin when it is configured to allow
    # any; what matters is that the header is on the response at all, which is
    # what a bare 500 lacked.
    assert response.headers["access-control-allow-origin"] in ("*", "https://pgb.example")
