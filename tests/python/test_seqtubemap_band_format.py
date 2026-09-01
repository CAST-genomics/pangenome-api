"""`/seqtubemap?format=bands`: the band payload, over the endpoint.

The band route returns the numbers the layout computed instead of a drawing
document that encodes them — a JSON header carrying the document's dimensions,
the strand table and the segment boxes, and a binary body carrying six floats
and a strand id per band. `docs/band-format.md` is the specification; this file
is what holds the endpoint to it.

What is checked here is what a *client* can observe: that the parameter selects
the format, that an unrecognised value is refused rather than quietly served as
SVG, that omitting it returns exactly what the endpoint returned before, and
that the payload is complete enough to draw from — every band's strand id
resolving into the table, every per-strand value appearing once.

The renders run for real. `vg` does not: this file stands in for the two `vg`
stages with the committed conversion of the same subgraph, which is exactly
what they would have produced, so the Node render downstream is the real one.
That is deliberate — the band payload is written by that render and by nothing
else, and a test that stubbed it would be testing its own stub.
"""

import json
import os
import shutil
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "seqtubemap"

# The same 90 bp subgraph the other endpoint tests use — chr8:78,771,162-78,771,252
# over 9 segments and 464 strands. The endpoint builds these filenames from the
# query parameters below, which is what makes the cache hit.
CHROM, START, END, VERSION = "chr8", 78771162, 78771252, "v2"
NAME = f"subgraph_{CHROM}_{START}_{END}_{VERSION}"
SUBGRAPH = FIXTURES / f"{NAME}_with_walk.gfa"
VG_JSON = FIXTURES / f"{NAME}_with_walk.json"
REQUEST = {"chrom": CHROM, "start": START, "end": END, "version": VERSION}


def parse_payload(content: bytes) -> tuple[dict, memoryview]:
    """A band payload, read the way `docs/band-format.md` says to read one.

    Written out here rather than imported: the specification's whole claim is
    that a parser can be written against it without reading the server, and a
    test that called the server's own encoder back would not be evidence of
    that. Four lines is the whole of it.
    """
    (header_length,) = struct.unpack_from("<I", content, 0)
    header = json.loads(content[4 : 4 + header_length])
    body = memoryview(content)[(4 + header_length + 3) & ~3 :]
    return header, body


@pytest.fixture(scope="module")
def bands_workdir(main_module, tmp_path_factory):
    """A working directory holding the subgraph and its `vg` conversion.

    Every path the endpoint builds is relative to the process's working
    directory, so a test that wants to control the cache has to own the working
    directory too. The `.json` is placed where `vg view -j` would have written
    it; `vg_stages` is what stops the pipeline overwriting it.
    """
    workdir = tmp_path_factory.mktemp("bands")
    cache = workdir / "cache" / "seqtubemap" / "mc"
    cache.mkdir(parents=True)
    shutil.copy(SUBGRAPH, cache / SUBGRAPH.name)
    # `generate_bands_js_script` is relative too, so the generator has to be
    # reachable from the new working directory. A symlink keeps its real path
    # inside the repository, where `node_modules` is.
    (workdir / "seqtubemap").symlink_to(REPO_ROOT / "seqtubemap")
    return workdir


@pytest.fixture(scope="module")
def bands_client(client, node_stage, bands_workdir, main_module):
    """A client whose requests run from that directory, with `vg` stood in for.

    The two `vg` stages become a copy of the committed conversion of this very
    subgraph — the same bytes `vg convert -g` and `vg view -j` produce from it,
    obtained from the live server (tests/fixtures/seqtubemap/README.md) — so
    everything from the Node render onwards is real without needing `vg` on the
    machine.
    """
    cache = bands_workdir / "cache" / "seqtubemap" / "mc"

    def convert_to_vg(gfa_file, vg_file):
        Path(vg_file).write_bytes(b"")  # only its existence is checked
        return True

    def convert_to_json(vg_file, json_file):
        shutil.copy(VG_JSON, json_file)
        return True

    previous = Path.cwd()
    os.chdir(bands_workdir)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(main_module, "SubgraphMC", lambda *args, **kwargs: None)
        patch.setattr(main_module, "GenerateWalksMC", lambda *args, **kwargs: None)
        patch.setattr(main_module, "ConvertGfaToVg", convert_to_vg)
        patch.setattr(main_module, "ConvertVgToJson", convert_to_json)
        try:
            yield client
        finally:
            os.chdir(previous)
    assert (cache / SUBGRAPH.name).exists(), "the subgraph left the cache"


@pytest.fixture(scope="module")
def payload(bands_client):
    """The response to one `format=bands` request, parsed."""
    response = bands_client.get("/seqtubemap", params={**REQUEST, "format": "bands"})
    assert response.status_code == 200, response.text
    return response, *parse_payload(response.content)


# --- the parameter ----------------------------------------------------------


