"""The `/seqtubemap` endpoint, end to end, with no pangenome graph data.

The endpoint normally extracts its subgraph from a multi-gigabyte `.gbz` that
no developer machine has. It does not have to: the pipeline already skips
extraction when the extracted subgraph is present (`main.py:666-679`), an
existing production branch rather than a test hook. Placing one of the
committed golden subgraphs at that cache path makes everything downstream of
extraction runnable from a checkout.

The request therefore runs from a temporary working directory holding

    cache/seqtubemap/mc/<the golden subgraph>
    seqtubemap/ -> the repository's generator

because every path the endpoint builds is relative to the process's working
directory. Everything the pipeline writes lands in there and goes with it, so
nothing leaks into the repository or into the next test.

`vg` is still required: the pipeline reaches Node through `vg convert -g` and
`vg view -j`. Increment D of the roadmap removes that, and these assertions are
what it will be checked against — so they are written against what a client can
observe in the response, and not against the pipeline's intermediates, whose
disappearance is the point of increments B and D.
"""

import os
import shutil
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pytest

SVG_NS = "{http://www.w3.org/2000/svg}"

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "seqtubemap"

# The smallest of the five committed subgraphs: chr8:78,771,162-78,771,252, 90 bp
# over 9 segments. Its name is not decoration — the endpoint builds exactly this
# filename from the query parameters below, and that is what makes it cache-hit.
CHROM, START, END, VERSION = "chr8", 78771162, 78771252, "v2"
SUBGRAPH = FIXTURES / f"subgraph_{CHROM}_{START}_{END}_{VERSION}_with_walk.gfa"


def _segment_sequences(gfa: Path) -> dict[str, str]:
    """The `S` lines of a GFA, as id -> sequence."""
    segments = {}
    for line in gfa.read_text().splitlines():
        if line.startswith("S\t"):
            _, segment_id, sequence = line.split("\t")[:3]
            segments[segment_id] = sequence
    return segments


@pytest.fixture(scope="module")
def tube_map(client, vg, node_stage, main_module, tmp_path_factory):
    """The response to one `/seqtubemap` request over the golden subgraph.

    Module-scoped: the request runs the real `vg` pair and a real Node render,
    and every test below reads the same response rather than paying for its own.
    """
    workdir = tmp_path_factory.mktemp("seqtubemap")
    cache = workdir / "cache" / "seqtubemap" / "mc"
    cache.mkdir(parents=True)
    shutil.copy(SUBGRAPH, cache / SUBGRAPH.name)
    # `generate_svg_js_script` is relative too (main.py:80), so the generator
    # has to be reachable from the new working directory. A symlink keeps its
    # real path inside the repository, where `node_modules` is.
    (workdir / "seqtubemap").symlink_to(REPO_ROOT / "seqtubemap")

    # `main_module` is taken for its import, which resolves `data.path` before
    # the working directory moves out from under it.
    previous = Path.cwd()
    os.chdir(workdir)
    try:
        yield client.get(
            "/seqtubemap",
            params={"chrom": CHROM, "start": START, "end": END, "version": VERSION},
        )
    finally:
        os.chdir(previous)


@pytest.fixture(scope="module")
def document(tube_map):
    """The response parsed as XML, read by every test that inspects content."""
    return ElementTree.fromstring(tube_map.content)


def test_the_graph_the_endpoint_would_extract_from_is_absent(data_dir):
    """The premise of this file: there is no graph here to extract from.

    If a `.gbz` ever appeared beside the walk stand-ins, the request below
    could be passing for the ordinary reason, and would stop demonstrating
    anything about the cache branch.
    """
    assert not list(data_dir.glob("*.gbz"))


def test_the_endpoint_returns_an_svg_document(tube_map):
    assert tube_map.status_code == 200
    assert tube_map.headers["content-type"].startswith("image/svg+xml")


def test_the_document_is_well_formed(tube_map):
    # Parsed here rather than through the `document` fixture, so a malformed
    # document fails this test rather than erroring in every other one.
    root = ElementTree.fromstring(tube_map.content)

    assert root.tag == f"{SVG_NS}svg"
    # Without a viewBox the client has no coordinate system to draw into.
    assert root.get("viewBox")


def test_the_document_carries_bands_attributed_to_strands(document):
    """Bands are the drawable elements of `g.track`, keyed by strand.

    This is what `pgb`'s parser reads: a document whose bands carry no strand
    identity is a document it cannot colour.
    """
    tracks = document.find(f'{SVG_NS}g[@class="track"]')

    assert tracks is not None, "no g.track group in the document"
    bands = list(tracks)
    assert bands, "the track group carries no bands"
    assert all(
        band.get("trackID") is not None and band.get("trackName") is not None
        for band in bands
    )

    # The subgraph carries 464 strands and the layout draws a band per strand
    # per step, so what is recovered here is a population of strands rather
    # than one strand drawn repeatedly.
    strand_names = {band.get("trackName") for band in bands}
    assert len(strand_names) > 1, strand_names


def test_the_document_carries_the_subgraph_segments(document):
    """Segment boxes are `g.node`'s paths, each carrying its own sequence.

    Asserted against the `S` lines of the fixture that went in, so this says
    the pipeline carried the right DNA through — not merely that boxes exist.

    Equality holds because this subgraph's segments are neither merged nor
    reversed by the layout, and `vg` neither chops nor renumbers nodes this
    small. A break here is one of those four things changing, which is worth
    hearing about rather than tolerating.
    """
    segments = document.find(f'{SVG_NS}g[@class="node"]')

    assert segments is not None, "no g.node group in the document"
    boxes = list(segments)
    assert boxes, "the node group carries no segment boxes"

    expected = _segment_sequences(SUBGRAPH)
    assert {box.get("sequence") for box in boxes} == set(expected.values())
    assert all(box.get("d") for box in boxes), "a segment box has no outline"
