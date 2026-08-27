# Subgraph fixtures — the inputs behind `pgb`'s golden tube maps

Five real `.gfa` subgraphs, captured from the live server on 2026-08-27. Each one is the
**input** to a `/seqtubemap` request whose **output** `pgb` already commits as a golden
document in `src/tubemap/__tests__/fixtures/`.

Until these landed, those golden documents pinned only the client side: `pgb` could check
that its parser read a tube map correctly, but nothing could check that this repository
produced that tube map in the first place. With the inputs committed, the pair becomes an
end-to-end fixture — feed the `.gfa` in, expect the golden document out.

## Provenance

These are not synthetic. They come off the HPRC v2 minigraph-cactus graph on
`pangenome-api.ucsd.edu`, requested by a colleague with server access following
[`docs/perf/deploy-request.md`](../../../docs/perf/deploy-request.md), and copied out of the
API's cache directory (`cache/seqtubemap/mc/`) exactly as the pipeline left them. The
filenames are the server's own.

Each file is the artifact `main.py:666-673` writes: `SubgraphMC` extracts the region from
the GBZ, then `GenerateWalksMC` adds the `W` lines. It is the file
[`ConvertGfaToVg`](../../../main.py) consumes, so it is the earliest point in the pipeline
that can be pinned without provisioning the multi-gigabyte graph.

**They cannot be regenerated locally.** Reproducing one requires the HPRC GBZ and the walk
derivatives, which are not in this repository and are not small. That is why they are
committed rather than fetched — and why they should not be deleted casually. Losing them
means another round trip to somebody else's server.

## The five

| file | region | span | `S` | `L` | strands | node bp |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `subgraph_chr8_78771162_78771252_v2_with_walk.gfa` | chr8:78,771,162-78,771,252 | 90 bp | 9 | 11 | 464 | 379 |
| `subgraph_chr1_25331046_25331646_v2_with_walk.gfa` | chr1:25,331,046-25,331,646 | 600 bp | 75 | 110 | 369 | 896 |
| `subgraph_chr8_10079054_10080461_v2_with_walk.gfa` | chr8:10,079,054-10,080,461 | 1.4 kb | 92 | 122 | 463 | 1,783 |
| `subgraph_chr1_25301271_25309238_v2_with_walk.gfa` | chr1:25,301,271-25,309,238 | 8.0 kb | 770 | 1,043 | 378 | 9,317 |
| `subgraph_chr1_25331646_25335796_v2_with_walk.gfa` | chr1:25,331,646-25,335,796 | 4.2 kb | 280 | 391 | 464 | 6,901 |

*strands* is distinct `sample#hap#seq` across the `W` lines, not the `W` line count — a
haplotype fragmented across the region contributes several walks but one strand. The two
differ only in the 8.0 kb file (383 walks, 378 strands) and the 4.2 kb one (1,201 walks,
464 strands), and that is exactly what makes those two worth having.

## Which golden document each one produces

Matched on strand count, which is a property of the region and is not constant — 369, 378,
463, 464 across this set. All five agree with the byte census in
[§8 of the findings](../../../docs/perf/seqtubemap-latency.md).

| this fixture | `pgb` golden document | output size | amplification |
| --- | --- | ---: | ---: |
| chr8:78,771,162+ (90 bp) | 90 bp | 0.29 MB | 5.7× |
| chr1:25,331,046+ (600 bp) | 600 bp | 3.37 MB | 18.9× |
| chr8:10,079,054+ (1.4 kb) | chr8 1.4 kb | 3.97 MB | 13.0× |
| chr1:25,301,271+ (8.0 kb) | node 5514 | 12.92 MB | 7.5× |
| chr1:25,331,646+ (4.2 kb) | node 5520 | 13.56 MB | 20.5× |

*amplification* is golden output ÷ this file. The last two sit at `pgb`'s fetch ceiling, so
they are the two that matter most for increment **B** — and the 4.2 kb region turning 694 KB
of graph into 13.56 MB of XML is the whole argument of
[ADR 0001](../../../docs/adr/0001-additive-band-format.md) in one row.

## A note on `.gitignore`

The repository ignores `*.gfa*` (`.gitignore:4`) — subgraphs are normally transient cache
files, and the real graphs are far too large to commit. These five survive it because
`!tests/fixtures/**` (`.gitignore:34`) is the last matching rule and un-ignores the whole
fixtures tree.

That exemption was already there for `tiny-vg.json`, so nothing had to be added for these.
It does mean a `.gfa` fixture is only committable **under `tests/fixtures/`** — put one
anywhere else in the repo and `git add` will silently do nothing.
