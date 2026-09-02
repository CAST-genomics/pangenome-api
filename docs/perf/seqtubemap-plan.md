# `/seqtubemap` performance work — how the effort was run

The phase record for the `/seqtubemap` latency effort: what happened in what order, which
skill drove each step, and what each one produced.

**This document does not carry status.** The tickets, the increments, what has merged and
what is next all live in [`../seqtubemap-roadmap.md`](../seqtubemap-roadmap.md), which is
the current document and the one to read first. Two documents claiming to say where things
stand is the exact failure mode this whole refactor exists to remove, so this one stopped
claiming it.

Companion documents:

- [`../seqtubemap-roadmap.md`](../seqtubemap-roadmap.md) — the build: tickets, increments, and where they stand
- [`seqtubemap-latency.md`](./seqtubemap-latency.md) — the measured findings this plan acted on, and the before-baseline
- [`increment-b.md`](./increment-b.md) — what **B** actually bought, before and after
- [`increment-c.md`](./increment-c.md) — what **C** bought, and the day `pgb` read it
- [`../band-format.md`](../band-format.md) — the wire format **C** publishes
- [`local-endpoint-harness.md`](./local-endpoint-harness.md) — how to drive the endpoint with no graph data and no `vg`
- [`perf/`](../../perf/) — the harness
- Rendered report: <https://claude.ai/code/artifact/71539dd1-fb13-44d0-8468-a3a96e726114>

Written 2026-08-27 at the end of the diagnosis phase; cut back to the phase record on
2026-09-01, when the roadmap took over everything else.

---

## Step 0 — Deploy, and start the timers ✅ *done 2026-08-27*

**Skill:** none. Plain git and a deploy.

The `[stage-timing]` instrumentation (PR #12) went onto the live server and three fresh
regions — 90 bp, 3 kb, 10 kb, all `cached=False` — were captured, along with the pipeline
intermediates for the five regions `pgb` holds goldens for. The full reading is
[§6 of the findings](./seqtubemap-latency.md).

**Exit criteria, met:** `subgraph_extract` owns the majority of a slow request at 10 kb;
`generate_svg` owns it above that.

**It re-ranked the work, which is why the step existed.** Three results did it:
`subgraph_extract` is 77% of a 10 kb request, but the cost is `GenerateWalksMC` and not
`gbz-base`; the `vg` round trip is 1.6%, which demoted increment **D** out of performance
entirely and added **E**; and `generate_svg` is superlinear — 8.2 s at 10 kb, 91 s of a
93.6 s *cached* 35.9 kb request — which strengthened **B** and **C** rather than weakening
them.

Step 0 was run to decide whether **D** was the first real fix. The answer was that it is
the last.

## Step 1 — Sharpen the idea ✅ *done 2026-08-27*

**Skill:** `/grill-with-docs` — the stateful interview.

**Outcome:** six rounds. Produced [`CONTEXT.md`](../../CONTEXT.md) — which `CLAUDE.md` had
been promising all along — and [ADR 0001](../adr/0001-additive-band-format.md). Two
measurements were taken mid-interview to settle questions rather than guess at them: the
layout-vs-DOM split (§7 of the findings) and the five-fixture byte census (§8).

The one-sentence statement of the change, per the exit criteria: **`/seqtubemap` publishes
the numbers it already has, instead of emulating a browser to hide them in XML.**

`grill-with-docs` rather than `grill-me` for a specific reason: **`CLAUDE.md` pointed at a
`CONTEXT.md` that did not exist.** This project's domain vocabulary lived in other people's
heads. The interview produced that glossary as a side effect, plus ADRs for hard-to-reverse
calls. For an inherited codebase that paper trail turned out to be worth as much as the
refactor.

**Exit criteria:** you can state the change in one sentence, and `CONTEXT.md` exists.

*Preceded by `/compact`, not `/clear`.* The diagnosis context mattered to the grilling —
particularly the ruled-out paths — but the raw sweep output did not, and it was all
recoverable from `seqtubemap-latency.md`.

## Step 2 — Decide the build shape ✅ *done 2026-08-27*

**Answer: multi-session.** Separable increments with real ordering between them, so
**`/to-spec`** then **`/to-tickets`**, filing into `CAST-genomics/PangenomeAPI` per
[`docs/agents/issue-tracker.md`](../agents/issue-tracker.md), each ticket declaring its
blocking edges. Those tickets are the roadmap.

*The rule that applied here:* multi-session build → `/to-spec` then `/to-tickets`; single
session → straight to `/implement` in the same window.

**Context hygiene:** Steps 1 and 2 stayed in **one unbroken context window**. Compact only
at the Step 0/1 boundary and after `/to-tickets` — never in between, or the spec loses the
thinking that produced it.

## Step 3 — Build *(in progress)*

**Skill:** **`/implement`**, once per ticket, **`/clear`ing between each**. Each ticket is
self-contained, so the previous one's context is disposable.

`/implement` drives **`/tdd`** internally for each red-green slice and closes by running
**`/code-review`** (Standards + Spec) against the diff before committing.

**Where it stands is the roadmap's job, not this document's.**

### How the increment order was reached, and revised

Worth keeping because it changed twice, both times on measurement rather than argument.

The original ranking led with *delete the `vg` round trip*, on the reasoning that it was
the most obviously silly thing in the pipeline. **The grilling session re-ranked it**
(2026-08-27): the DOM is 93.7% of the memory and 41–47% of every response carries no
information, so the work that raises the ceiling goes first and `vg` drops to last. Full
reasoning in [ADR 0001](../adr/0001-additive-band-format.md).

**Step 0 then confirmed the demotion with a number** — 1.6% of a 10 kb request — and put a
new increment **E** above it, where the upstream time actually turned out to be. A–C were
untouched.

**E has no ADR and has not been grilled.** It comes from Step 0's numbers rather than from
the interview, and it is entirely independent of A–D: it sits upstream of layout, touches
no wire format, and `pgb` cannot observe it. That makes it schedulable in parallel with the
band work rather than in sequence with it — but not startable without first establishing
whether a single batched query can replace the per-segment one. That investigation is the
prerequisite, not the fix.

> **Amended 2026-09-02.** E has since been grilled, and the sentence above is a record of
> where Step 0 left it rather than where it stands. It is now #74 (measure the split) and #75
> (stop the per-segment reads), and whether it wants an ADR is a question #74 answers. Status
> lives in [the roadmap](../seqtubemap-roadmap.md), per this document's own rule.

## Step 4 — Verify

**Skill:** none, plus **`/code-review`** if reviewing the whole branch against `main`.

Re-run the live probe against the baseline in [§1 of the findings](./seqtubemap-latency.md),
same regions, same parameters. Then re-run the local harness to confirm the Node stage did
not regress:

```sh
node perf/bench.mjs --axis=spine
SPINES=40,150,600 HAPS=464 ALT=0.08 node perf/cross.mjs
python3 perf/gfa-rewrite-bench.py
node --expose-gc --max-old-space-size=8192 perf/rss-split.mjs \
  perf/fixtures/split-400.json 0 8000 compressed
```

`--expose-gc` is not optional — retained-memory numbers taken without a forced collection
measure garbage rather than retention.

Update `seqtubemap-latency.md` with after-numbers beside the before-numbers. Update the
rendered artifact **by passing its URL**; publishing without it forks the link into a
second artifact.

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
