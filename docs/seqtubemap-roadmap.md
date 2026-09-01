# `/seqtubemap` rework — the roadmap

The execution sequence for the `/seqtubemap` plumbing work: eighteen planned tickets and
three defects found along the way — what each delivers, what gates it, and what has to be
true before it is called done.

This is the **build** document. Its companions:

| | |
| --- | --- |
| [`CONTEXT.md`](../CONTEXT.md) | the vocabulary — **strand**, **segment**, **band**, **node** |
| [`docs/adr/0001`](./adr/0001-additive-band-format.md) | the decision, and the alternatives that were rejected |
| [`docs/perf/seqtubemap-latency.md`](./perf/seqtubemap-latency.md) | the measurements, §1-9 |
| [`docs/perf/increment-b.md`](./perf/increment-b.md) | what **B** actually bought, before and after |
| [`docs/perf/local-endpoint-harness.md`](./perf/local-endpoint-harness.md) | how to drive `/seqtubemap` on a machine with no graph data and no `vg` |
| [`docs/adr/0002`](./adr/0002-when-the-server-is-stood-up.md) | when the server gets stood up, and when it does not |
| [`docs/perf/seqtubemap-plan.md`](./perf/seqtubemap-plan.md) | which skill drives each phase |
| [`docs/releasing.md`](./releasing.md) | why merging is not shipping |
| [`docs/tube-map-pipeline.html`](./tube-map-pipeline.html) | the whole rework in one illustrated page — the two ways to draw a tube map |
| [`tests/fixtures/seqtubemap/README.md`](../tests/fixtures/seqtubemap/README.md) | the five real subgraphs, and what they do and do not pin |
| [#13](https://github.com/CAST-genomics/PangenomeAPI/issues/13) | the spec these tickets decompose |

Written 2026-08-27 at the end of the grilling and ticketing phase; revised through
2026-08-28, the substantive revision being a grilling session on
[#41](https://github.com/CAST-genomics/PangenomeAPI/issues/41) that measured its premises and
found them false. That re-sequenced the coverage work ahead of
[#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22) and added two tickets — all
three of which have since merged; see *Before #22*. Revised again 2026-09-01, after the
live trial of increment **B** on 2026-08-31 and the merge of
[#23](https://github.com/CAST-genomics/PangenomeAPI/issues/23) and
[#45](https://github.com/CAST-genomics/PangenomeAPI/issues/45).

## Where this stands

Phase 0, increment **A**, increment **B** and the first half of **C** are merged. The browser
emulation is gone: the document is written from the layout's own numbers, `jsdom` and `canvas`
have left the dependency tree, and the ceiling moved — a region that died with `heap out of
memory` at a 1 GB heap now renders in under a second. The figures are in
[`increment-b.md`](./perf/increment-b.md). Since #23 the geometry is carried as numbers rather
than as a drawing command, so what remains of **C** is the wire format itself.

**B has been tried on the real server.** On 2026-08-31 Cici pointed the live server at `main`
for a short while and `pgb` drew against it: regions that used to exceed the frontend's 90 s timeout and never return now
retrieve. Two defects surfaced during the trial and both were fixed inside it — see *The live
trial*. The server has since been put back on `release`.

| | |
| --- | --- |
| Merged | [#14](https://github.com/CAST-genomics/PangenomeAPI/issues/14), [#15](https://github.com/CAST-genomics/PangenomeAPI/issues/15), [#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16), [#17](https://github.com/CAST-genomics/PangenomeAPI/issues/17), [#18](https://github.com/CAST-genomics/PangenomeAPI/issues/18), [#19](https://github.com/CAST-genomics/PangenomeAPI/issues/19), [#20](https://github.com/CAST-genomics/PangenomeAPI/issues/20), [#21](https://github.com/CAST-genomics/PangenomeAPI/issues/21), [#46](https://github.com/CAST-genomics/PangenomeAPI/issues/46), [#41](https://github.com/CAST-genomics/PangenomeAPI/issues/41), [#40](https://github.com/CAST-genomics/PangenomeAPI/issues/40), [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22), [#45](https://github.com/CAST-genomics/PangenomeAPI/issues/45), [#23](https://github.com/CAST-genomics/PangenomeAPI/issues/23) |
| Frontier | **[#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24)** — increment C's wire format, unblocked by #23 |
| Live | **Nothing.** The server follows `release`, so merging is not shipping; `git log release..main` — 59 commits — is what is waiting. The trial was a loan, not a promotion |
| Defects, outside the increments | [#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52), [#54](https://github.com/CAST-genomics/PangenomeAPI/issues/54), [#58](https://github.com/CAST-genomics/PangenomeAPI/issues/58) — all still open, all triaged, none blocking #24 |

---

## The one-sentence version

**`/seqtubemap` publishes the numbers it already has, instead of emulating a browser to
hide them in XML.**

## Why

A researcher clicks a **minigraph node** to look inside it. Roughly 43% of the time nothing
appears. When it works, a 10 kb region takes 120 seconds and delivers 10 MB — and the
frontend gives up at 90, so for a large node the feature is simply unavailable, with no way
to tell in advance which nodes will work.

And the failure is not contained. Both endpoints were `async def` while every stage blocks,
so one slow tube map request stalled **every** other request to the server, including the
`/json` the 3D graph depends on. (Fixed on `main` by
[#20](https://github.com/CAST-genomics/PangenomeAPI/issues/20); still live on the server,
which follows `release`.)

One cause sits under all three symptoms. The server computes the geometry, then boots a
headless browser, builds a jsdom document, and serializes it to XML — so that `pgb`, the
only consumer, can parse the XML back into the numbers the layout already held in memory.

Those three symptoms are the three goals, in priority order: **(1) no request blocks
another, (2) the unfetchable-node ceiling rises, (3) wall-clock falls.** Every increment
below is ranked by which of them it wins. Bytes are a consequence of these, never a target
in themselves.

*Every row of this table is now past tense; [`increment-b.md`](./perf/increment-b.md) has
what each became.*

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
                        ├── #18 golden test ✅─┬── #21 capture ✅── #22 delete jsdom ✅
                        │                      │                         │
                        │                      │                         └── #23 floats ✅── #24 ?format=bands ◀── HERE ── #25 contract test
                        │                      │
                        │                      ├── #40 pclai golden ✅
                        │                      │
                        │                      ├── #46 fix the reorder ✅── #41 fetch-ceiling band data ✅
                        │                      │
                        │                      └── #26 delete vg ── #27 no disk
                        │
                        └── #19 lazy tabix ✅

#15 declare the fork ✅────── #21
#16 timings + fixtures ✅──── #26
#45 strip the debug logging ✅
#E  batch GenerateWalksMC — no ticket yet, no ADR behind it

Defects, off the sequence and blocking nothing:
#52 pgb refuses a reversal — #24 decides what a reversal means on the band route
#54 concurrent extraction of one uncached region — corruption half fixed in PR #60
#58 drop d3, and the dead read-track colouring that is its last user
```

**The frontier is [#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24)**, and nothing blocks it. Edges are GitHub's native issue
dependencies, so a ticket whose blockers are all closed is grabbable without consulting this
document.

The three coverage tickets hanging off #18 — #46, #41 and #40 — were worth closing before #22
re-baselined the goldens, and all three did; *Before #22* below records what each one added,
and is history rather than a queue. The housekeeping ticket,
[#45](https://github.com/CAST-genomics/PangenomeAPI/issues/45), has merged too — it ended up
smaller than it was written, since #22 took the `getComputedTextLength` patch and the DOM boot
out from under it.

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
intermediates for the five regions `pgb` already holds golden outputs for. Both came back
2026-08-27.

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

**B deliberately shipped band data carrying path strings, not six floats.** That takes the
entire ceiling win without touching a line of geometry code, and leaves **C** as a pure
encoding change with B's own output as its oracle. Splitting them that way is why #23 could
come out byte-identical.

### [#21](https://github.com/CAST-genomics/PangenomeAPI/issues/21) — Capture ✅

The expand half. As the file then stood — at `tubemap.js:3599`, before #22 and #23 rewrote
around it — the geometry was bound as `(d) => d.path`: **already a finished string, before any
element existed**. jsdom's entire contribution was to hold it and hand it back. Make that data
reachable; keep building the document exactly as before.

Deliberately not demoable on its own. Its acceptance criterion was *the golden test passes with
no re-baselining* — the only meaningful thing to assert about a change that changes nothing.
Delivered as `getBandData()` plus `seqtubemap/band-data.mjs`, with sufficiency *demonstrated*:
`tests/node/reconstruct-document.mjs` rebuilt the document from the band data alone and was
compared byte for byte, including against a real 464-strand subgraph. #22 promoted that file
to `seqtubemap/emit-document.mjs` and deleted the thing it was demonstrating against, so the
demonstration is now the implementation.

### [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22) — Delete jsdom ✅

The contract half, and the payoff. Every draw function now collects what it was about to
draw (`seqtubemap/band-data.mjs`) and `seqtubemap/emit-document.mjs` writes the document from
that. `jsdom`, `canvas` and `d3-selection-multi` — three of five dependencies — are gone, and so is the
`getComputedTextLength` they existed for: a monospace label's width is its glyph count times
one advance, which also makes `nodeWidthOption=normal` deterministic across machines for the
first time.

**Measured, on `perf/fixtures/split-400.json` and the committed fixtures — the full record is
[`increment-b.md`](./perf/increment-b.md):**

| | before | after |
| --- | ---: | ---: |
| retained by `create()` | 1,851.4 MB, 95.0% of it DOM | **94.9 MB, all of it layout** |
| peak RSS | 2,446.5 MB | **472.5 MB** |
| `cross.json` at production's own 8 GB heap | `heap out of memory`, 35.1 s | **renders, 6.4 s** |
| the smallest possible request, warm | 0.56 s | **0.13 s** |
| the 4.2 kb document | 15.81 MB | **13.19 MB** (−16.6%) |

The ceiling row is the one that matters: an input that could not be rendered at all now
renders, at the heap the server actually gives the generator (`main.py:618`).

**It held byte-compatible with `pgb`'s existing parser, which was the constraint.**
`parseBands.ts` requires `style="fill: rgb(R, G, B); fill-opacity: 1;" trackID="N"
trackName="…"` contiguous and in that order, and counts `<rect>` + `<path>` in `g.track`.
What went, because the client ignores all of it: `color=` (duplicating the rgb already in
`style=`), `class="track{id}"` (duplicating `trackID`), and the empty `<title>` on every
band. The diff was *shown* to be only those three: every golden and all five real subgraphs
matched their old bytes character for character with exactly those deleted — including
`nodeWidthOption=normal`, the one mode whose geometry could have moved, since it is what the
deleted `canvas` was measuring labels with. It now measures them arithmetically, which agrees
exactly on a host that resolves Courier New and is deterministic on one that does not; that
mode has its first golden, `small-normal.svg`, as a result.

So **this ships against an unchanged `pgb`**, and the frontend is its conformance test in
production: a bad deploy surfaces as an error card, not as a diff nobody ran. On this side
the same contract is written down in `tests/node/pgb-parser.mjs` and checked by
`tests/node/document-conformance.test.mjs`, including the drawable counts as they stood
before the increment.

### Before #22 — what the left-hand side of the diff actually covers

#22 re-baselines the golden documents deliberately, and its acceptance criterion is that
**the diff is only those three removals**. That is a claim about a diff, so it is worth
asking what the left-hand side covers before making it — because a golden created *after* the
change cannot police the change, and after B nothing else in the repository pins output
against what the jsdom pipeline produced.

The answer, when this was asked: less than it looks. The committed goldens were synthetic, and
they passed byte-identically **through a change that reorders every strand in the picture** —
which is how #46 sat undetected. They covered the mechanism; they did not cover the regime.

Three gaps, all ticketed, and the order among them mattered because one of them moved the
documents the other two would baseline. **All three have since merged**, in that order, so
what follows is the record of what the left-hand side now covers.

- **[#46](https://github.com/CAST-genomics/PangenomeAPI/issues/46) — the reorder is wrong *(merged, PR #47)*.**
  `reorderTracksForLayout` arrived in `0f69615` inside a commit about walk generation, with a
  three-point comment and a one-line body implementing one of the three. It decides which
  strand is the **pivot strand** — `createTubeMap` straightens `tracks[0]` and orients
  everything else against it — and that was being decided by a stable-sort tiebreak on
  sequence length. Measured: CHM13 landed at index **455 of 464** where the comment promised
  second, and GRCh38 led only because it happened to tie for longest.

  What landed: GRCh38's walks first and CHM13's second, by group rather than by index, since a
  reference contig can itself be fragmented; all walks of one strand together, keyed on the
  `sample#haplotype#contig` triple with `vg`'s phase-block and subrange tail stripped; the rest
  longest first, every tie broken on something in the data. The same subgraph now lays out
  identically however `vg` emitted it. `assertDenseStrandIds` came with it, turning `pgb`'s
  dense-`trackID` requirement into an invariant checked on this side.

  **It cost shapes, and the numbers are the ones to baseline against.** Grouping plus a
  pivot-first constraint claw back most of what the length sort bought: the 4.2 kb fixture goes
  from 34,937 bands to 44,795, and the 1.4 kb from 11,586 to 13,246. Determinism was the point
  and a picture that does not move is worth the payload.

  It was human-labelled because it changes the arrangement of every real document the server
  emits. It did *not* re-baseline the synthetic goldens — those pass byte-identically either
  way, which is a useful signal about how little of the real regime they cover.

- **[#40](https://github.com/CAST-genomics/PangenomeAPI/issues/40) — PCLAI colour scheme *(merged, PR #44)*.** Every committed golden invoked
  the five-argument form of the generator, so the colour scheme branch — live in production
  whenever `minigraphnode` is set — produced output nothing pinned. #21 had added band-data
  coverage for it, not a golden document.

  What landed: a `small-pclai` case rendering `small`'s input through the six-argument form
  against `pclai-color-scheme.json`, pinned by `small-pclai.svg`. The scheme deliberately
  mixes strands carrying a colour with the grey no-coordinate entry, whose fill is the same
  grey as an uncoloured strand — so only the `pclaiX`/`pclaiY`/`pclaiScore` attributes tell
  them apart, which is exactly the distinction a byte comparison has to be able to see.

- **[#41](https://github.com/CAST-genomics/PangenomeAPI/issues/41) — the fetch-ceiling regime *(merged, PR #48)*.** The two
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
  largest at the time, 13.19 MB since #22, accounted for byte by byte. Both fetch-ceiling skips are gone — the one `skip` left
  in `generate-svg.golden.test.mjs` is #40's, on the `small-pclai` case, which shares `small`'s
  input and so has no seed of its own to regenerate. Each fixture also gained a
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

## The live trial — B on the real server, 2026-08-31

Increment B was tried where it has to work. Cici pointed the live server at `main`, we looked
at it together in `pgb`, and it went back on `release` afterwards. **The headline held:
regions that used to exceed the frontend's 90 s timeout and never return now retrieve.**

Two defects surfaced that nothing in this repository could have caught, and both were fixed
during the trial rather than filed:

- **Fractional colour channels (PR [#59](https://github.com/CAST-genomics/PangenomeAPI/pull/59)).** `pgb` refused the very first real region
  — `NonConformingDocument` on `chr7:55134330`, 6 of 1,626 drawables unmatched, and its gate
  refuses the *whole* document, so nothing drew. The channels come out of the walks file as
  floats, and jsdom's CSS serializer had been rounding them all along: `rgb(0, 228.5, 178.5)`
  went out as `rgb(0, 229, 179)`. #22 deleted the emulation and with it a rounding step nobody
  knew was load-bearing. `cssColor` now rounds and clamps itself, half away from zero. No
  committed scheme holds a fractional channel, which is why every golden missed it; a
  conformance test now shifts a real subgraph's scheme half a step off every channel.

- **One wedged request breaking every uncached region (PR [#60](https://github.com/CAST-genomics/PangenomeAPI/pull/60)).** A 40 kb region
  was abandoned mid-flight from the browser, and from then on *every* uncached region returned
  500 in 0.3 s while every cached one served normally. Three defects stacked: a shared
  `pysam.TabixFile` handle read from the threadpool — reachable only after #20 moved handlers
  off the event loop, which is the edge that change exposed, now one handle per thread via
  `threading.local`; a failed extraction that cached itself, since `GenerateWalksMC` writes its
  `W` lines last and `subgraph_cached` asked only `exists()` — extraction now writes under a
  temporary name and `os.replace`s into place, and a cache hit means a subgraph with at least
  one `W` line, which also clears the poisoned entries already on disk; and three stages that
  returned a boolean nobody read, so the failure surfaced as `FileResponse` raising over a file
  no stage ever wrote — a failing stage now raises a 502 naming itself and the region, through
  the CORS middleware, so the panel can show the reason.

**A trial is not a promotion.** The server is back on `release`, and `release..main` is still
what is waiting. [`releasing.md`](./releasing.md) is the procedure.

---

## Increment C — publish the numbers

### [#23](https://github.com/CAST-genomics/PangenomeAPI/issues/23) — Floats, not strings ✅

Internal representation only; documents stayed byte-identical. Every one of **127,101 of
127,101** surveyed strand paths conforms to a single grammar at constant thickness 15, so six
values plus a strand id describe a band completely. Measured, not assumed — the survey is in
`pgb`'s ADR 0002.

**What landed.** The layout no longer builds a `d` string anywhere: `band-data.mjs` carries
`x0, y0, x1, y1` and the two control abscissae plus a strand index, and
`emit-document.mjs` is now the one place a band becomes a drawing at all. A `<rect>` is the
degenerate case storing the same six values `pgb` fills in for one, not a second shape with
its own fields. **The thickness is said once**, not on each of 55,053 bands — and a band of
any other thickness throws where the layout that drew it is still in scope, as does a width
that would not survive being written down and read back.

All four goldens, all five real subgraphs and the synthetic reversal came out byte-identical,
so the golden tests took no re-baselining; the band-data baselines *were* re-baselined
deliberately, because they are what pins the representation that changed, and they shrank from
2.33 MB to 1.87 MB gzipped. `tests/node/band-geometry.test.mjs` carries the claim that
matters — that the numbers `pgb` recovers from each emitted document are, to the bit, the
numbers the layout held. Exact equality, not a tolerance.

A reversal's **corners** (quadratics, no `trackName`) and its **vertical connectors** are
outside the six-value grammar and are collected as their own kinds rather than forced into it.
`pgb` can read neither today — that is [#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52), which predates this — and #24 is where
what they mean on the band route gets decided.

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

## Defects — off the sequence

Three, all found by reading or by running rather than by planning. None blocks the increments,
and none is scheduled; each is here so it is not rediscovered.

### [#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52) — a reversal draws shapes `pgb` refuses

`tubemap.js` can draw a **reversal** — corners and vertical rectangles for an inverted strand.
`pgb`'s `parseBands.ts` reads none of them, and its gate compares drawables counted against
drawables matched, so one unreadable shape refuses the *whole* document: an error card, not a
degraded picture. Off the grammar three independent ways — a corner carries no `trackName`,
is built from quadratics rather than cubics, and neither shape has ever painted a
`fill-opacity`.

Found 2026-08-28 while verifying #22 against `pgb`'s real parser. **It predates #22, and #22
moved it in neither direction.** #23 made the two shapes explicit kinds rather than bands with
impossible numbers, which is the groundwork; [#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24) is where what they mean on the
band route gets decided.

### [#54](https://github.com/CAST-genomics/PangenomeAPI/issues/54) — two requests extract the same uncached region at once

`subgraph_cached` used to ask `path.exists()`, so two requests for one uncached region could
both extract it over each other, and a third could read a half-written file as finished — and
the bad copy is *cached*, so the region stays broken until someone deletes it by hand.

**The corruption half is fixed**, in PR [#60](https://github.com/CAST-genomics/PangenomeAPI/pull/60) during the live trial, which is where
it stopped being a code reading and became an incident: extraction writes under a temporary
name and `os.replace`s into place, and a cache hit now means a subgraph with at least one `W`
line. What remains is the duplicated work — nothing serialises two requests for one region, so
both still pay the extraction. That is the ticket's option (2), a lock per region, and it is
correctness-neutral now.

### [#58](https://github.com/CAST-genomics/PangenomeAPI/issues/58) — drop `d3`

After B, `d3` has one live call site left in the repo — `d3.interpolateRdYlGn` at
`tubemap.js:2478`, since #45 moved the line — and it is unreachable in this pipeline: it sits
behind `track.type === "read"`, and `render.mjs:75` always passes `reads: null`. So the last user of a
31-package dependency is a feature this fork does not have. Upstream's read-track colour model,
not ours.

---

## Housekeeping — not an increment

### [#45](https://github.com/CAST-genomics/PangenomeAPI/issues/45) — Strip the debug instrumentation ✅

`0f69615` left debugging aids in the render path and they ran on every request: a
`setInterval` memory logger in `generate-svg.mjs`, a `tracks[0].name` line in `render.mjs`,
and a `t(label)` stage timer calling `process.memoryUsage()` at ~20 points through
`createTubeMap`. `main.py` pipes the child's stderr into the server log, so all of it reached
production.

The `[stage-timing]` line from [#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16)
already does this job properly, in one line per request, from the Python side. And
`process.memoryUsage()` is a Node global in a file that is a declared fork of a *browser*
library.

All three are gone. It touched no document, and `npm test` stayed byte-identical through it —
the constraint was that if a golden moved, something else went with it, and none did.

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
- ~~**Two documents in `pgb` make a forward claim**~~ — that #22 ships byte-compatible.
  **Answered: it held, and the amendments merged** as `pgb` PR #142. The forward claim is now a
  past-tense one, and the live trial exercised it against the real parser.
- **Does a reversal reach a real region?** #52 says `pgb` refuses any document containing one,
  and the live trial drew several regions without hitting it. Whether that is luck or whether
  reversals are rare in this graph decides how urgent #52 is, and nobody has counted.

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

`rss-split.mjs` was the one that mattered for [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22),
and it has reported: the DOM share is **zero**, because there is no longer a DOM, and peak RSS
on `split-400.json` fell from 2,446.5 MB to 472.5 MB. Its `--expose-gc` requirement is not
optional — retained-memory numbers taken without a forced collection measure garbage rather
than retention.

The TTFB and payload rows above are still *before* figures, and there are no *after* ones. The
live trial of 2026-08-31 was a look, not a measurement — it established that regions past the
90 s ceiling now return, which the rows cannot show, but no stage timings were captured while
`main` was up. They are server measurements, and the server is back on `release`; nothing in
this repository can move them until `release..main` is promoted.

Then update the rendered report **by passing its URL**
(`https://claude.ai/code/artifact/71539dd1-fb13-44d0-8468-a3a96e726114`); publishing without it
forks the link into a second artifact.
