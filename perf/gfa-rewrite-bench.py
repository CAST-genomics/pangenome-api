"""
Times SeqTubeGfaProcessor's W->P rewrite in isolation.

Pure Python with no external tools, so it runs anywhere -- no gbz-base, no vg,
no data.path. Replicates main.py's rewrite loop exactly and reports throughput
against a synthetic GFA of the same shape the real pipeline produces.
"""
import random, re, time, io, os, sys, tempfile

WALKS = 464  # haplotype count is fixed input, not a variable

def make_gfa(path, walks, nodes_per_walk, seed=5):
    rnd = random.Random(seed)
    with open(path, "w") as f:
        f.write("H\tVN:Z:1.1\n")
        for nid in range(1, nodes_per_walk * 2):
            f.write(f"S\t{nid}\t{''.join(rnd.choice('ACGT') for _ in range(32))}\n")
        for w in range(walks):
            sample = "GRCh38" if w == 0 else f"HG{10000+w:05d}"
            walk = "".join(
                f"{'>' if rnd.random() < 0.9 else '<'}{rnd.randrange(1, nodes_per_walk*2)}"
                for _ in range(nodes_per_walk)
            )
            f.write(f"W\t{sample}\t{w%2+1}\tchr8\t0\t{nodes_per_walk*32}\t{walk}\n")

def rewrite(src, dst, pathnumoption):
    """Byte-for-byte the loop from main.py SeqTubeGfaProcessor."""
    input_gfa = open(src, "r")
    output_gfa = open(dst, "w")
    path_summary = {}
    hg38_line = ""
    for line in input_gfa:
        parts = line.strip().split("\t")
        header = parts[0]
        if header != "W":
            output_gfa.write(line)
            continue
        sample, haplo, contig, walk = parts[1], parts[2], parts[3], parts[6]
        walk_parts = re.split(r'([<>])', walk)[1:]
        walk_update = ""
        for i in range(1, len(walk_parts), 2):
            if walk_parts[i-1] == ">":
                walk_update += f"{walk_parts[i]}+,"
            else:
                walk_update += f"{walk_parts[i]}-,"
        walk_update = walk_update[:-1]
        if pathnumoption == "compressed":
            if sample == "GRCh38":
                hg38_line = f"P\t{sample}#{haplo}#{contig}\t{walk_update}\t*\n"
            else:
                if walk_update not in path_summary:
                    path_summary[walk_update] = f"{sample}#{haplo}#{contig}"
                else:
                    path_summary[walk_update] += f",{sample}#{haplo}#{contig}"
        else:
            output_gfa.write(f"P\t{sample}#{haplo}#{contig}\t{walk_update}\t*\n")
    if pathnumoption == "compressed":
        output_gfa.write(hg38_line)
        for path, assembly_list in path_summary.items():
            output_gfa.write(f"P\t{assembly_list}\t{path}\t*\n")
    input_gfa.close(); output_gfa.close()

print(f"walks={WALKS} (fixed)\n")
print(f"{'nodes/walk':>11} {'in_MB':>8} {'out_MB':>8} {'gen_s':>8} {'rewrite_s':>10} {'MB/s':>8}")
print("-" * 60)
tmp = tempfile.mkdtemp()
for npw in (200, 1000, 5000):
    src = os.path.join(tmp, f"in_{npw}.gfa")
    dst = os.path.join(tmp, f"out_{npw}.gfa")
    t0 = time.perf_counter(); make_gfa(src, WALKS, npw); gen = time.perf_counter() - t0
    t0 = time.perf_counter(); rewrite(src, dst, "normal"); el = time.perf_counter() - t0
    inmb = os.path.getsize(src) / 1048576
    outmb = os.path.getsize(dst) / 1048576
    print(f"{npw:>11} {inmb:>8.1f} {outmb:>8.1f} {gen:>8.1f} {el:>10.2f} {inmb/el:>8.1f}")
