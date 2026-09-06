"""The batched walk lookup, pinned against the five committed subgraphs.

`GenerateWalksMC` used to call `fetch` once per `S` line. It now fetches one
contiguous run of segment ids at a time, which on these five fixtures turns
1,226 lookups into 11. #74 measured what that is worth: on the 8.0 kb region,
770 point fetches take 90 s where two range fetches take 0.31 s.

**The oracle is the fixtures' own `W` lines, byte for byte.** That is only
possible because a walk derivative can be *rebuilt* from them. The real
`hprc-v2.0-mc-grch38-v2.2.walk.gz` is team-generated, multi-gigabyte and not on
any machine that runs these tests -- the same reason #74 had to run on the
server. But `_write_walks_mc`'s output determines its input closely enough to
invert: a `W` line names an assembly, a contig, a start coordinate and an
ordered walk, and the `S` lines give every segment's length, so the coordinate
of each segment along each haplotype falls out by accumulation. Feed the rebuilt
derivative back in and the same `W` lines must come out.

That makes this a genuine end-to-end pin on real data, in CI, rather than a
comparison of the new code against a remembered copy of the old.

**What the rebuilt derivative is not.** Column 5, the repeat placements, is
written as `.` throughout, because a `W` line cannot say which of its
coordinates arrived that way. That is harmless for the oracle: a dup coordinate
that survived into the real output was reinserted into the regular lists
(`main.py:405-412`) and is reconstructed here as a regular placement, so the
same `W` line comes back. It does mean this file exercises the dedupe at
`main.py:373` with an empty table -- that filter is
[#76](https://github.com/CAST-genomics/PangenomeAPI/issues/76)'s business, and
`test_the_duplicate_quirks_are_preserved` below covers it directly instead.
"""

import re

import pytest

from conftest import REPO_ROOT

FIVE = sorted((REPO_ROOT / "tests" / "fixtures" / "seqtubemap").glob("*_with_walk.gfa"))

# What #75 buys, per fixture: `S` lines, and the runs they collapse into.
EXPECTED_RUNS = {
    "subgraph_chr1_25301271_25309238_v2_with_walk.gfa": (770, 2),
    "subgraph_chr1_25331046_25331646_v2_with_walk.gfa": (75, 2),
    "subgraph_chr1_25331646_25335796_v2_with_walk.gfa": (280, 5),
    "subgraph_chr8_10079054_10080461_v2_with_walk.gfa": (92, 1),
    "subgraph_chr8_78771162_78771252_v2_with_walk.gfa": (9, 1),
}


def _read(gfa):
    """Split a committed fixture into the part that goes in and the part that
    must come back out."""
    lengths, structure, walks = {}, [], []
    for line in open(gfa):
        if line[0] == "S":
            fields = line.rstrip("\n").split("\t")
            lengths[int(fields[1])] = len(fields[2])
            structure.append(line)
        elif line[0] in "HL":
            structure.append(line)
        elif line[0] == "W":
            walks.append(line)
    return lengths, structure, walks


def _rebuild_derivative_rows(lengths, walks):
    """Invert the `W` lines into the walk-table rows that would produce them.

    A walk is contiguous by construction -- the emitter starts a new `W` line
    wherever the coordinates stop meeting -- so segment coordinates accumulate
    straight off the start.
    """
    placements, assemblies = {}, []
    for walk_line in walks:
        _, sample, haplotype, contig, start, _, walk = walk_line.rstrip("\n").split("\t")
        assembly = f"{sample}#{haplotype}"
        if assembly not in assemblies:
            assemblies.append(assembly)
        coord = int(start)
        for sign, segment_id in re.findall(r"([><])(\d+)", walk):
            segment_id = int(segment_id)
            placements.setdefault(segment_id, []).append(
                (assembly, contig, coord, "+" if sign == ">" else "-")
            )
            coord += lengths[segment_id]

    # `coord_table` is an insertion-ordered dict and the emission loop walks it
    # in that order, so the order assemblies appear *within a row* decides the
    # order the `W` lines come out. First-appearance order across the fixture's
    # own walks is what produced it, so it is what reproduces it.
    rank = {assembly: i for i, assembly in enumerate(assemblies)}
    rows = []
    for segment_id in sorted(placements):
        entries = sorted(placements[segment_id], key=lambda p: rank[p[0]])
        column_four = ",".join(f"{a}|{c}:{coord}:{s}" for a, c, coord, s in entries)
        rows.append(f".\t{segment_id}\t{lengths[segment_id]}\t{column_four}\t.")
    return rows


