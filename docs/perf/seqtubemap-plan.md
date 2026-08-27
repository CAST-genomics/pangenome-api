# `/seqtubemap` performance work — order of events

A working plan for the `/seqtubemap` latency effort: what happens in what order, which
skill drives each step, and what has already been decided so it doesn't get re-litigated.

Companion documents:

- [`seqtubemap-latency.md`](./seqtubemap-latency.md) — the measured findings this plan acts on
- [`perf/`](../../perf/) — the harness
- Rendered report: <https://claude.ai/code/artifact/71539dd1-fb13-44d0-8468-a3a96e726114>

Written 2026-08-27, at the end of the diagnosis phase.

---

## Where things stand

| | |
| --- | --- |
| Branch | `perf/seqtubemap-diagnosis` merged to `main` via PR [#12](https://github.com/CAST-genomics/PangenomeAPI/pull/12) |
| Diagnosis | Complete. The upstream stage was measured 2026-08-27 (see Step 0) |
| Grilling | Complete, 2026-08-27. Produced [`CONTEXT.md`](../../CONTEXT.md) and [ADR 0001](../adr/0001-additive-band-format.md) |
| Built | Local harness (`perf/`), server-side stage timers (`main.py`) |
| Changed in production behaviour | Nothing yet |

**The shape of the work is now settled.** Steps 0, 1 and 2 below are done; what remains is
Step 3 (the build). The increments are A-E under *The roadmap*; A-D come from ADR 0001, and
**E is new — it comes from Step 0's numbers and has no ADR behind it yet.**

## Decisions already made — do not reopen

These were considered and closed during diagnosis. Reopening them costs a grilling round
each.

**Result caching is ruled out.** Retrievals are near-random — a scientist loads a graph and
pokes arbitrary nodes with no intent to repeat a specific one. A cache would almost never
hit. This is settled on access-pattern grounds, not technical ones.

**Haplotype collapsing is out of scope.** The 464 strands are fixed input, not a variable to
optimise. Any proposal that reduces cost by merging or dropping haplotypes is off the table
regardless of how much time it would save. (The `pathnumoption=compressed` bug is still a
real defect worth its own issue — it just isn't the performance strategy.)

**The target is systemic plumbing inefficiency**, not hot loops and not data volume. The
working thesis is that the server is a set of separately-authored pieces joined by temp
files and subprocesses, and that the cost lives in the joins. Measurement bore this out: the
single largest cost is a headless browser emulated to serialize XML that the client parses
straight back into numbers.

Added by the grilling session, 2026-08-27. Each of these is recorded with its reasoning in
[ADR 0001](../adr/0001-additive-band-format.md):

**The band format is additive, never a replacement.** `?format=bands` appears beside the
existing SVG URL, which keeps working. The two repos never deploy in lockstep, and the SVG
stays as the oracle the band payload is checked against.

**The band data is canonical; the SVG is derived from it.** Not two sinks over one layout —
one path, so drift is impossible by construction rather than by discipline.

**`pgb` is the sole consumer**, and the `parseBands` grammar is an internal encoding between
two repos on one team rather than a public contract.

**Correctness is `parseBands`-equivalence**, not byte-identity — except in increment B,
where byte-compatibility is a deliberate constraint so the client need not move at all.

**`pathnumoption` does not exist on the band route.** It is measurably dead
(`main.py:212-226`, byte-identical output to `normal`), and fixing it would merge strands,
which is a data change and out of scope.

## Known-good baseline

Verification at the end measures against these. All from the live API, 2026-08-27,
`chr8:78,771,162+`, `version=v2`, `pathnumoption=normal`.

| Region | TTFB | Payload |
| --- | ---: | ---: |
| 90 bp | 1.46 s | 178 KB |
| 3,000 bp | 35.33 s | 3.2 MB |
| 10,000 bp | 120.40 s | 10.1 MB |

---

## Step 0 — Deploy, and start the timers ✅ *done 2026-08-27*

**Skill:** none. Plain git and a deploy.

The `[stage-timing]` instrumentation (PR #12) was deployed by a colleague with server access
following [`deploy-request.md`](./deploy-request.md), and three fresh regions — 90 bp, 3 kb,
10 kb, all `cached=False` — were captured. The full reading is in
[§6 of the findings](./seqtubemap-latency.md); the three results that change this plan:

**`subgraph_extract` dominates** — 30.1 s of a 38.9 s 10 kb request, 77%. The ~34 s upstream
inference was right about where the time lives.

**But it is `GenerateWalksMC`, not `gbz-base`.** The gbz query prints its own timing:
0.042 s of those 30.1 s. The rest is a Python loop doing one tabix `fetch` per node across
464 haplotypes, at a flat 65-79 ms per node. This is a new item — increment **E**.

**And SVG generation is bigger than §2 estimated** — 8.2 s at 10 kb rather than 1-2 s, and
91 s of a 93.6 s *cached* 35.9 kb request. It scales superlinearly with JSON size and takes
over entirely at the fetch ceiling.

**Exit criteria, met:** `subgraph_extract` owns the majority of a slow request at 10 kb;
`generate_svg` owns it above that.

**Task 2 followed separately.** The five pipeline intermediates arrived after the log, and
are committed at [`tests/fixtures/seqtubemap/`](../../tests/fixtures/seqtubemap/). Both
halves of [issue #16](https://github.com/CAST-genomics/PangenomeAPI/issues/16) are now
satisfied.

## Step 1 — Sharpen the idea ✅ *done 2026-08-27*

**Skill:** `/grill-with-docs` — the stateful interview.

**Outcome:** six rounds. Produced [`CONTEXT.md`](../../CONTEXT.md) — which `CLAUDE.md` had
been promising all along — and [ADR 0001](../adr/0001-additive-band-format.md). Two
measurements were taken mid-interview to settle questions rather than guess at them: the
layout-vs-DOM split (§7 of the findings) and the five-fixture byte census (§8).

The one-sentence statement of the change, per the exit criteria: **`/seqtubemap` publishes
the numbers it already has, instead of emulating a browser to hide them in XML.**

Precede it with **`/compact`**, not `/clear`. The diagnosis context matters to the
grilling — particularly the ruled-out paths above — but the raw sweep output does not, and
it is all recoverable from `seqtubemap-latency.md`.

Use `grill-with-docs` rather than `grill-me` for a specific reason: **`CLAUDE.md` points at
a `CONTEXT.md` that does not exist.** This project's domain vocabulary lives in other
people's heads. The interview produces that glossary as a side effect, plus ADRs for
hard-to-reverse calls. For an inherited codebase that paper trail is worth as much as the
refactor.

**Expect to settle:** how far the rework goes (targeted excisions vs. restructuring the
pipeline), what must not change (output fidelity, the 464 strands, the SVG contract pgb
depends on), and what "fast enough" means as a number.

**Exit criteria:** you can state the change in one sentence, and `CONTEXT.md` exists.

### If the shape is already settled

Skip to **`/request-refactor-plan`** instead. It interviews you about the increments rather
than the idea, and files the result as a GitHub issue broken into tiny safe commits. Use
grilling when still hunting; use refactor-plan when done hunting.

### If a question needs a runnable answer

Detour through **`/prototype`**. The likely candidate: *can the vg JSON be emitted directly
from the GFA, skipping `vg convert` and `vg view -j` entirely?* That is a question best
answered by throwaway code against a real GFA, not by argument. Bridge with **`/handoff`**
out and back, and reference the prototype branch from the resulting issue.

## Step 2 — Decide the build shape ✅ *done 2026-08-27*

**Answer: multi-session.** Four separable increments with real ordering between them, so
**`/to-spec`** then **`/to-tickets`**, filing into `CAST-genomics/PangenomeAPI` per
[`docs/agents/issue-tracker.md`](../agents/issue-tracker.md), each ticket declaring its
blocking edges. A-E below are the increments those tickets cover — E was added after Step 0
reported and has not been through `/to-spec`.

*Original guidance, retained:*

**Skill:** still inside the Step 1 window. Do not compact between Steps 1 and 2.

- **Multi-session build** → **`/to-spec`**, then **`/to-tickets`**. Tickets land as GitHub
  issues in `CAST-genomics/PangenomeAPI` per `docs/agents/issue-tracker.md`, each declaring
  its blocking edges.
- **Single session** → straight to **`/implement`** in the same window.

Given the roadmap below has at least four separable items with real ordering between them,
multi-session is the likely answer.

**Context hygiene:** Steps 1–2 must stay in **one unbroken context window**. Compact only
at the Step 0/1 boundary and after `/to-tickets` — never in between, or the spec loses the
thinking that produced it.

## Step 3 — Build

**Skill:** **`/implement`**, once per ticket, **`/clear`ing between each**. Each ticket is
self-contained, so the previous one's context is disposable.

`/implement` drives **`/tdd`** internally for each red-green slice and closes by running
**`/code-review`** (Standards + Spec) against the diff before committing.

### The roadmap, in order

Superseded 2026-08-27 by the grilling session. The previous ranking led with *delete the
`vg` round trip*, on the reasoning that it was the most obviously silly thing in the
pipeline. Two measurements re-ranked it: the DOM is **93.7%** of the memory, and **41-47%**
of every response carries no information. The ceiling has a name now, so the work that
raises it goes first and `vg` drops to last. Full reasoning in
[ADR 0001](../adr/0001-additive-band-format.md).

*Amended 2026-08-27, after Step 0.* The server timings confirmed D's demotion with a number
— 1.6% of a 10 kb request — and put a new item **E** above it, where the upstream time
turned out to actually be. A-C are untouched; §6 of the findings strengthens B and C rather
than weakening them, because `generate_svg` scales worse than §2 predicted.

Ranked by **what it wins**, against the goals in priority order: (1) no request blocks
another, (2) the unfetchable-node ceiling rises, (3) wall-clock. Bytes are a consequence of
these, never a target in themselves.

| | change | wins | risk |
| --- | --- | --- | --- |
| **#12** | stage timing ✅ *shipped, deployed, read* | measurement | none — no behaviour change |
| **A** | `async def` → `def` ×2; lazy `TabixFile` | goal 1 | very low |
| **B** | capture the d3 joins; derive SVG from band data; **delete jsdom + canvas** | goal 2 | low — see below |
| **C** | floats not strings; binary body; `?format=bands` | goals 2, 3 | medium |
| **E** | batch `GenerateWalksMC`'s per-node tabix fetch | goal 3 | unscoped — needs its own investigation |
| **D** | delete the `vg` round trip | provisioning, not perf | low |

**A — unblock the event loop.** `main.py:470` and `:527` are both `async def`, and neither
awaits anything: every pipeline stage is a blocking `subprocess.run`. FastAPI runs a plain
`def` endpoint in a threadpool automatically, so **deleting the word `async` twice is the
fix.** Ship it with the lazy `TabixFile` opens (`main.py:71`, `:73`, `:81`), which currently
prevent the app from booting unless all three `.walk.gz` derivatives are present even for a
request that touches none of them. Both are server-wide, so this improves `/json` too —
which also makes it the easiest PR in the programme for Cici to say yes to.

**B — delete the browser.** Capture the d3 data joins rather than appending to a document,
emit the SVG from the captured band data, and drop `jsdom` and `canvas` from
`package.json` — two of five dependencies, present solely to feed `tubemap.js`.

The reason B is *low* risk and not medium: it is held **byte-compatible with `pgb`'s
existing parser by design**. `parseBands.ts` requires `style="fill: rgb(R, G, B);
fill-opacity: 1;" trackID="N" trackName="…"` contiguous and in that order, and its
conformance gate counts `<rect>` + `<path>` in `g.track`. Dropping `color=`, `class=`, and
the empty `<title>` children changes neither. So B is a **server-only change against an
unchanged client**, and `pgb` becomes its conformance test — a bad B surfaces as an error
card in the frontend rather than as a diff nobody ran.

B ships band data carrying *path strings*, not six floats, and that is deliberate: it takes
the entire ceiling win without touching a line of geometry code, and leaves C as a pure
encoding change with B's own output as its oracle.

**C — the format.** The path builder emits floats; the response becomes a JSON header (the
viewBox and the ~464-row strand table) plus a binary body of `Float32 × 6 + Uint16` per band.
Roughly **1.5 MB against today's 10.07 MB** at the 10 kb region, with `pgb`'s regex pass
deleted rather than shrunk — typed arrays copy straight into the GPU buffer. This is the
increment where `pgb` changes, and where `pgb`'s ADR 0002 gets amended.

**D — delete the `vg` round trip.** *Re-ranked by Step 0: this is no longer a performance
item.* `gfa_to_vg` + `vg_to_json` measured **0.63 s of a 38.9 s request — 1.6%**. The
standing case for D survives on its own terms and none of them are latency: `GFA → protobuf
→ JSON` exists only to change format between two processes this project controls, inflates
the intermediate **13×** (3.9 B per segment visit as a GFA walk, 51.0 B as vg JSON), costs
two subprocess spawns and two temp files, and makes the `vg` binary a provisioning
dependency for anyone standing the service up. Schedule it as the cleanup it is, after
A-C and E. Step 0 was run to decide whether D was the first real fix; the answer is that it
is the last.

**E — make `GenerateWalksMC` not cost 79 ms a node.** *New from Step 0, and the largest
server-side win available.* 30.0 s of a 38.9 s 10 kb request is one function
(`main.py:177`), and the graph query it wraps accounts for 0.042 s of that. The cost is flat
per node — 65 ms at 13 nodes, 65 ms at 118, 79 ms at 381 — which is the signature of a fixed
per-iteration overhead rather than an algorithm that grows. The loop does one
`mc_mapped_walks_v2.fetch()` per `S` line and rebuilds coordinate tables across 464
haplotypes in Python.

E has no ADR and has not been grilled. It is also **entirely independent of A-D**: it sits
upstream of layout, touches no wire format, and `pgb` cannot observe it. That makes it
schedulable in parallel with the band work rather than in sequence with it — but not
startable without first establishing what the fetch pattern actually costs and whether a
single batched query can replace the per-node one. That investigation is the prerequisite,
not the fix.

Also worth its own issue, and not a performance item: **`pathnumoption=compressed` never
fires** (`main.py:212-226`). It keys on the entire walk across the region, so a single SNP
prevents any collapse — measured byte-identical to `normal` at 1000 bp. It is a correctness
defect, and ADR 0001 records why it is not carried onto the band route.

### Two things to do alongside

**Declare the fork.** `seqtubemap/tubemap.js` is an unmarked 4,000-line vendored copy of
`vgteam/sequence-tube-map`, carrying upstream's eslint header and no provenance, version, or
README note. B removes its DOM sink, so the re-sync option is gone in fact; a header comment
naming upstream and the commit makes it gone on paper. This is the single most
duct-taped-feeling artifact in the repo and one comment fixes the feeling as well as the
fact.

**Get golden inputs.** `pgb` commits five real documents in
`src/tubemap/__tests__/fixtures/` — 0.29 MB to 13.56 MB, 369 to 464 strands, including the
two at the fetch ceiling. Those pin the *expected* side. The matching **inputs** exist only
on the live server, so the intermediates for those five regions are part of the ask in
[`deploy-request.md`](./deploy-request.md). Once they land, the fixtures become end-to-end
and B has a real oracle.

> **Landed 2026-08-27.** All five are committed at
> [`tests/fixtures/seqtubemap/`](../../tests/fixtures/seqtubemap/), matched to their golden
> outputs on strand count. **B has its oracle.** The fixtures are the only copy of these
> inputs outside the live server — they cannot be regenerated without the HPRC GBZ.

## Step 4 — Verify

**Skill:** none, plus **`/code-review`** if reviewing the whole branch against `main`.

Re-run the live probe against the baseline table above, same regions, same parameters. Then
re-run the local harness to confirm the Node stage did not regress:

```sh
node perf/bench.mjs --axis=spine
SPINES=40,150,600 HAPS=464 ALT=0.08 node perf/cross.mjs
python3 perf/gfa-rewrite-bench.py
node --expose-gc --max-old-space-size=8192 perf/rss-split.mjs \\
  perf/fixtures/split-400.json 0 8000 compressed
```

`rss-split.mjs` is the one that matters after B: it should report the DOM share at or near
**zero**, because there should no longer be a DOM. Its `--expose-gc` requirement is not
optional — retained-memory numbers taken without a forced collection measure garbage rather
than retention.

Update `seqtubemap-latency.md` with after-numbers beside the before-numbers. Update the
artifact by passing its URL — publishing without it forks the link into a second artifact.

---

## Skill quick reference for this effort

| Situation | Skill |
| --- | --- |
| Shape of the work still open | `/grill-with-docs` |
| Shape settled, need safe increments | `/request-refactor-plan` |
| A design question needs runnable proof | `/prototype` (+ `/handoff` both ways) |
| Interview thread → buildable plan | `/to-spec` |
| Plan → tickets with blocking edges | `/to-tickets` |
| Build one ticket | `/implement` (drives `/tdd`, closes with `/code-review`) |
| Review a branch against a fixed point | `/code-review` |
| Something breaks during the rework | `/diagnosing-bugs` |
| The duct-tape survey beyond seqtubemap | `/improve-codebase-architecture` |
| A message didn't land | `/wait-what` |

## Open questions

- **Can `GenerateWalksMC`'s per-node tabix fetch be batched?** This is now the open
  question that most changes the plan — it is the difference between increment E being a
  half-day and a rewrite. Nothing else is blocked on it.
- **Does anything depend on the intermediate `.gfa` / `.vg` / `.json` files existing on
  disk?** They are deleted after every response, which suggests purely internal — worth
  confirming with Cici before removing them.

*Closed by the grilling session:* whether the SVG contract can change (yes — `pgb` is the
sole consumer and the two repos are one team), and whether `create()`'s cost is layout or
DOM (DOM, 93.7%).

*Closed by Step 0:* whether `subgraph_extract` dominates (yes at 10 kb — 77%, and it is
`GenerateWalksMC` inside it), and whether the `vg` round trip is worth removing for speed
(no — 1.6%).
