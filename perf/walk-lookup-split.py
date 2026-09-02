"""
Splits GenerateWalksMC's per-segment cost between the lookup and the parse.

This is the measurement docs/tube-map-pipeline.html says increment E is waiting
on. The stage timings put 30.0 of a 10,000-base region's 38 seconds inside
GenerateWalksMC, at a flat 65-79 ms per segment -- the signature of a fixed
overhead paid once per segment rather than of work that scales with the data.
What that number does not say is *which* fixed overhead:

  the lookup   one tabix seek into the bgzip-compressed .walk.gz, plus the
               decompression of whatever block the row lands in. Consecutive
               segment ids very likely share a block, so asking for them one at
               a time may decompress the same block repeatedly.

  the parse    tearing ~464 `assembly|contig:coord:strand` entries out of the
               returned row and accumulating them into the coordinate tables,
               in Python, a field at a time. ~177,000 entries for 381 segments.

The two imply different work. If it is the lookup, batching into range fetches
is most of the win and it is large. If it is the parse, batching removes the
seeks and the work stays, and E needs a different shape.

Four arms, over the same segment ids, so subtraction isolates each cost:

  point+parse   what main.py does today -- one fetch per S line, full parse
  point         the same fetches, rows consumed but not parsed
  range+parse   the proposed shape -- fetch each contiguous run of ids, parse
  range         the same range fetches, rows consumed but not parsed

  parse cost  = (point+parse) - (point)
  lookup cost = (point) - (range)
  E's time    = (range+parse), measured rather than predicted

Needs the real walk derivative and so runs on the server, not on a laptop.

Usage:
  python3 perf/walk-lookup-split.py <subgraph.gfa> [--walks PATH] [--repeat N]

  <subgraph.gfa>  any extracted subgraph; only its S lines are read. The five in
                  tests/fixtures/seqtubemap are real but small -- for a number
                  comparable to the document's, use a ~10,000-base extraction.
  --walks         defaults to the v2 derivative under `git config data.path`.
  --repeat        timed passes per arm, median reported (default 3).
"""
import argparse, os, statistics, subprocess, sys, time

try:
    import pysam
except ImportError:
    sys.exit("pysam is not importable. This script reads the real .walk.gz and "
             "is meant to run on the server, in the API's own environment.")

DEFAULT_WALKS = "hprc-v2.0-mc-grch38-v2.2.walk.gz"


def segment_ids(gfa_path):
    """Every S-line id, in file order -- exactly what the real loop iterates."""
    ids = []
    with open(gfa_path) as gfa:
        for line in gfa:
            if line[0] == "S":
                ids.append(int(line.split("\t")[1]))
    return ids


def contiguous_runs(ids):
    """Group into runs of consecutive ids, mirroring main.py:231-234."""
    runs = []
    for segment_id in sorted(ids):
        if not runs or runs[-1][-1] + 1 != segment_id:
            runs.append([segment_id])
        else:
            runs[-1].append(segment_id)
    return runs


def parse_row(row, coord_table, dup_coord_table):
    """The accumulation from _write_walks_mc, lifted verbatim (main.py:337-375).

    Kept identical on purpose: an approximation of the parse would make the
    subtraction meaningless. The only change is that the segment id comes from
    the row rather than from the caller's S line, which is the same integer.
    """
    _, node_id, length, asm_coord, asm_coord_dup = row.strip().split("\t")
    node_id = int(node_id)
    length = int(length)
    for single_coord in asm_coord.split(","):
        asm, contig_coord_strand = single_coord.split("|")
        contig, coord, strand = contig_coord_strand.split(":")
        coord = int(coord)
        if asm not in coord_table:
            coord_table[asm] = {contig: [[(coord, coord + length)], [node_id], [strand]]}
        else:
            if contig not in coord_table[asm]:
                coord_table[asm][contig] = [[(coord, coord + length)], [node_id], [strand]]
            else:
                coord_table[asm][contig][0].append((coord, coord + length))
                coord_table[asm][contig][1].append(node_id)
                coord_table[asm][contig][2].append(strand)
    if asm_coord_dup != ".":
        for dup_coord in asm_coord_dup.split(","):
            part = dup_coord.split("|")
            asm = part[0]
            if asm not in dup_coord_table:
                dup_coord_table[asm] = {}
            for i in range(1, len(part)):
                contig, coord, strand = part[i].split(":")
                coord = int(coord)
                if contig not in dup_coord_table[asm]:
                    dup_coord_table[asm][contig] = {node_id: [[(coord, coord + length)], [strand]]}
                else:
                    if node_id not in dup_coord_table[asm][contig]:
                        dup_coord_table[asm][contig][node_id] = [[(coord, coord + length)], [strand]]
                    else:
                        if any(coord == t[0] for t in dup_coord_table[asm][contig][node_id][0]):
                            continue
                        dup_coord_table[asm][contig][node_id][0].append((coord, coord + length))
                        dup_coord_table[asm][contig][node_id][1].append(strand)