def test_an_unrecognised_format_is_refused(client):
    """Refused, and refused *before* the pipeline runs.

    Serving the default instead would hand a client that asked for numbers a
    document it cannot read — a failure that surfaces in the other repository,
    far from its cause. Needs neither `vg` nor Node: nothing has run yet when
    the request is turned away.
    """
    response = client.get("/seqtubemap", params={**REQUEST, "format": "geojson"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "geojson" in detail
    # And it says what it would have accepted, so the caller can fix it.
    assert "bands" in detail and "svg" in detail


def test_omitting_the_format_returns_what_it_always_did(bands_client):
    """The additive claim, from the client's side.

    The two repositories never have to deploy together, so a request that names
    no format has to be the request it was before this parameter existed. What
    this test can say is that omitting the parameter and passing `format=svg`
    are the same bytes and the same media type — that the parameter has a
    default and it is the document.

    That the document itself did not move is held elsewhere, where the bytes
    are actually pinned: the golden tests in `tests/node/` compare each render
    against a committed document, byte for byte, and would fail if the render
    had drifted. The two together are the claim; neither is it alone.
    """
    without = bands_client.get("/seqtubemap", params=REQUEST)
    explicit = bands_client.get("/seqtubemap", params={**REQUEST, "format": "svg"})

    assert without.status_code == 200
    assert without.headers["content-type"].startswith("image/svg+xml")
    assert without.content == explicit.content
    assert without.content.startswith(b'<svg id="mysvg"')


# --- what the band payload carries ------------------------------------------


def test_the_payload_is_a_json_header_and_a_binary_body(payload):
    response, header, body = payload

    assert response.headers["content-type"].startswith("application/octet-stream")
    assert header["format"] == "pangenome-bands"
    assert header["version"] == 1
    # The header maps the rest of the response, so a reader that knows only the
    # length prefix can reach every section of the body.
    assert len(body) == header["bodyLength"]
    assert header["band"]["kinds"]["byteOffset"] + header["band"]["count"] <= len(body)


def test_the_header_carries_the_documents_dimensions(payload):
    _, header, _ = payload

    document = header["document"]
    assert document["width"] > 0 and document["height"] > 0
    # The viewBox is the client's coordinate system; without it there is nothing
    # to draw the bands into.
    assert document["viewBox"].split() == [
        "0",
        str(document["extent"]["minYCoordinate"] - 20),
        str(document["width"]),
        str(document["height"]),
    ]


def test_the_strand_table_is_complete_and_says_each_value_once(payload):
    """The 41-47% of every SVG response that is per-strand values repeated.

    Here each one is a row: an id, a colour, a name and a PCLAI placement, said
    once for the whole document however many bands the strand draws.
    """
    _, header, _ = payload

    strands = header["strands"]
    assert len(strands) == 464, "this subgraph carries 464 strands"
    for strand in strands:
        assert set(strand) >= {"id", "name", "color", "pclaiX", "pclaiY", "pclaiScore"}
        # Three whole channels, not CSS: a client building a GPU buffer gets
        # numbers rather than the two spellings the layout writes.
        assert len(strand["color"]) == 3
        assert all(0 <= channel <= 255 and isinstance(channel, int) for channel in strand["color"])

    # `pgb` indexes tables by trackID, so the ids have to be exactly 0..n-1 —
    # no gaps, and nothing beyond the end.
    assert sorted(strand["id"] for strand in strands) == list(range(len(strands)))
    # And a name belongs to one row, which is what "exactly once" means here.
    names = [strand["name"] for strand in strands]
    assert len(set(names)) == len(names)


def test_every_bands_strand_id_resolves_into_the_table(payload):
    _, header, body = payload

    count = header["band"]["count"]
    assert count > 0
    ids = header["band"]["strandIds"]
    assert ids["type"] == "Uint16"

    strand_ids = struct.unpack_from(f"<{count}H", body, ids["byteOffset"])
    assert len(strand_ids) == count
    assert max(strand_ids) < len(header["strands"])
    # Not one strand drawn over and over: this is a population of strands.
    assert len(set(strand_ids)) > 1


def test_the_geometry_is_six_floats_a_band(payload):
    _, header, body = payload

    count = header["band"]["count"]
    geometry = header["band"]["geometry"]
    assert geometry["type"] == "Float32"
    assert geometry["fields"] == ["x0", "y0", "x1", "y1", "controlTop", "controlBottom"]
    assert geometry["byteLength"] == count * 6 * 4

    values = struct.unpack_from(f"<{count * 6}f", body, geometry["byteOffset"])
    width = header["document"]["width"]
    for index in range(count):
        x0, y0, x1, y1, control_top, control_bottom = values[index * 6 : index * 6 + 6]
        assert 0 <= x0 <= x1 <= width, f"band {index} runs backwards or off the document"
        # The control abscissae lie between the band's own ends, which is what
        # makes the six values a band rather than an arbitrary cubic.
        for control in (control_top, control_bottom):
            assert x0 - 1 <= control <= x1 + 1, f"band {index} control {control} is outside it"
        assert y0 == y0 and y1 == y1  # not NaN


def test_the_segment_boxes_travel_with_their_sequences(payload):
    """The segment boxes `pgb` reads today, carried whole rather than dropped.

    Asserted against the `S` lines of the fixture that went in, so this says
    the pipeline carried the right DNA through — not merely that boxes exist.
    """
    _, header, _ = payload

    expected = {}
    for line in SUBGRAPH.read_text().splitlines():
        if line.startswith("S\t"):
            _, segment_id, sequence = line.split("\t")[:3]
            expected[segment_id] = sequence

    segments = header["segments"]
    assert {segment["sequence"] for segment in segments} == set(expected.values())
    for segment in segments:
        assert segment["outline"].startswith("M ")
        assert segment["id"]


def test_the_band_payload_is_a_fraction_of_the_document(bands_client, payload):
    """The size the whole change is for, measured rather than projected.

    The figures are recorded per region in `docs/band-format.md`; what is
    asserted here is only the direction, so the numbers live in one place and
    this test does not need re-baselining every time the layout moves a
    coordinate.

    This is the 90 bp region, where the win is smallest by a wide margin: 464
    strands and only 592 bands, so the strand table — said once, but said in
    full — is most of the payload. The ratio is a fraction on the regions that
    matter, where the band count is in the tens of thousands.
    """
    response, header, _ = payload
    document = bands_client.get("/seqtubemap", params=REQUEST)

    assert len(response.content) < len(document.content), (
        f"band payload {len(response.content)} B against a "
        f"{len(document.content)} B document over {header['band']['count']} bands"
    )
