# `/seqtubemap` rework — the roadmap

The execution sequence for the `/seqtubemap` plumbing work: eighteen tickets, what each
delivers, what gates it, and what has to be true before it is called done.

This is the **build** document. Its companions:

| | |
| --- | --- |
| [`CONTEXT.md`](../CONTEXT.md) | the vocabulary — **strand**, **segment**, **band**, **node** |
| [`docs/adr/0001`](./adr/0001-additive-band-format.md) | the decision, and the alternatives that were rejected |
| [`docs/perf/seqtubemap-latency.md`](./perf/seqtubemap-latency.md) | the measurements, §1-9 |
| [`docs/adr/0002`](./adr/0002-when-the-server-is-stood-up.md) | when the server gets stood up, and when it does not |
| [`docs/perf/seqtubemap-plan.md`](./perf/seqtubemap-plan.md) | which skill drives each phase |
| [`docs/releasing.md`](./releasing.md) | why merging is not shipping |
| [`docs/perf/deploy-request.md`](./perf/deploy-request.md) | the ask that unblocked [#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16) — a record now, not a procedure |
| [`tests/fixtures/seqtubemap/README.md`](../tests/fixtures/seqtubemap/README.md) | the five real subgraphs, and what they do and do not pin |
| [#13](https://github.com/CAST-genomics/PangenomeAPI/issues/13) | the spec these tickets decompose |

Written 2026-08-27 at the end of the grilling and ticketing phase; updated 2026-08-28, twice
— the second time after a grilling session on [#41](https://github.com/CAST-genomics/PangenomeAPI/issues/41)
measured its premises and found them false. That re-sequenced the coverage work ahead of
[#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22) and added two tickets; see
*Before #22*.

## Where this stands

Phase 0 and increment **A** are merged. **B** is half done.

| | |
| --- | --- |
| Merged | [#14](https://github.com/CAST-genomics/PangenomeAPI/issues/14), [#15](https://github.com/CAST-genomics/PangenomeAPI/issues/15), [#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16), [#17](https://github.com/CAST-genomics/PangenomeAPI/issues/17), [#18](https://github.com/CAST-genomics/PangenomeAPI/issues/18), [#19](https://github.com/CAST-genomics/PangenomeAPI/issues/19), [#20](https://github.com/CAST-genomics/PangenomeAPI/issues/20), [#21](https://github.com/CAST-genomics/PangenomeAPI/issues/21) |
| On `fix/reorder-tracks-pivot-strand`, not yet merged | [#46](https://github.com/CAST-genomics/PangenomeAPI/issues/46), [#41](https://github.com/CAST-genomics/PangenomeAPI/issues/41) |
| Frontier | **[#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22)** — its only blocker, #21, is closed |
| Live | **Nothing.** The server follows `release`, so merging is not shipping; `git log release..main` is what is waiting |
| Coverage gaps worth closing first | [#40](https://github.com/CAST-genomics/PangenomeAPI/issues/40) *(agent)* — see *Before #22* below |
| Housekeeping, unblocked, no document changes | [#45](https://github.com/CAST-genomics/PangenomeAPI/issues/45) *(agent)* |

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
#14 test runner + CI ✅─┬── #17 endpoint seam ✅── #20 threadpool ✅
                        │
                        ├── #18 golden test ✅─┬── #21 capture ✅── #22 delete jsdom ◀── HERE
                        │                      │                         │
                        │                      │                         └── #23 floats ── #24 ?format=bands ── #25 contract test
                        │                      │
                        │                      ├── #40 pclai golden        (ready-for-agent)
                        │                      │
                        │                      ├── #46 fix the reorder ── #41 fetch-ceiling band data
                        │                      │   (ready-for-human)       (ready-for-agent)
                        │                      │
                        │                      └── #26 delete vg ── #27 no disk
                        │
                        └── #19 lazy tabix ✅

#15 declare the fork ✅────── #21
#16 timings + fixtures ✅──── #26
#45 strip the debug logging — unblocked, touches no document
#E  batch GenerateWalksMC — no ticket yet, no ADR behind it
```

**The frontier is [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22)**, and nothing blocks it. Edges are GitHub's native issue
dependencies, so a ticket whose blockers are all closed is grabbable without consulting this
document — which is why the coverage tickets hanging off #18 are worth reading before
grabbing #22 rather than after.

**[#46](https://github.com/CAST-genomics/PangenomeAPI/issues/46) is also unblocked, and it is the one to take first.** It is not on #22's
critical path, but it changes the arrangement of every real document the server produces, so
anything baselined before it lands is baselined against a layout that is about to move. #41
is blocked on it for exactly that reason.

---

## Phase 0 — Foundation

**Done — all three.** Nothing could be asserted until something could run assertions, and
when this was written the repository had no tests, no runner configuration and no workflows.
It now has two suites and CI that runs both on every pull request.

### [#14](https://github.com/CAST-genomics/PangenomeAPI/issues/14) — Test runner and CI ✅

A Python runner, a Node runner, a workflow running both on every pull request, and one smoke
test per runner proving the setup works end to end. CI also carries the `vg` binary, because
the endpoint seam needs it until [#26](https://github.com/CAST-genomics/PangenomeAPI/issues/26)
removes it; tests needing `vg` skip with a stated reason when it is absent, so the suite
stays runnable on a machine that has none.

Prefactoring. Make the change easy, then make the easy change.

### [#15](https://github.com/CAST-genomics/PangenomeAPI/issues/15) — Declare the fork ✅

`seqtubemap/tubemap.js` is an unmarked ~4,000-line vendored copy of
`vgteam/sequenceTubeMap`, carrying upstream's eslint header and no provenance, version, or
note. [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22) removes its DOM sink, so
the re-sync option is gone in fact; a header comment makes it gone on paper. Land it before
anyone edits the file.

### [#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16) — Timings and fixtures ✅ *(human)*

Two artifacts off one deploy: stage timings for three uncached regions, and the pipeline
intermediates for the five regions `pgb` already holds golden outputs for. The full request
is in [`deploy-request.md`](./perf/deploy-request.md).

**It reported, and it re-ranked the roadmap.** `subgraph_extract` is **77% of a 10 kb
request** — but the cost is `GenerateWalksMC`'s per-node tabix loop, not `gbz-base`, whose own
query prints 0.042 s. The `vg` round trip is **1.6%**, which demotes increment D out of
performance entirely and adds **E** below. `generate_svg` also turned out larger than
estimated: 8.2 s at 10 kb, and 91 s of a 93.6 s *cached* 35.9 kb request, which strengthens B
and C rather than weakening them.

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

### [#17](https://github.com/CAST-genomics/PangenomeAPI/issues/17) — Endpoint seam ✅

The tracer bullet for Seam 2: request a small region with no graph data present, get a real
document back, assert it contains bands and segment boxes rather than merely that bytes
arrived.

### [#20](https://github.com/CAST-genomics/PangenomeAPI/issues/20) — Threadpool ✅

**The fix was deleting the word `async` twice.** Neither endpoint awaits anything; FastAPI
runs a plain `def` endpoint in a threadpool automatically. The ticket existed for the *test* —
issue a slow request and a fast one concurrently, assert the fast one does not wait. Merged,
and **not yet live**: it is in `release..main` with everything else.

### [#19](https://github.com/CAST-genomics/PangenomeAPI/issues/19) — Lazy tabix opens ✅

Done. The `.walk.gz` derivatives used to be opened at module scope, so the app could not boot
unless all of them were present — even for a request touching none of them. They are
team-generated files, not public downloads, which made this the first wall anyone hit trying
to run the server. Each is now opened the first time something reads it (`WalkDerivative` in
`main.py`), once per process, and a missing one is a 503 naming the file and what wanted it.

---

## Increment B — delete the browser

Where the ceiling moves. This is the increment that makes large nodes *fetchable*, not merely
faster.

### [#21](https://github.com/CAST-genomics/PangenomeAPI/issues/21) — Capture ✅

The expand half. At `tubemap.js:3599` the geometry is bound as `(d) => d.path` — **already a
finished string, before any element exists**. jsdom's entire contribution is to hold it and
hand it back. Make that data reachable; keep building the document exactly as before.

Deliberately not demoable on its own. Its acceptance criterion was *the golden test passes with
no re-baselining* — the only meaningful thing to assert about a change that changes nothing.
Delivered as `getBandData()` plus `seqtubemap/band-data.mjs`, with sufficiency *demonstrated*:
`tests/node/reconstruct-document.mjs` rebuilds the document from the band data alone and is
compared byte for byte, including against a real 464-strand subgraph.

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

### Before #22 — what the left-hand side of the diff actually covers

#22 re-baselines the golden documents deliberately, and its acceptance criterion is that
**the diff is only those three removals**. That is a claim about a diff, so it is worth
asking what the left-hand side covers before making it — because a golden created *after* the
change cannot police the change, and after B nothing else in the repository pins output
against what the jsdom pipeline produced.

The answer, as of 2026-08-28: less than it looks. The committed goldens are synthetic, and
they pass byte-identically **through a change that reorders every strand in the picture** —
which is how #46 sat undetected. They cover the mechanism; they do not cover the regime.

Three gaps, all ticketed — and the order among them matters, because one of them moves the
documents the other two would baseline.

- **[#46](https://github.com/CAST-genomics/PangenomeAPI/issues/46) — the reorder is wrong *(landed on `fix/reorder-tracks-pivot-strand`)*.**
  `reorderTracksForLayout` arrived in `0f69615` inside a commit about walk generation, with a
  three-point comment and a one-line body implementing one of the three. It decides which
  strand is the **pivot strand** — `createTubeMap` straightens `tracks[0]` and orients
  everything else against it — and today that is decided by a stable-sort tiebreak on
  sequence length. Measured: CHM13 lands at index **455 of 464** where the comment promises
  second, and GRCh38 leads only because it happens to tie for longest.

  It is human-labelled because it changes the arrangement of every real document the server
  emits. It does *not* re-baseline the synthetic goldens — those pass byte-identically either
  way, which is a useful signal about how little of the real regime they cover.

- **[#40](https://github.com/CAST-genomics/PangenomeAPI/issues/40) — PCLAI colour scheme *(ready-for-agent)*.** Every committed golden invokes
  the five-argument form of the generator, so the colour scheme branch — live in production
  whenever `minigraphnode` is set — produces output nothing pins. #21 added band-data coverage
  for it, not a golden document. Small, mechanical, and it closes a real hole under B.

- **[#41](https://github.com/CAST-genomics/PangenomeAPI/issues/41) — the fetch-ceiling regime *(landed on `fix/reorder-tracks-pivot-strand`)*.** The two
  skipped cases in `generate-svg.golden.test.mjs` wanted the regime that actually fails to be
  the regime under test. **This ticket was rewritten on 2026-08-28**; the version that asked
  for a naming decision, server access and a 12 MB commit rested on two claims that were then
  measured and found false.

  What the measurement found: the committed 90 bp `.gfa` reproduces `pgb`'s golden **exactly**
  — 291 paths, 726 rects, identical viewBox, identical strand names — once the #46 reorder is
  taken out, which was added after that golden was captured. The naming difference across the
  five goldens is `vg`'s own spelling (`sample#hap#contig#phaseblock`, plus a subrange for a
  partial walk) seen at three different dates, not a convention anyone chose. Only two
  fixtures genuinely mismatch, and it is the walk count that says so: 383 walks for 378
  strands, and 1,201 for 464, against goldens from before `0f69615` allowed multiple walks per
  assembly.

  So the pin is **self-baselined band data in this repository**, which is what ADR 0001 makes
  canonical anyway — no server access, no 12 MB, and no decision left to make. The full
  measurement is in `tests/fixtures/seqtubemap/README.md` and in the comment on the issue.

  What landed: `tests/node/real-subgraph.band.test.mjs` renders all five real subgraphs,
  compares their band data to `<name>.band.json.gz` baselines beside each subgraph, and
  rebuilds each document from the committed baseline in full — 15.81 MB of XML for the
  largest, accounted for byte by byte. The skip mechanism is gone. Each fixture also gained a
  `.pclai.json`, so the real subgraphs are rendered with all three of a real request's
  inputs: the PCLAI colour scheme each region was rendered with turned out to be recoverable
  from `pgb`'s goldens, where the generator writes every entry onto the elements it draws.

> **Do not reach for `perf/gfa-to-vg-json.mjs --names=bare`.** The old #41 offered it as the
> lever for "restoring the older naming convention". On the 90 bp fixture the suffixed names
> are the ones that match `pgb`'s golden character for character, so it would break a pair
> that already works.

`pgb`'s five goldens are not this repository's oracle and never were captured as one. They
pin `pgb`'s parser, which is the job they were built for. What crosses the boundary is
[#25](https://github.com/CAST-genomics/PangenomeAPI/issues/25)'s contract test.

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

**The measurement reported, and it demoted this.** `gfa_to_vg` + `vg_to_json` is **0.63 s of a
38.9 s request — 1.6%**. D is no longer a performance item and should not be sold as one. The
standing case survives on its own terms, none of which are latency: two subprocess spawns, two
temp files, a **13×** intermediate inflation, and a `vg` binary that CI and every developer
machine has to carry. Do it when the provisioning cost is worth paying down, not for speed.

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

## Increment E — where the time actually is

**No ticket yet, and no ADR behind it.** It comes from Step 0's numbers rather than from the
grilling, and it is the largest single cost in the pipeline: `GenerateWalksMC` is a Python
loop doing one tabix `fetch` per node across 464 strands, at a flat **65-79 ms per node**, and
it is most of `subgraph_extract`'s 30.1 s of a 38.9 s request.

The open question is whether that per-node fetch can be batched. It is the difference between
E being a half-day and a rewrite, and nothing else is blocked on the answer — A, B and C are
correct wherever the upstream time lives.

---

## Housekeeping — not an increment

### [#45](https://github.com/CAST-genomics/PangenomeAPI/issues/45) — Strip the debug instrumentation *(ready-for-agent)*

`0f69615` left debugging aids in the render path and they still run on every request: a
`setInterval` memory logger in `generate-svg.mjs`, a `tracks[0].name` line in `render.mjs`,
and a `t(label)` stage timer calling `process.memoryUsage()` at ~20 points through
`createTubeMap`. `main.py` pipes the child's stderr into the server log, so all of it reaches
production.

The `[stage-timing]` line from [#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16)
already does this job properly, in one line per request, from the Python side. And
`process.memoryUsage()` is a Node global in a file that is a declared fork of a *browser*
library.

Unblocked, touches no document, and `npm test` must stay byte-identical through it — if a
golden moves, something else went with it.

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

- ~~**Does `subgraph_extract` dominate?**~~ **Answered 2026-08-27: yes, 77%** — and the cost
  is `GenerateWalksMC`, not `gbz-base` and not the `vg` round trip. See increment E.
- **Can `GenerateWalksMC`'s per-node tabix fetch be batched?** The question that now most
  changes the plan.
- **Does anything depend on the intermediate `.gfa` / `.vg` / `.json` files existing on
  disk?** They are deleted after every response, which suggests purely internal. Confirm with
  Cici before [#27](https://github.com/CAST-genomics/PangenomeAPI/issues/27).
- **Does `perf/gfa-to-vg-json.mjs` agree with real `vg view -j`?** It is now known *not* to,
  in at least one way: `vg` appends a subrange to a path covering part of a contig
  (`CHM13#0#chr8#0[9659985-9661740]` in `pgb`'s 1.4 kb golden) and the shim never does. The
  `.gfa` is the source of truth and the shim is this repository's own derivation from it, so
  baselines taken through it pin the layout but say nothing about the wire. Confirming it
  needs somebody who can run `vg`, and it wants its own ticket.
- **Does a reference strand lose its PCLAI colour in a subrange region?** `truncateTrackName`
  keeps the first three `#`-fields, so a three-field name carrying a subrange —
  `GRCh38#0#chr8[10078919-10080674]` — passes through with the bracket attached, and
  `getPclaiEntry` uses it as the scheme lookup key. Found while measuring #46, not confirmed
  against a live scheme.
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