def _tabix(rows, path):
    """bgzip and index the rebuilt rows on column 2, as the real one is."""
    import pysam

    plain = path.with_suffix(".txt")
    plain.write_text("\n".join(rows) + "\n")
    pysam.tabix_compress(str(plain), str(path), force=True)
    plain.unlink()
    pysam.tabix_index(
        str(path), force=True, seq_col=0, start_col=1, end_col=1, zerobased=False
    )
    return path


class _Derivative:
    """A `WalkDerivative` for a file that is present, without the lazy open."""

    def __init__(self, path):
        import pysam

        self._tabix_file = pysam.TabixFile(str(path))

    def fetch(self, *args, **kwargs):
        return self._tabix_file.fetch(*args, **kwargs)


@pytest.mark.parametrize("gfa", FIVE, ids=lambda p: p.name)
def test_the_walk_lines_come_back_byte_identical(main_module, tmp_path, gfa):
    """The acceptance criterion of #75, on all five committed subgraphs."""
    lengths, structure, expected_walks = _read(gfa)

    no_walk = tmp_path / "no_walk.gfa"
    no_walk.write_text("".join(structure))
    derivative = _tabix(_rebuild_derivative_rows(lengths, expected_walks),
                        tmp_path / "rebuilt.walk.gz")

    written = tmp_path / "with_walk.gfa"
    main_module.GenerateWalksMC(no_walk, written, _Derivative(derivative), main_module.api_log)

    produced = [line for line in open(written) if line[0] == "W"]
    assert produced == expected_walks


@pytest.mark.parametrize("gfa", FIVE, ids=lambda p: p.name)
def test_the_structure_lines_are_copied_through_unchanged(main_module, tmp_path, gfa):
    """Pass 1 still writes every H, S and L line, in file order.

    Separate from the oracle above because it is the half of the output that
    never touches the walk derivative, and a batching bug that dropped an `S`
    line would otherwise only show up as a confusing walk mismatch.
    """
    lengths, structure, expected_walks = _read(gfa)

    no_walk = tmp_path / "no_walk.gfa"
    no_walk.write_text("".join(structure))
    derivative = _tabix(_rebuild_derivative_rows(lengths, expected_walks),
                        tmp_path / "rebuilt.walk.gz")

    written = tmp_path / "with_walk.gfa"
    main_module.GenerateWalksMC(no_walk, written, _Derivative(derivative), main_module.api_log)

    assert [line for line in open(written) if line[0] != "W"] == structure


@pytest.mark.parametrize("gfa", FIVE, ids=lambda p: p.name)
def test_one_fetch_per_run_of_consecutive_ids(main_module, tmp_path, gfa):
    """The point of the change, asserted as a count rather than as a timing.

    1,226 lookups become 11 across the five. The counts are pinned so that a
    later refactor which quietly reverts to per-segment fetches fails here
    rather than only in production latency.
    """
    lengths, structure, expected_walks = _read(gfa)

    no_walk = tmp_path / "no_walk.gfa"
    no_walk.write_text("".join(structure))
    derivative = _tabix(_rebuild_derivative_rows(lengths, expected_walks),
                        tmp_path / "rebuilt.walk.gz")

    class Counting(_Derivative):
        fetches = 0

        def fetch(self, *args, **kwargs):
            Counting.fetches += 1
            return super().fetch(*args, **kwargs)

    main_module.GenerateWalksMC(
        no_walk, tmp_path / "with_walk.gfa", Counting(derivative), main_module.api_log
    )

    segments, runs = EXPECTED_RUNS[gfa.name]
    assert len(lengths) == segments
    assert Counting.fetches == runs


def test_runs_break_on_a_gap_and_follow_file_order(main_module):
    """`_contiguous_runs` groups in the order given, and never sorts.

    Sorting first would batch a non-ascending GFA more aggressively, at the cost
    of parsing its rows in a different order than the per-segment loop did --
    and `coord_table` is built by appending, so parse order breaks ties in the
    stable sort that emits the `W` lines. Grouping in file order cannot reorder
    anything, which is why there is no separate fallback path.
    """
    assert main_module._contiguous_runs([1, 2, 3]) == [[1, 2, 3]]
    assert main_module._contiguous_runs([1, 2, 5]) == [[1, 2], [5]]
    assert main_module._contiguous_runs([]) == []
    assert main_module._contiguous_runs([7]) == [[7]]
    # Descending, and consecutive-but-backwards: three runs, not one.
    assert main_module._contiguous_runs([3, 2, 1]) == [[3], [2], [1]]


