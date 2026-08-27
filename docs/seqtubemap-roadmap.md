# `/seqtubemap` rework — the roadmap

The execution sequence for the `/seqtubemap` plumbing work: fourteen tickets, what each
delivers, what gates it, and what has to be true before it is called done.

This is the **build** document. Its companions:

| | |
| --- | --- |
| [`CONTEXT.md`](../CONTEXT.md) | the vocabulary — **strand**, **segment**, **band**, **node** |
| [`docs/adr/0001`](./adr/0001-additive-band-format.md) | the decision, and the alternatives that were rejected |
| [`docs/perf/seqtubemap-latency.md`](./perf/seqtubemap-latency.md) | the measurements, §1-9 |
| [`docs/perf/seqtubemap-plan.md`](./perf/seqtubemap-plan.md) | which skill drives each phase |
| [`docs/perf/deploy-request.md`](./perf/deploy-request.md) | the ask that unblocks [#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16) |
| [#13](https://github.com/CAST-genomics/PangenomeAPI/issues/13) | the spec these tickets decompose |

Written 2026-08-27, at the end of the grilling and ticketing phase.

---

## The one-sentence version

**`/seqtubemap` publishes the numbers it already has, instead of emulating a browser to
hide them in XML.**

## Why

A researcher clicks a **minigraph node** to look inside it. Roughly 43% of the time nothing
appears. When it works, a 10 kb region takes 120 seconds and delivers 10 MB — and the
frontend gives up at 90, so for a large node the feature is simply unavailable, with no way
to tell in advance which nodes will work.

And the failure is not contained. Both endpoints are `async def` while every stage blocks,
so one slow tube map request stalls **every** other request to the server, including the
`/json` the 3D graph depends on.

One cause sits under all three symptoms. The server computes the geometry, then boots a
headless browser, builds a jsdom document, and serializes it to XML — so that `pgb`, the
only consumer, can parse the XML back into the numbers the layout already held in memory.

| measured | |
| --- | ---: |
| of the render's retained memory is the jsdom document | **93.7%** |
| of every response carries no information | **41-47%** |
| empty `<title>` elements in one 13.56 MB document | **40,716** |
| fixed per-request cost to boot Node and jsdom | **722 ms** |

## The dependency graph

```
#14 test runner + CI ──┬── #17 endpoint seam ──── #20 threadpool
                       │
                       ├── #18 golden test ──┬── #21 capture ── #22 delete jsdom
                       │                     │                        │
                       │                     │                        └── #23 floats ── #24 ?format=bands ── #25 contract test
                       │                     │
                       │                     └── #26 delete vg ── #27 no disk
                       │
                       └── #19 lazy tabix

#15 declare the fork ──────── #21
#16 timings + fixtures ────── #26          (ready-for-human)
```

**The frontier is [#14](https://github.com/CAST-genomics/PangenomeAPI/issues/14),
[#15](https://github.com/CAST-genomics/PangenomeAPI/issues/15),
[#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16)** — three independent starts.
Edges are GitHub's native issue dependencies, so a ticket whose blockers are all closed is
grabbable without consulting this document.

---

## Phase 0 — Foundation

Nothing can be asserted until something can run assertions. **This repository has no tests
and no CI**: no test files, no runner configuration, no workflows. Every seam below is a new
seam.

### [#14](https://github.com/CAST-genomics/PangenomeAPI/issues/14) — Test runner and CI

A Python runner, a Node runner, a workflow running both on every pull request, and one smoke
test per runner proving the setup works end to end. CI also carries the `vg` binary, because
the endpoint seam needs it until [#26](https://github.com/CAST-genomics/PangenomeAPI/issues/26)
removes it; tests needing `vg` skip with a stated reason when it is absent, so the suite
stays runnable on a machine that has none.

Prefactoring. Make the change easy, then make the easy change.

### [#15](https://github.com/CAST-genomics/PangenomeAPI/issues/15) — Declare the fork

`seqtubemap/tubemap.js` is an unmarked ~4,000-line vendored copy of
`vgteam/sequenceTubeMap`, carrying upstream's eslint header and no provenance, version, or
note. [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22) removes its DOM sink, so
the re-sync option is gone in fact; a header comment makes it gone on paper. Land it before
anyone edits the file.

### [#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16) — Timings and fixtures *(human)*

Two artifacts off one deploy: stage timings for three uncached regions, and the pipeline
intermediates for the five regions `pgb` already holds golden outputs for. The full request
is in [`deploy-request.md`](./perf/deploy-request.md).

Start it now — it is a conversation with a colleague, and it gates
[#26](https://github.com/CAST-genomics/PangenomeAPI/issues/26) only.

---

## The two seams

Everything below tests at one of two places. The ideal is one; two is the honest count,
because the work spans two runtimes and one increment is invisible below HTTP.

**Seam 1 — the Node stage CLI.** Graph JSON in, document out, across a process boundary that
already exists. Increments **B** and **C** live entirely here. No Python, no `vg`, no graph
data, so it runs anywhere. `perf/` is the prior art for driving it.
Established by [#18](https://github.com/CAST-genomics/PangenomeAPI/issues/18).

**Seam 2 — the HTTP endpoint**, via the framework's test client. Increment **A** lives here
and nowhere else: *a slow request no longer stalls a concurrent one* is a statement about the
event loop that cannot be observed lower down. **D** also lands here.
Established by [#17](https://github.com/CAST-genomics/PangenomeAPI/issues/17).

Seam 2 runs with **no graph data at all**, by exploiting an existing production branch: the
pipeline already skips extraction when the subgraph is present, so a golden subgraph
pre-placed at that path stands in for a multi-gigabyte `.gbz`. An existing code path, not a
test hook.

**What makes a good test here.** Assert what a consumer can observe: the bytes of a response,
the floats a parser recovers, whether a second request completes while a first is in flight.
Never assert on intermediate data structures, internal function names, or the presence of
temp files — every one of those is something an increment is *expected* to change. The
strongest available assertion is **parser-equivalence**: run the client's own parser over
before and after, and diff the recovered arrays.

---

## Increment A — stop one request taking the server down

Highest priority, smallest diff, and it improves `/json` for free — which also makes it the
easiest thing in the programme for a reviewer to say yes to.

### [#17](https://github.com/CAST-genomics/PangenomeAPI/issues/17) — Endpoint seam

The tracer bullet for Seam 2: request a small region with no graph data present, get a real
document back, assert it contains bands and segment boxes rather than merely that bytes
arrived.

### [#20](https://github.com/CAST-genomics/PangenomeAPI/issues/20) — Threadpool

**The fix is deleting the word `async` twice** (`main.py:470`, `:527`). Neither endpoint
awaits anything; FastAPI runs a plain `def` endpoint in a threadpool automatically. The
ticket exists for the *test* — issue a slow request and a fast one concurrently, assert the
fast one does not wait.

### [#19](https://github.com/CAST-genomics/PangenomeAPI/issues/19) — Lazy tabix opens

Done. The `.walk.gz` derivatives used to be opened at module scope, so the app could not boot
unless all of them were present — even for a request touching none of them. They are
team-generated files, not public downloads, which made this the first wall anyone hit trying
to run the server. Each is now opened the first time something reads it (`WalkDerivative` in
`main.py`), once per process, and a missing one is a 503 naming the file and what wanted it.

---

## Increment B — delete the browser

Where the ceiling moves. This is the increment that makes large nodes *fetchable*, not merely
faster.

### [#21](https://github.com/CAST-genomics/PangenomeAPI/issues/21) — Capture

The expand half. At `tubemap.js:3599` the geometry is bound as `(d) => d.path` — **already a
finished string, before any element exists**. jsdom's entire contribution is to hold it and
hand it back. Make that data reachable; keep building the document exactly as before.

Deliberately not demoable on its own. Its acceptance criterion is *the golden test passes with
no re-baselining* — the only meaningful thing to assert about a change that changes nothing.

### [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22) — Delete jsdom

The contract half, and the payoff: **~15× on the ceiling, −722 ms fixed, −16.6% bytes**, and
`jsdom` and `canvas` — two of five dependencies — gone.

**Held byte-compatible with `pgb`'s existing parser as a deliberate constraint.**
`parseBands.ts` requires `style="fill: rgb(R, G, B); fill-opacity: 1;" trackID="N"
trackName="…"` contiguous and in that order, and counts `<rect>` + `<path>` in `g.track`.
What may go, because the client ignores all of it: `color=` (duplicating the rgb already in
`style=`), `class="track{id}"` (duplicating `trackID`), and the empty `<title>` on every band.

So **this ships against an unchanged `pgb`**, and the frontend becomes its conformance test
in production: a bad deploy surfaces as an error card, not as a diff nobody ran.

> **If the compatibility constraint cannot be held, stop and escalate.** Do not work around
> it. The no-client-change property is the entire reason B is safe to ship alone.

---

## Increment C — publish the numbers

### [#23](https://github.com/CAST-genomics/PangenomeAPI/issues/23) — Floats, not strings

Internal representation only; documents stay byte-identical. Every one of **127,101 of
127,101** surveyed strand paths conforms to a single grammar at constant thickness 15, so six
values plus a strand id describe a band completely. Measured, not assumed — the survey is in
`pgb`'s ADR 0002.

### [#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24) — `?format=bands`

JSON header (viewBox + the ~464-row strand table) plus a binary body of `Float32 × 6 +
Uint16` per band, with segment boxes carrying id, outline and sequence. Per-strand values
appear **once** instead of once per band, and a fixed-width body copies straight into `pgb`'s
GPU instance buffer with no parse at all.

**Additive.** Omit the parameter and you get today's response, byte for byte. The two repos
never deploy in lockstep, and the SVG stays as the oracle.

> Projected at ~1.5 MB against 10.07 MB — **arithmetic from the band count and record width,
> not a measurement.** The ticket asks for the real figure. It is the one number in these
> documents that is not a direct observation.

### [#25](https://github.com/CAST-genomics/PangenomeAPI/issues/25) — Contract test

Golden fixtures committed here; the test that parses them lives in `pgb`, where the parser
lives, and runs in `pgb`'s CI. **Not a vendored copy of the parser** — two copies that must
agree is precisely the failure mode this whole effort exists to remove.

---

## Increment D — delete the `vg` round trip

**Do not start [#26](https://github.com/CAST-genomics/PangenomeAPI/issues/26) until
[#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16) reports.** It sits *upstream*
of layout, untouched by A-C, and if `subgraph_extract` dominates the request it is not worth
doing at all. The measurement decides.

### [#26](https://github.com/CAST-genomics/PangenomeAPI/issues/26) — Graph JSON in-process

`GFA → protobuf → JSON` exists only to change format between two processes this project
controls: two subprocess spawns, two temp files, and a **13×** inflation (3.9 B per segment
visit as a GFA walk, 51.0 B as vg JSON). The target shape is small and the source already
contains it.

Success is *demonstrated*, not asserted: the Seam 1 golden tests pass with `vg` uninstalled.

### [#27](https://github.com/CAST-genomics/PangenomeAPI/issues/27) — No disk round trip

Stages pass bytes rather than filenames; the response stops being written to disk purely to
be read back. **The subgraph cache stays** — it is a deliberate optimisation, it is what makes
a repeated region fast, and Seam 2 depends on it to run without graph data.

---

## Closed — do not reopen

Each of these cost a grilling round. Reopening costs another.

**Result caching.** Retrievals are near-random: a scientist loads a graph and pokes arbitrary
nodes with no intent to repeat one. Settled on access patterns, not technology.

**Haplotype collapsing.** The ~464 strands are fixed input, not a variable. Nothing here
reduces cost by merging or dropping strands, regardless of how much time it would save.

**Fixing `pathnumoption=compressed`.** Real defect — it keys on the entire walk across the
region, so one SNP prevents any collapse, and it is measurably byte-identical to `normal`. But
fixing it *merges strands*, which is a data change and out of scope. It stays as-is on the SVG
route and does not exist on the band route; ADR 0001 records why.

**Replacing SVG, or mutating the existing URL in place.** Both force lockstep deploys and
both discard the oracle. See ADR 0001's rejected alternatives.

**Changing the layout algorithm, or recolouring.** Geometry in equals geometry out. Colour is
shared vocabulary with the PCLAI chart and the 3D graph.

---

## Still open

- **Does `subgraph_extract` dominate?** The last inferred number in the effort. Gates
  [#26](https://github.com/CAST-genomics/PangenomeAPI/issues/26) alone — A, B and C are
  correct wherever that time lives.
- **Does anything depend on the intermediate `.gfa` / `.vg` / `.json` files existing on
  disk?** They are deleted after every response, which suggests purely internal. Confirm with
  Cici before [#27](https://github.com/CAST-genomics/PangenomeAPI/issues/27).
- **Two documents in `pgb` make a forward claim** — that
  [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22) ships byte-compatible. Verified
  against the real regex and the real conformance gate, but describing code that does not exist
  yet. If #22 cannot hold the constraint, those amendments need correcting rather than quietly
  going stale. They live on `docs/tubemap-upstream-band-format` in `pgb`, unmerged.

## Verifying the whole thing

Against the baseline in [`seqtubemap-latency.md`](./perf/seqtubemap-latency.md) §1 — same
regions, same parameters:

| Region | TTFB before | Payload before |
| --- | ---: | ---: |
| 90 bp | 1.46 s | 178 KB |
| 3,000 bp | 35.33 s | 3.2 MB |
| 10,000 bp | 120.40 s | 10.1 MB |

```sh
node perf/bench.mjs --axis=spine
SPINES=40,150,600 HAPS=464 ALT=0.08 node perf/cross.mjs
python3 perf/gfa-rewrite-bench.py
node --expose-gc --max-old-space-size=8192 perf/rss-split.mjs \
  perf/fixtures/split-400.json 0 8000 compressed
```

`rss-split.mjs` is the one that matters after [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22):
it should report the DOM share at or near **zero**, because there should no longer be a DOM.
Its `--expose-gc` requirement is not optional — retained-memory numbers taken without a forced
collection measure garbage rather than retention.

Then update the rendered report **by passing its URL**
(`https://claude.ai/code/artifact/71539dd1-fb13-44d0-8468-a3a96e726114`); publishing without it
forks the link into a second artifact.
