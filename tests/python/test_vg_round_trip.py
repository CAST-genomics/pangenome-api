"""The `vg` seam: GFA in, vg JSON out.

`/seqtubemap` reaches Node through two `vg` subprocesses — `vg convert -g` then
`vg view -j` — and increment D of the roadmap deletes them. This pins what they
produce first, so the deletion has something to be checked against.

Every test here takes the `vg` fixture, which skips with a reason when the
binary is absent.
"""

import json

# A three-segment GFA with a bubble and one walk through it. Small enough to
# read, large enough that the round trip has something to carry.
TINY_GFA = """H\tVN:Z:1.1
S\t1\tACGT
S\t2\tA
S\t3\tG
S\t4\tTTTT
L\t1\t+\t2\t+\t0M
L\t1\t+\t3\t+\t0M
L\t2\t+\t4\t+\t0M
L\t3\t+\t4\t+\t0M
W\tGRCh38\t0\tchr1\t0\t9\t>1>2>4
W\tHG00001\t1\tchr1\t0\t9\t>1>3>4
"""


def test_a_gfa_round_trips_to_vg_json(vg, main_module, tmp_path):
    gfa_file = tmp_path / "subgraph.gfa"
    gfa_file.write_text(TINY_GFA)
    vg_file = tmp_path / "subgraph.vg"
    json_file = tmp_path / "subgraph.json"

    assert main_module.ConvertGfaToVg(str(gfa_file), vg_file)
    assert vg_file.stat().st_size > 0

    assert main_module.ConvertVgToJson(vg_file, json_file)
    document = json.loads(json_file.read_text())

    # The shape tubemap.js reads: segments under `node`, strands under `path`.
    assert {segment["sequence"] for segment in document["node"]} == {
        "ACGT",
        "A",
        "G",
        "TTTT",
    }
    # `vg` is free to decorate a W-line's name with a subrange suffix, so this
    # asserts the two strands survive the round trip, not how vg spells them.
    names = [strand["name"] for strand in document["path"]]
    assert len(names) == 2
    assert any(name.startswith("GRCh38") for name in names), names
    assert any(name.startswith("HG00001") for name in names), names