def test_a_row_for_a_segment_the_subgraph_does_not_hold_is_skipped(main_module, tmp_path):
    """The filter §4(c) of the increment E document calls dead-but-deliberate.

    Exact runs never hand back a stray, so nothing in production reaches this
    today. It exists so that coalescing runs across a gap stays a one-line
    change, and it is tested because untested dead code is how that stops being
    true.
    """
    no_walk = tmp_path / "no_walk.gfa"
    no_walk.write_text("H\tVN:Z:1.1\nS\t1\tACGT\nS\t3\tGGGG\n")

    class RowsForEverySegment(_Derivative):
        def __init__(self):
            pass

        def fetch(self, contig, start, end):
            # Segment 2 is in the file but not in this subgraph. A coalescing
            # fetch would hand it back; it must not reach `coord_table`.
            return iter([
                "\t".join((".", str(i), "4", f"HG1#1|chr8:{i * 4}:+", "."))
                for i in range(start + 1, end + 1)
            ])

    written = tmp_path / "with_walk.gfa"
    main_module.GenerateWalksMC(no_walk, written, RowsForEverySegment(), main_module.api_log)

    walks = [line for line in open(written) if line[0] == "W"]
    assert walks == ["W\tHG1\t1\tchr8\t4\t8\t>1\n", "W\tHG1\t1\tchr8\t12\t16\t>3\n"]


def test_the_duplicate_quirks_are_preserved(main_module, tmp_path):
    """Bug for bug, on purpose -- they are #76's business, not #75's.

    A repeat placement already held for the same assembly, contig and segment is
    dropped silently (`main.py:373`), and one that survives is folded back into
    the regular lists only if it falls inside that assembly's own span
    (`main.py:405-412`). Both carry `TODO`s. The byte-identical oracle above
    pins them by construction; this pins them where a reader can see them.
    """
    no_walk = tmp_path / "no_walk.gfa"
    no_walk.write_text("H\tVN:Z:1.1\nS\t1\tACGT\nS\t2\tGGGG\nS\t3\tTTTT\n")

    class WithDuplicates(_Derivative):
        def __init__(self):
            pass

        def fetch(self, contig, start, end):
            rows = {
                1: (".", "1", "4", "HG1#1|chr8:0:+", "."),
                # Segment 2 carries the same dup coordinate twice. The second is
                # dropped. The survivor sits inside 0-12, so it is reinserted.
                2: (".", "2", "4", "HG1#1|chr8:4:+", "HG1#1|chr8:4:+|chr8:4:+"),
                # Segment 3's dup sits outside the span and is not reinserted.
                3: (".", "3", "4", "HG1#1|chr8:8:+", "HG1#1|chr8:400:+"),
            }
            return iter(
                "\t".join(rows[i]) for i in range(start + 1, end + 1) if i in rows
            )

    written = tmp_path / "with_walk.gfa"
    main_module.GenerateWalksMC(no_walk, written, WithDuplicates(), main_module.api_log)

    walks = [line for line in open(written) if line[0] == "W"]
    # Two `W` lines where the graph has one unbroken path, and segment 2 appears
    # in both. That is the quirk, and it is worth reading slowly:
    #
    #   - the *second* of segment 2's two identical dup entries is dropped by
    #     the dedupe at `main.py:373`, silently;
    #   - the *first* survives, falls inside HG1#1's own 0-12 span, and is
    #     reinserted at `main.py:405-412` -- next to the identical regular
    #     placement that was already there;
    #   - so `coord_table` now holds (4, 8) twice, the gap check sees a step
    #     that does not advance, and the walk is split in two.
    #
    # Segment 3's dup sits outside the span and is simply never reinserted.
    #
    # None of this is #75's to fix -- it is #76's -- and the byte-identical
    # oracle above depends on it staying exactly this wrong.
    assert walks == [
        "W\tHG1\t1\tchr8\t0\t8\t>1>2\n",
        "W\tHG1\t1\tchr8\t4\t12\t>2>3\n",
    ]
