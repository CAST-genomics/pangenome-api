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
| [`docs/band-format.md`](./band-format.md) | the wire format **C** publishes, in enough detail to write a parser against |
| [`docs/perf/increment-c.md`](./perf/increment-c.md) | what **C** actually bought, and the day `pgb` read it |
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
[#45](https://github.com/CAST-genomics/PangenomeAPI/issues/45). Revised again 2026-09-02,
when `pgb` read band payloads off the live server and the server stopped going back to
`release`.

## Where this stands

Phase 0 and increments **A**, **B** and **C** are merged — all of **C** that lives in this
repository, which is everything but the cross-repo contract test (#25). The browser emulation is gone: the
document is written from the layout's own numbers, `jsdom` and `canvas` have left the
dependency tree, and the ceiling moved — a region that died with `heap out of memory` at a
1 GB heap now renders in under a second. The figures are in
[`increment-b.md`](./perf/increment-b.md). Since #23 the geometry is carried as numbers rather
than as a drawing command, and since #24 those numbers are published:
`/seqtubemap?format=bands`, specified in [`band-format.md`](./band-format.md).

**And `pgb` reads them off the live server.** On 2026-09-02 the app retrieved band payloads
from the deployed API and drew from them — the first time the format has been exercised
anywhere but a test. That closed the loop **C** exists for: the server publishes the numbers
and the client consumes them, with no XML in between. The record is
[`increment-c.md`](./perf/increment-c.md).

**The server now runs `main`, and stays there.** The 2026-08-31 window was a loan; this is
not. `release` has stopped being the deployed branch and is now a lagging pointer at what
used to be live — see *What "live" means now*. Everything A, B and C bought is what a
researcher gets today, which is the first time that sentence has been true.

**Milestones carry tags.** `increment-b` marks the state at which the browser emulation was
gone and confirmed on the server; `increment-c` marks `f9b05f6`, the state `pgb` read band
payloads from. Both are annotated and both are on `origin`; `git tag -n99 increment-c` is
the fullest single account of what **C** landed.

| | |
| --- | --- |
| Merged | [#14](https://github.com/CAST-genomics/PangenomeAPI/issues/14), [#15](https://github.com/CAST-genomics/PangenomeAPI/issues/15), [#16](https://github.com/CAST-genomics/PangenomeAPI/issues/16), [#17](https://github.com/CAST-genomics/PangenomeAPI/issues/17), [#18](https://github.com/CAST-genomics/PangenomeAPI/issues/18), [#19](https://github.com/CAST-genomics/PangenomeAPI/issues/19), [#20](https://github.com/CAST-genomics/PangenomeAPI/issues/20), [#21](https://github.com/CAST-genomics/PangenomeAPI/issues/21), [#46](https://github.com/CAST-genomics/PangenomeAPI/issues/46), [#41](https://github.com/CAST-genomics/PangenomeAPI/issues/41), [#40](https://github.com/CAST-genomics/PangenomeAPI/issues/40), [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22), [#45](https://github.com/CAST-genomics/PangenomeAPI/issues/45), [#23](https://github.com/CAST-genomics/PangenomeAPI/issues/23), [#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24), [#66](https://github.com/CAST-genomics/PangenomeAPI/issues/66), [#70](https://github.com/CAST-genomics/PangenomeAPI/issues/70) |
| Frontier | **[#25](https://github.com/CAST-genomics/PangenomeAPI/issues/25)** — the contract test, and now the only unfinished part of **C**. `pgb`'s reader exists (`pgb`#151) and has read the real thing; what is missing is the test that keeps the two sides from drifting |
| Live | **A, B and C.** The server runs `main` as of 2026-09-02 and no longer goes back. `release` is 71 commits behind and is no longer what is deployed |
| Defects, outside the increments | [#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52), [#54](https://github.com/CAST-genomics/PangenomeAPI/issues/54), [#58](https://github.com/CAST-genomics/PangenomeAPI/issues/58) — all still open, all triaged, none blocking #25. #52 is answered *on the band route* by #24, and stands on the SVG route — see below |

---

## The one-sentence version

**`/seqtubemap` publishes the numbers it already has, instead of emulating a browser to
hide them in XML.**

## Why

*Written in the present tense on 2026-08-27, and kept that way: this is the problem the whole
programme was built against, and it is the state the service was in until 2026-09-02.*

A researcher clicks a **minigraph node** to look inside it. Roughly 43% of the time nothing
appears. When it works, a 10 kb region takes 120 seconds and delivers 10 MB — and the
frontend gives up at 90, so for a large node the feature is simply unavailable, with no way
to tell in advance which nodes will work.

And the failure is not contained. Both endpoints were `async def` while every stage blocks,
so one slow tube map request stalled **every** other request to the server, including the
`/json` the 3D graph depends on. (Fixed by
[#20](https://github.com/CAST-genomics/PangenomeAPI/issues/20), and live since the server
moved to `main` on 2026-09-02.)

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
                        │                      │                         └── #23 floats ✅── #24 ?format=bands ✅── #25 contract test ◀── HERE
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
#74 measure the lookup/parse split ── #75 stop the per-segment reads   (increment E, blocked by nothing)

Sent back by pgb's reader, all merged:
#66 a segment box as five numbers, not a path command ✅
#70 the format doc said numbers where the payload sends strings ✅
    (and PR #67, the same defect on pclaiScore)

Defects, off the sequence and blocking nothing:
#52 pgb refuses a reversal — answered on the band route (header, not body); the SVG route is unchanged, so #52 stands there
#54 concurrent extraction of one uncached region — corruption half fixed in PR #60
#76 GenerateWalksMC drops duplicate walk entries silently — needs a count before it is anything
#58 drop d3, and the dead read-track colouring that is its last user
```

**The frontier is [#25](https://github.com/CAST-genomics/PangenomeAPI/issues/25)**, and nothing blocks it. Edges are GitHub's native issue
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
request** — but the cost is `GenerateWalksMC`'s per-segment tabix loop, not `gbz-base`, whose own
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
and **live since 2026-09-02**, with everything else that had been queued behind `release`.

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

**That trial was not a promotion** — the server went back on `release` afterwards, and
`release..main` stayed the queue for two more days. What ended it was not a decision to
promote but **C** needing a live band route to be read against; see *What "live" means now*.

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
`pgb` can read neither on the SVG route — that is
[#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52), which predates this — and #24
decided what they mean on the band route: they ride in the header, each carrying its position
in the draw order.

### [#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24) — `?format=bands` ✅

JSON header (the dimensions, the strand table, the segment boxes) plus a binary body of
`Float32 × 6 + Uint16` per band. Per-strand values appear **once** instead of once per band,
and the geometry column is `pgb`'s GPU instance buffer with no parse step at all. The format
is specified in [`docs/band-format.md`](band-format.md), written to be enough to write a
parser against without reading the server.

**Additive.** Omit the parameter and you get today's response, byte for byte — checked over
the endpoint, not merely intended. An unrecognised `format` is refused with a 400 before any
stage runs, rather than quietly served as SVG.

**The projection is now a measurement**, and it was right and slightly pessimistic: **1.10 MB
against 9.97 MB** over the committed 7,967 bp subgraph, where this document predicted ~1.5 MB
against 10.07 MB. Across the five real subgraphs the ratio runs 1.9× at 90 bp to 9.3× at
44,795 bands — smallest where the response is smallest, because a 592-band payload is almost
all strand table. `perf/band-payload-sizes.mjs` reproduces the table.

| region | span | bands | SVG | band payload | ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| chr8:78,771,162-78,771,252 | 90 bp | 592 | 0.13 MB | 0.07 MB | 1.9× |
| chr1:25,331,046-25,331,646 | 600 bp | 8,089 | 2.25 MB | 0.27 MB | 8.5× |
| chr8:10,079,054-10,080,461 | 1.4 kb | 13,246 | 3.61 MB | 0.41 MB | 8.8× |
| chr1:25,301,271-25,309,238 | 8.0 kb | 35,020 | 9.97 MB | **1.10 MB** | 9.0× |
| chr1:25,331,646-25,335,796 | 4.2 kb | 44,795 | 12.58 MB | 1.35 MB | 9.3× |

*Re-measured 2026-09-02, after [#66](https://github.com/CAST-genomics/PangenomeAPI/issues/66)
took the segment outlines out of the header. The row that moved most is the 8.0 kb one, at
768 segment boxes: 1.25 MB → 1.10 MB.*

Three things the increment decided that the ticket left to it. The body is **columnar** —
interleaved, a 26-byte record admits no `Float32Array` view, so the client would copy the
fields apart one at a time, which is the parse step being deleted. A strand's colour travels
as **three whole channels** rather than CSS, so the rounding that caused the live chr7 refusal
happens once on the server. And a reversal's corners and connectors ride in the **header**,
each carrying its position in the draw order — which is [#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52)'s
answer on this route, and needs nothing new from `pgb`.

### What writing the reader sent back

Three corrections came the other way while `pgb`'s reader was being written (`pgb`#151), and
all three were found the same way: **by someone reading the spec instead of the encoder.**
That is what a format document written to be read without the server is for, and it is the
only part of this increment that could not have been found on this side.

- **[#67](https://github.com/CAST-genomics/PangenomeAPI/pull/67) — `pclaiScore` is an opaque
  string.** The spec's example wrote `0.98`. The band data carries it as text (`"993"`), and
  real schemes also spell it `"impainted"` on strands that *are* placed — a different kind of
  answer, not a number with a bad value. A reader taking the spec at its word either refuses
  real documents or turns a category into `NaN`.

- **[#70](https://github.com/CAST-genomics/PangenomeAPI/issues/70) — a segment's style fields
  are strings.** `fillOpacity` and `strokeWidth` were documented as `0.4` and `2`; the payload
  sends `"0.4"` and `"2px"`, because the four appearance fields come through `tubemap.js` as
  the document's own attribute values. `pgb`'s `SegmentBox.stroke` does arithmetic with it, so
  the spec as written laid a border of `NaN` width — silently, since `NaN` in a CSS length is
  an ignored declaration rather than an error. **The document moved, not the payload:** no
  encoder change, no bytes, and `version` stays 1.

- **[#66](https://github.com/CAST-genomics/PangenomeAPI/issues/66) — a segment box travels as
  numbers.** It had travelled as the path command that draws it —
  `"M 11 20 Q 11 11 20 11 L 67 11 …"` — and every one is a rounded rectangle whose five
  numbers the layout holds before it builds the string. Now those five travel, `outline`
  replaced rather than joined. This is #23's argument one level down, and it removed the last
  string in the payload a client had to parse back into numbers.

  `version` stayed 1 deliberately: a version protects readers and this format has none yet, so
  carrying both spellings would have kept the string in the format forever and left the reader
  being written at that moment with two ways to find the same rectangle.

  **The SVG route's bytes did move**, and the goldens were re-baselined. The layout walked the
  outline as a running position, so it printed the same edge twice one ulp apart —
  `225.85714285714286` along the top of a box, `225.8571428571429` along its bottom. Four to
  eight numbers per golden document, each within 1.5e-16 of what it was, no command and no
  element altered. That ulp is the same defect #66 cites as the reason `pgb` needed nine
  tolerant comparisons, so no five numbers can reproduce those bytes; a tolerance there would
  be the first of the comparisons the ticket exists to delete.

### [#25](https://github.com/CAST-genomics/PangenomeAPI/issues/25) — Contract test

Golden fixtures committed here; the test that parses them lives in `pgb`, where the parser
lives, and runs in `pgb`'s CI. **Not a vendored copy of the parser** — two copies that must
agree is precisely the failure mode this whole effort exists to remove.

**The reader now exists and has read the real thing**, which changes what this ticket is for.
It is no longer the step that proves the format works — 2026-09-02 did that, against the live
server. It is the step that stops the two sides drifting apart afterwards, and the three
corrections above are the evidence that they drift: each was a place where the spec and the
encoder had already disagreed, and each was caught by a human rather than by a test.

---

## What "live" means now — `main` on the server, 2026-09-02

**The server runs `main`, and is not going back.** The 2026-08-31 window was a loan against
`release`; this is not a loan. `pgb` retrieved `?format=bands` payloads from the deployed API
and drew from them, which is the first exercise of the format outside a test, and the first
time any of A, B or C has been what a researcher actually gets.

What that changes across this document:

- **The "before" numbers are now past tense.** The 120 s, 10 MB, ~43%-of-clicks-fail figures
  in *Why* describe what the service did on 2026-08-27 under `release`. They are the baseline,
  not the present.
- **`release` is no longer a claim about what is live.** It is a lagging pointer at what used
  to be, 71 commits behind. [`releasing.md`](./releasing.md) describes a discipline the deploy
  no longer follows, and says so at the top; whether to re-establish it, retire it, or promote
  `release` to catch up is an open decision, and a human one.
- **The after-column is now capturable.** `[stage-timing]` lines are being written by a server
  running the current code, which is exactly what the 2026-08-31 trial could not provide. See
  *Verifying the whole thing*.

The state is tagged: `increment-c`, annotated, on `origin`, at `f9b05f6`.

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

## Increment E — stop reading the walk table one segment at a time

**Ticketed 2026-09-02 as [#74](https://github.com/CAST-genomics/PangenomeAPI/issues/74) and
[#75](https://github.com/CAST-genomics/PangenomeAPI/issues/75), no ADR yet and possibly none
needed.** It comes from Step 0's numbers rather than from the grilling, and it is the largest
single cost in the pipeline: `GenerateWalksMC` is a Python loop doing one tabix `fetch` per
**segment** across 464 strands, at a flat **65-79 ms per segment**, and it is most of
`subgraph_extract`'s 30.1 s of a 38.9 s request.

**Scoped by outcome, not by mechanism.** Batching is the leading hypothesis, not the
definition — a measurement that rules it out changes what E contains rather than closing it
unsuccessfully. `docs/tube-map-pipeline.html` shows the mechanism in full.

### [#74](https://github.com/CAST-genomics/PangenomeAPI/issues/74) — Split the cost between the lookup and the parse *(human)*

The flat 65-79 ms is a fixed overhead paid once per segment, and nothing yet says which one:
the **lookup**, one tabix seek plus the decompression of a block that consecutive segments
probably share, or the **parse**, ~464 `assembly|contig:coord:strand` entries torn out of the
returned row in Python — roughly 177,000 of them for 381 segments.

`perf/walk-lookup-split.py` runs four arms over the same ids — point and range, each with and
without the parse — so subtraction separates them. It needs the real derivative and so runs on
the server, but it reads a file and touches nothing the app serves, so it does not need a live
window. What it decides is the **ratio**; it warms the cache first, so its absolutes will not
reproduce the published 30 s and are not meant to.

It also decides whether E needs an ADR: a parse-dominated result makes #75 "move the parse out
of the interpreter", and adding `numpy`, `pandas` or a C extension to a project that has none
wants one first. A lookup-dominated result does not.

### [#75](https://github.com/CAST-genomics/PangenomeAPI/issues/75) — Stop the per-segment reads

Blocked by #74. The walk table is tabix-indexed on the **segment id**, not on genomic
coordinates — column 1 is a constant `.` — so a range fetch addresses a range of *ids*. That
matters, because the segments do not tile the genome: bubbles put alternatives at the same
reference coordinates, and in the chr8 fixture `181810310` and `181810311` are the `A` and `C`
of one SNP. What is nearly gapless is the integers, and two of the five committed fixtures are
consecutive. 770 lookups where two would cover the same ground.

The batched form is not hypothetical — the v1 path in this same file already groups ids into
contiguous runs (`main.py:231-234`) and fetches a run at a time (`main.py:244`). The v2 path
never picked it up.

Success is the **`W` lines byte-identical, in the same order, across all five committed
fixtures**. That oracle is why this can be small, and it pins the duplicate-handling quirks in
place on purpose — they are [#76](https://github.com/CAST-genomics/PangenomeAPI/issues/76)'s
business, not this ticket's.

**E sits before D.** They touch disjoint code and neither blocks the other, but D is 0.63 s
and E is 30. E is blocked by nothing at all, #25 included: its oracle is the fixtures' `W`
lines, not the band contract.

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
impossible numbers, which was the groundwork, and
[#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24) answered it on the band route:
corners and connectors ride in the header, each carrying its position in the draw order, and a
client needs nothing new to skip or draw them. **On the SVG route #52 stands unchanged** — the
document still contains shapes `parseBands.ts` refuses, and its gate still refuses the whole
document over one of them. The route a client picks now decides whether the defect exists.

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

**Haplotype collapsing.** Every strand in the region appears in the response; nothing merges,
drops or samples them, regardless of how much time it would save. **The line is the output.**
Reading the ~464 strands' coordinates more cheaply — one split pass instead of three, keeping
them out of Python objects, parsing a row lazily, parsing it outside the interpreter — is an
implementation matter and is *not* this decision. Emitting fewer `W` lines is.

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
- **Does batching `GenerateWalksMC`'s reads help, or is the cost the parse?** That it *can* be
  batched is settled: the v1 path at `main.py:231-244` already groups ids into contiguous runs
  and fetches a run at a time, and the committed fixtures show the runs are there — two of five
  subgraphs are consecutive integers. What is unmeasured is whether the 65-79 ms is the seek or
  the parsing of 464 haplotypes' coordinates out of each row, and that decides whether E is a
  half-day or a rewrite. `perf/walk-lookup-split.py` is the measurement; it needs the real
  derivative and so runs on the server.
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
- ~~**Will anything ever read `?format=bands`?**~~ **Answered 2026-09-02: `pgb` does, off the
  live server.** The format's first consumer exists, which retires the risk that this
  increment published a format nobody would adopt — the risk ADR 0001's additive design was
  chosen to survive.
- **Does a reversal reach a real region?** #52 says `pgb` refuses any *SVG* document
  containing one, and two live windows have now drawn regions without hitting it. Whether that
  is luck or whether reversals are rare in this graph still decides how urgent #52 is, and
  nobody has counted. Less urgent than it was, in one specific way: the band route carries
  corners and connectors in the header, so a client on that route is no longer refused by
  them — which makes #52 a defect of the *old* route rather than of the picture.
- **Is `release` re-established, retired, or caught up?** The server runs `main` as of
  2026-09-02 and `release` is 71 commits behind, so the discipline in
  [`releasing.md`](./releasing.md) describes something the deploy no longer does. Three
  answers are available and it is a human decision, not a technical one. Until it is made,
  "what is live" is again a moment rather than a branch — which is the exact problem that
  document was written to fix.
- **Which regions has `pgb` actually drawn from band data?** 2026-09-02 established that the
  format works end to end. It did not establish coverage: nobody recorded which regions were
  tried, whether any were in the fetch-ceiling regime, or how the payload behaved at 44,795
  bands over a real network rather than a loopback.

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

The TTFB and payload rows above are still *before* figures, and there are no *after* ones.
Neither live window produced them: 2026-08-31 was a look rather than a measurement, and
2026-09-02 was a look at the band route. No `[stage-timing]` lines have been read off either.

**That is now a task rather than a blocker.** The server runs the current code
continuously, so the after-column needs nobody's permission — it needs somebody to pull
`[stage-timing]` lines for the same three regions at the same parameters and put them beside
the rows above. Until that happens this table is a baseline with an empty right-hand side, and
the honest statement about production latency is that it has not been measured since
2026-08-27.

Then update the rendered report **by passing its URL**
(`https://claude.ai/code/artifact/71539dd1-fb13-44d0-8468-a3a96e726114`); publishing without it
forks the link into a second artifact.
