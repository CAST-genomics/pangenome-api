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

## The `.json` beside each `.gfa`

Each `.gfa` now has a matching `.json` — the same subgraph in the shape the Node stage
eats, so the layout can be driven on a machine with no `vg` binary and no Python. The
whole of increments B and C then runs from a checkout:

```
node seqtubemap/generate-svg.mjs \
  tests/fixtures/seqtubemap/subgraph_chr8_78771162_78771252_v2_with_walk.json \
  /tmp/out.svg 78771162 78771252 normal
```

**These were not produced by `vg`.** The server reaches this shape as
`vg convert -g | vg view -j` (`main.py:396-421`), and both binaries are Linux-only in
practice. These were produced instead by [`perf/gfa-to-vg-json.mjs`](../../../perf/gfa-to-vg-json.mjs),
which reads the GFA directly. Regenerate them with:

```
for f in tests/fixtures/seqtubemap/*.gfa; do
  node perf/gfa-to-vg-json.mjs "$f" "${f%.gfa}.json"
done
```

Only the fields the layout reads are emitted — `vgExtractNodes` (`seqtubemap/tubemap.js:3760`)
reads `node.id` and `node.sequence`; `vgExtractTracks` (`:3842`) reads `path.name`,
`path.freq` and `path.mapping[].position.{node_id,is_reverse}`. `L` lines are dropped: the
paths already describe the edges they use, and nothing in the layout looks at them. `freq`
is absent, as it is for W-line paths out of `vg`.

**What is verified.** Node and path counts match this file's `S` and walk columns exactly,
across all five. Every walk's node ids resolve into the node set. For the 90 bp fixture, the
464 strand names the layout emits are identical — as a set — to the 464 in its golden
document.

**What is not.** Nobody has diffed these against real `vg view -j` output, because nobody
here can run `vg`. Treat them as a development convenience, not as the wire truth, until
somebody with the binary confirms them.

## Two conventions — the goldens disagree with each other

While checking the naming above, the five golden documents in `pgb` turned out **not to be
one homogeneous set**:

| golden | strand names | form |
| --- | ---: | --- |
| `stm-chr8-78771162-78771252.svg` (90 bp) | 463 of 464 suffixed | `sample#hap#contig#N` |
| the other four | 0 suffixed | `sample#hap#contig` |

The suffixed form is the newer one — it is what "allow multiple walks per asm" (`0f69615`)
produces, and the 90 bp document is the most recently captured. So four of the five goldens
predate a change in how this pipeline names strands.

The geometry differs too, and by more than naming. Rendering the 90 bp fixture through
`generate-svg.mjs` gives 82 `<path>` and 517 `<rect>` against the golden's 291 and 726, and
a viewBox 3,795 wide against 4,717 — the golden's graph carries about two more segments per
strand than the `.gfa` committed here for the same region does.

**This matters for increment B**, which plans to use these pairs as an end-to-end oracle:
feed the `.gfa` in, expect the golden out. That does not hold today for the pair anyone
would reach for first. Either the goldens need recapturing from the current server, or the
`.gfa` inputs do. `perf/gfa-to-vg-json.mjs --names=bare` reproduces the older naming if the
older documents turn out to be the ones worth keeping.

## A note on `.gitignore`

The repository ignores `*.gfa*` (`.gitignore:4`) — subgraphs are normally transient cache
files, and the real graphs are far too large to commit. These five survive it because
`!tests/fixtures/**` (`.gitignore:34`) is the last matching rule and un-ignores the whole
fixtures tree.

That exemption was already there for `tiny-vg.json`, so nothing had to be added for these.
It does mean a `.gfa` fixture is only committable **under `tests/fixtures/`** — put one
anywhere else in the repo and `git add` will silently do nothing.
