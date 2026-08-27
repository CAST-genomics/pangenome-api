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
| Branch | `perf/seqtubemap-diagnosis` at `ab3e5b0`, local only, `main` untouched |
| Diagnosis | Complete, with one open gap (see Step 1) |
| Built | Local harness (`perf/`), server-side stage timers (`main.py`) |
| Changed in production behaviour | Nothing yet |

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
files and subprocesses, and that the cost lives in the joins.

## Known-good baseline

Verification at the end measures against these. All from the live API, 2026-08-27,
`chr8:78,771,162+`, `version=v2`, `pathnumoption=normal`.

| Region | TTFB | Payload |
| --- | ---: | ---: |
| 90 bp | 1.46 s | 178 KB |
| 3,000 bp | 35.33 s | 3.2 MB |
| 10,000 bp | 120.40 s | 10.1 MB |

---

## Step 0 — Push, and start the timers

**Skill:** none. Plain git and a deploy.

Push `perf/seqtubemap-diagnosis` and get the `[stage-timing]` instrumentation onto the
server. Capture three requests — roughly 90 bp, 3 kb, 10 kb — each against a **fresh
region** so `cached=False`, because the cached path skips the stage most likely to dominate.

```sh
grep '\[stage-timing\]' <logfile>
```

**Why first:** the ~34 s upstream figure is inferred by subtraction. Everything downstream
of here is ranked on that inference. One deploy converts it to fact and may reorder the
whole plan.

**Exit criteria:** you can name which of `subgraph_extract`, `gfa_process`, `gfa_to_vg`,
`vg_to_json`, `generate_svg` owns the majority of a slow request.

> This does not block Step 1. Start the deploy, then begin grilling; fold the numbers in
> when they arrive.

## Step 1 — Sharpen the idea

**Skill:** `/grill-with-docs` — the stateful interview.

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

## Step 2 — Decide the build shape

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

Ranked on evidence as of 2026-08-27. **Step 0's numbers may reorder this** — in particular,
if `subgraph_extract` dominates, items 1–2 win less than their effort suggests and the real
work moves into how the `gbz-base` query is issued.

1. **Delete the `vg` round trip.** `GFA → protobuf → JSON` exists only to change format
   between two processes this project controls, and inflates the payload **13×** (3.9 B per
   node visit as a GFA walk, 51.0 B as vg JSON, identical information). The target schema is
   trivial — `node[]` of `{id, sequence}`, `path[]` of `{name, mapping[].position}` — and
   the GFA already contains it. Removes two subprocess spawns and two temp files.
2. **Stop round-tripping through disk.** With `vg` gone, the remaining stages can pass bytes
   rather than filenames. The SVG is currently written to disk purely so `FileResponse` can
   read it back.
3. **Unblock the event loop.** `seqtubemap` is `async def` with four blocking
   `subprocess.run` calls inside it. This wins no latency but stops one slow request from
   killing every concurrent one — currently a hard outage, observed.
4. **Kill the per-request Node boot.** 722 ms measured, paid on every request, to start a
   process that immediately rebuilds the same JSDOM document.
5. **Only then** revisit the layout substrate — running the tube map layout without
   emulating a browser, or moving it to the client. Real, but 1–4 are cheaper and may make
   it unnecessary.

Not on this list but worth its own issue: **`pathnumoption=compressed` never fires**
(`main.py:212–226`) — it keys on the entire walk across the region, so one SNP prevents any
collapse. A correctness defect, not a performance item.

## Step 4 — Verify

**Skill:** none, plus **`/code-review`** if reviewing the whole branch against `main`.

Re-run the live probe against the baseline table above, same regions, same parameters. Then
re-run the local harness to confirm the Node stage did not regress:

```sh
node perf/bench.mjs --axis=spine
SPINES=40,150,600 HAPS=464 ALT=0.08 node perf/cross.mjs
python3 perf/gfa-rewrite-bench.py
```

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

- Does `subgraph_extract` dominate? (Step 0 answers this.)
- Is the SVG-over-HTTP contract with pgb fixed, or can the response shape change? This
  gates roadmap item 5 entirely and is a pgb question, not an API one.
- Does anything downstream depend on the intermediate `.gfa` / `.vg` / `.json` files
  existing on disk, or are they purely internal? They are deleted after every response,
  which suggests purely internal — worth confirming before removing them.
