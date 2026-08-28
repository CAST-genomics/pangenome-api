# Subgraph fixtures — the inputs behind `pgb`'s golden tube maps

Five real `.gfa` subgraphs, captured from the live server on 2026-08-27. Each one is the
**input** to a `/seqtubemap` request whose **output** `pgb` already commits as a golden
document in `src/tubemap/__tests__/fixtures/`.

Until these landed, those golden documents pinned only the client side: `pgb` could check
that its parser read a tube map correctly, but nothing could check that this repository
produced that tube map in the first place.

They were committed in the hope that the pair would become an end-to-end fixture — feed
the `.gfa` in, expect the golden document out. That is not what they turned out to be, and
the reason is worth reading before relying on them: see
[How these relate to `pgb`'s golden documents](#how-these-relate-to-pgbs-golden-documents--checked-2026-08-28)
below. The short version is that the inputs are sound and the goldens are snapshots of
three different states of this pipeline, so the pin that runs in CI is self-baselined here
rather than borrowed from the other repository.

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

## Standing in for the graph at the cache path

`tests/python/test_seqtubemap_endpoint.py` copies the 90 bp `.gfa` into
`cache/seqtubemap/mc/` under a temporary working directory and requests that region.
The endpoint skips extraction when that file is present (`main.py:665-676`), so the rest
of the pipeline runs with no `.gbz` anywhere — which is why the filenames here must stay
exactly as the server wrote them: the endpoint rebuilds the name from the query
parameters, and a renamed fixture is a cache miss.

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

**What is not — and one place they are now known to differ.** Nobody has diffed these
against real `vg view -j` output, because nobody here can run `vg`. One difference is
already visible without running it: `vg` appends a subrange to a path that covers part of
a contig, which is why `pgb`'s 1.4 kb golden carries
`CHM13#0#chr8#0[9659985-9661740]`. This script never emits a subrange, and the `N` in its
`--names=fragment` form is a fragment counter it invents rather than `vg`'s phase block.
The two coincide on the fixtures whose walks are unfragmented, and that is luck rather than
agreement.

So: a development convenience, not the wire truth. Anything asserting a cross-repo contract
should run on `.json` a real `vg` produced.

## The `.pclai.json` beside each `.gfa`

A render takes **three** inputs, not two: the subgraph, the region, and the PCLAI colour
scheme. The scheme takes over strand colour entirely when it is present
(`seqtubemap/tubemap.js:2503`), and production passes one whenever `minigraphnode` is set
(`main.py:767`) — which is every request that produces one of these five. A fixture with
only the first two inputs can therefore only ever be rendered down a branch production does
not take.

Unlike the other two inputs, the scheme is not a file anybody here can produce: the
endpoint builds it from a minigraph walks file on the server (`GetPclaiColorScheme`,
`main.py:673`). What it *can* be read back out of is a document rendered with it, because
the generator writes every entry onto the elements it draws — the colour as `color`, and
the placement as `pclaiX`, `pclaiY` and `pclaiScore`. That is what these files are:

```
node perf/pclai-from-document.mjs <pgb-golden.svg> tests/fixtures/seqtubemap/<name>.pclai.json
```

recovered on 2026-08-28 from the five golden documents in `pgb`'s
`src/tubemap/__tests__/fixtures/`, one per fixture, keyed by the
`sample#haplotype#contig` triple the layout looks a strand up by. The shape is exactly what
`main.py` builds — `[[r, g, b], [x, y], score]`, with the score a string, because some of
them are not numbers — `"impainted"` appears in four of the five.

| fixture | placed strands | of | size |
| --- | ---: | ---: | ---: |
| chr8 90 bp | 452 | 464 | 28 KB |
| chr1 600 bp | 362 | 369 | 23 KB |
| chr8 1.4 kb | 451 | 463 | 28 KB |
| chr1 8.0 kb | 373 | 378 | 24 KB |
| chr1 4.2 kb | 364 | 464 | 23 KB |

**Every key is a strand of its own fixture, and no key is anything else** — checked across
all five, and now held there: `real-subgraph.band.test.mjs` asserts the exact set of keys
that found a strand, so a scheme and a subgraph that drift apart fail rather than quietly
colouring less. That is the evidence that these schemes are about these regions rather than
about the documents they were read out of: the two repositories' walks moved on between
capture and now (the 4.2 kb region's extra 100 strands are `0f69615`'s multiple walks per
assembly), but nothing in the scheme names a strand this subgraph does not contain.

**A strand with no placement is omitted, not written as grey.** The endpoint distinguishes
two cases that a document cannot: an entry whose `x_coord` is `"."` gets an explicit grey
no-coordinate row (`main.py:684`), and a strand the walks file never mentions gets no row
and falls back to the same light grey (`tubemap.js:2509`). Both draw identically, so a
document is no evidence about which one produced it. Omitting claims less and renders the
same picture, which is the property the baselines below rely on. The synthetic
`small-pclai` golden next door covers both shapes explicitly, so neither branch is
untested.

## The `.band.json.gz` beside each `.gfa` — the baseline

The **band data** each subgraph produces, which is what this repository actually pins
against. `tests/node/real-subgraph.band.test.mjs` renders all three inputs, compares the
band data to the baseline, and then rebuilds the document from that band data and checks it
in full.

Band data rather than a document because
[`docs/adr/0001`](../../../docs/adr/0001-additive-band-format.md) makes the band data
canonical and the document derived from it. A baselined document would pin the derived
artifact — a weaker guarantee, at ten times the size — and would have to be captured from a
server, which is what the two tests at the fetch ceiling spent their skipped life waiting
for.

Re-baseline deliberately, as part of an increment meant to change the layout's output:

```
npm run baseline:bands
```

### On-disk cost

They are committed. Gzip is what makes that reasonable: 18.02 MB of JSON compresses to
2.33 MB, and the fixture directory was already 19.9 MB of `.gfa` and `.json`.

| fixture | strands | bands | band JSON | committed (gz) | the document it rebuilds |
| --- | ---: | ---: | ---: | ---: | ---: |
| chr8 90 bp | 464 | 592 | 0.12 MB | 15 KB | 0.17 MB |
| chr1 600 bp | 369 | 8,089 | 1.43 MB | 186 KB | 2.83 MB |
| chr8 1.4 kb | 463 | 13,246 | 2.26 MB | 291 KB | 4.55 MB |
| **chr1 8.0 kb** | 383 | 35,020 | 6.26 MB | 800 KB | 12.48 MB |
| **chr1 4.2 kb** | 1,201 | 44,795 | 7.94 MB | 1,038 KB | 15.81 MB |
| | | | **18.02 MB** | **2.33 MB** | **35.84 MB** |

The last column is the reason the baselines are the band data: committing the documents
these rebuild would have cost 35.84 MB, and pinned less. *strands* here is band-data rows,
which is one per `W` line rather than one per strand — hence 1,201 on the 4.2 kb fixture.

The test compares the **decompressed** text, so nothing about zlib's output is pinned; a
different zlib would produce different bytes on disk and the same green.

## How these relate to `pgb`'s golden documents — checked, 2026-08-28

An earlier version of this file claimed the five golden documents disagreed with each
other about strand naming, and that the 90 bp golden's graph carried "about two more
segments per strand" than the `.gfa` here. **Both claims were wrong**, and issue #41 was
written on top of them. What follows is what a measurement found instead.

**The 90 bp pair matches.** Rendering the committed 90 bp `.gfa` with
`reorderTracksForLayout` disabled — the state of the layout on the day the golden was
captured — reproduces the golden exactly where it counts:

| | this fixture | `pgb`'s golden |
| --- | ---: | ---: |
| `<path>` | 291 | 291 |
| `<rect>` | 726 | 726 |
| viewBox | `0 -95 4717.4285714285725 7115` | `0 -95 4717.4285714285725 7115` |

The two documents share their first 210 bytes, and the strand name at the first
divergence is identical on both sides (`NA21309#2#CM092102.1#0`). The divergence itself is
a *colour*: the golden was captured with a PCLAI colour scheme (129 distinct fills, 92
grey fallbacks) which is not committed here. So the input, the graph, the geometry and the
naming all agree; only the third input to a render is missing.

**The naming difference was never a convention split.** `vg` names a W-line path
`sample#hap#contig#phaseblock`, and appends a subrange when the walk covers part of a
contig. All three forms in the goldens are that one rule seen at different times:

| golden | committed | example name |
| --- | --- | --- |
| 600 bp, node 5514, node 5520 | Aug 17, Aug 20 | `HG00097#1#CM094060.1` |
| 90 bp | Aug 18 | `HG00097#1#CM094064.1#0` |
| chr8 1.4 kb | Aug 25 | `CHM13#0#chr8#0[9659985-9661740]` |

`truncateTrackName` used to strip the tail inside `vgExtractTracks` and no longer does
(`0f69615`). The wire now carries `vg`'s spelling verbatim and the codebase truncates only
where it looks something up — see **strand** in [`CONTEXT.md`](../../../CONTEXT.md).
**Do not reach for `perf/gfa-to-vg-json.mjs --names=bare` to "fix" this.** On the 90 bp
fixture the suffixed names are the ones that match; bare names would break a pair that
works.

**Two fixtures genuinely do not match their goldens**, and it is the walk count that says
so, not the naming:

| fixture | `W` lines | strands | golden's strands |
| --- | ---: | ---: | ---: |
| chr8 90 bp | 464 | 464 | 464 |
| chr1 600 bp | 369 | 369 | 369 |
| chr8 1.4 kb | 463 | 463 | 463 |
| **chr1 8.0 kb** (node 5514) | **383** | 378 | 378 |
| **chr1 4.2 kb** (node 5520) | **1201** | 464 | 464 |

The last two carry `0f69615`'s multiple-walks-per-assembly output; their goldens come from
the one-walk-per-assembly era that preceded it. Those are the two that were, until #41
landed, waiting on a recaptured document that was never coming. They are now pinned like
the other three — by band data baselined here, from all three of their own inputs.

**These goldens are not this repository's oracle.** They were captured from `pgb`, at
various dates, from at least three different states of this pipeline — and
`docs/adr/0001-additive-band-format.md` makes the band data canonical and the document
derived. The table above is a dated cross-check that the two repositories agreed at a
point in time, which is the useful thing a captured document can say — and they said one
more, which #41 took them up on: the PCLAI colour scheme each region was rendered with is
written on their elements, and is now recovered into the `.pclai.json` files above. The pin
that runs in CI is self-baselined band data in this repository.

## A note on `.gitignore`

The repository ignores `*.gfa*` (`.gitignore:4`) — subgraphs are normally transient cache
files, and the real graphs are far too large to commit. These five survive it because
`!tests/fixtures/**` (`.gitignore:34`) is the last matching rule and un-ignores the whole
fixtures tree.

That exemption was already there for `tiny-vg.json`, so nothing had to be added for these.
It does mean a `.gfa` fixture is only committable **under `tests/fixtures/`** — put one
anywhere else in the repo and `git add` will silently do nothing.