# ---------- the four arms. Each returns (rows_seen, bytes_seen). ----------

def arm_point(walks, contig, ids, parse):
    coord_table, dup_coord_table, rows, nbytes = {}, {}, 0, 0
    for segment_id in ids:
        for row in walks.fetch(contig, segment_id - 1, segment_id):
            rows += 1
            nbytes += len(row)
            if parse:
                parse_row(row, coord_table, dup_coord_table)
    return rows, nbytes


def arm_range(walks, contig, ids, parse):
    """Fetch a run at a time, and skip rows for ids this subgraph does not hold.

    The skip is charged to the range arm rather than hidden, because a real
    implementation pays it: a run spanning 5,569 ids to cover 280 segments
    hands back every row in between.
    """
    wanted = set(ids)
    coord_table, dup_coord_table, rows, nbytes = {}, {}, 0, 0
    for run in contiguous_runs(ids):
        for row in walks.fetch(contig, run[0] - 1, run[-1]):
            if int(row.split("\t", 2)[1]) not in wanted:
                continue
            rows += 1
            nbytes += len(row)
            if parse:
                parse_row(row, coord_table, dup_coord_table)
    return rows, nbytes


ARMS = (
    ("point+parse", arm_point, True),
    ("point",       arm_point, False),
    ("range+parse", arm_range, True),
    ("range",       arm_range, False),
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gfa")
    ap.add_argument("--walks")
    ap.add_argument("--contig", default=".", help="the placeholder chrom column (default '.')")
    ap.add_argument("--repeat", type=int, default=3)
    args = ap.parse_args()

    walks_path = args.walks
    if not walks_path:
        data_path = subprocess.run(["git", "config", "data.path"],
                                   capture_output=True, text=True).stdout.strip()
        if not data_path:
            sys.exit("no --walks and `git config data.path` is unset.")
        walks_path = os.path.join(data_path, DEFAULT_WALKS)
    if not os.path.exists(walks_path):
        sys.exit(f"{walks_path} is not on this machine.")

    ids = segment_ids(args.gfa)
    runs = contiguous_runs(ids)
    span = max(ids) - min(ids) + 1
    print(f"{args.gfa}")
    print(f"  {len(ids)} segments, ids {min(ids)}-{max(ids)}, span {span}")
    print(f"  {len(runs)} contiguous run(s) -> {len(ids)} point fetches become {len(runs)}")
    print(f"  walks: {walks_path}\n")

    walks = pysam.TabixFile(walks_path)

    # Warm the page cache first, so the arms are compared against each other
    # rather than against whoever ran first. The absolute cold number is the one
    # already in the document; what is being decided here is the *ratio*.
    arm_range(walks, args.contig, ids, parse=False)

    results = {}
    for name, fn, parse in ARMS:
        times = []
        for _ in range(args.repeat):
            t0 = time.perf_counter()
            rows, nbytes = fn(walks, args.contig, ids, parse)
            times.append(time.perf_counter() - t0)
        results[name] = statistics.median(times)
        print(f"{name:>12}  {results[name]:7.3f} s   "
              f"{results[name]/len(ids)*1000:6.1f} ms/segment   "
              f"{rows} rows, {nbytes/1e6:.1f} MB")

    parse_cost = results["point+parse"] - results["point"]
    lookup_cost = results["point"] - results["range"]
    print(f"\n  parse            {parse_cost:7.3f} s   "
          f"({parse_cost/results['point+parse']*100:.0f}% of today)")
    print(f"  point-vs-range   {lookup_cost:7.3f} s   "
          f"({lookup_cost/results['point+parse']*100:.0f}% of today) <- what batching removes")
    print(f"\n  today            {results['point+parse']:7.3f} s")
    print(f"  batched          {results['range+parse']:7.3f} s   "
          f"{results['point+parse']/max(results['range+parse'], 1e-9):.1f}x")
    print("\nIf point-vs-range dominates, increment E is a range fetch and the win is large.")
    print("If parse dominates, batching removes the seeks and the work stays -- E needs")
    print("a different shape, and the parse itself is what has to get cheaper.")


if __name__ == "__main__":
    main()
