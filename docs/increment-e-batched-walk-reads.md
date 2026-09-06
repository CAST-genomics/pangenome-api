# Increment E — batching the walk-table reads

What [#75](https://github.com/CAST-genomics/PangenomeAPI/issues/75) actually changes, in
pseudo-code, before and after. Written 2026-09-04; §7 updated 2026-09-06, when
[#74](https://github.com/CAST-genomics/PangenomeAPI/issues/74) — the measurement that decided
whether this is the right change at all — reported. It is.

Rendered as an illustrated page at <https://claude.ai/code/artifact/14368675-f544-48e0-b245-bbc33680145c>, and committed alongside this file as
[`docs/increment-e-batched-walk-reads.html`](./increment-e-batched-walk-reads.html).

Companions: [`docs/seqtubemap-roadmap.md`](./seqtubemap-roadmap.md) for where E sits in the
sequence, [`docs/tube-map-pipeline.html`](./tube-map-pipeline.html) for the whole pipeline
this one stage lives in, [`CONTEXT.md`](../CONTEXT.md) for **segment**, **strand** and
**node**.

---

## 1. The file being read

`GenerateWalksMC` is handed an extracted subgraph that has `S` and `L` lines and **no `W`
lines** — segments and their connections, but nothing that names a haplotype. Its job is to
manufacture the `W` lines, and the raw material is a separate file: the **walk derivative**,
`hprc-v2.0-mc-grch38-v2.2.walk.gz`.

That file is bgzip-compressed and **tabix-indexed**, which is where the shape gets unusual.
Tabix is ordinarily a *genomic* index — chromosome, start, end. Here:

| Col | Holds | Example |
|---|---|---|
| 1 | the chromosome column, a constant placeholder | `.` |
| 2 | **the segment id** — what tabix actually indexes on | `181810309` |
| 3 | that segment's length in bases | `145` |
| 4 | **every haplotype sitting at this segment**, comma-separated, each entry `assembly\|contig:coord:strand` | `HG00544#2\|CM089383.1:17162:+,…` ×464 |
| 5 | repeat placements, or `.` when there are none | `.` |

So it is a genomic index repurposed as a **segment-id index**. `fetch(".", id-1, id)` means
"the one row for this one segment". And **`fetch(".", lo-1, hi)` means "every row from
segment `lo` through segment `hi`"** — that is the whole of the batching idea. The index
already supports it; the v2 code path just never asks.

Column 4 is the payload and it is large: one row lists where *all 464 haplotypes* sit at that
single segment, which at ~30 characters an entry is on the order of **14 KB of text per
row**.

---

## 2. What the code does today

`_write_walks_mc`, `main.py:325-456`. Stripped to its skeleton:

```
open subgraph.gfa            # S and L lines, no W lines
open output.gfa
coord_table = {}             # {assembly: {contig: [coords, segment_ids, strands]}}
dup_table   = {}

for line in subgraph.gfa:

    if line is an S line:
        segment_id = line.field(1)

        for row in walks.fetch(".", segment_id - 1, segment_id):   # ◀ ONE SEEK, PER SEGMENT
            _, _, length, haplotypes, repeats = row.split(TAB)
            for entry in haplotypes.split(","):                    # ~464 of them
                asm, contig, coord, strand = tear apart entry
                append (coord, coord+length), segment_id, strand
                    into coord_table[asm][contig]
            if repeats != ".":
                … the same, into dup_table …

        copy line to output.gfa

    else if line is an L or H line:
        copy line to output.gfa

# second phase, unchanged by any of this
for asm, contig in coord_table:
    fold dup_table entries back in
    sort by coordinate
    split where consecutive intervals do not abut
    emit one W line per fragment
```

**One `fetch` per `S` line.** For a 10 kb region that is 381 seeks; for the largest committed
fixture, 770. Measured cost is a flat **65-79 ms per segment**, and it is most of
`subgraph_extract`'s 30.1 s out of a 38.9 s request — the single largest cost in the whole
pipeline.

A *flat* per-segment cost is the signature of a **fixed overhead paid once per segment**,
rather than of work that scales with the data. Two candidates, and #74 exists to tell them
apart:

- **the lookup** — one tabix seek plus the decompression of the bgzip block the row lands in.
  Consecutive segment ids very likely share a block, so asking one at a time may be
  decompressing the same block over and over.
- **the parse** — ~464 `assembly|contig:coord:strand` entries torn apart in Python, per row.
  Roughly **177,000 field splits** for 381 segments.

Batching removes the first entirely and does nothing at all about the second.

---

## 3. What the batched version does

The change is confined to how the rows are *obtained*. Everything about what is done with a
row stays byte-for-byte identical.

```
open subgraph.gfa
open output.gfa
segment_ids = []

# ── pass 1: read the GFA, copy it through, remember the ids ────────────────
for line in subgraph.gfa:
    if line is an S line:
        segment_ids.append(line.field(1))
        copy line to output.gfa
    else if line is an L or H line:
        copy line to output.gfa

# ── pass 2: one fetch per RUN of consecutive ids ───────────────────────────
coord_table = {}
dup_table   = {}
wanted      = set(segment_ids)

for run in contiguous_runs(sorted(segment_ids)):
    for row in walks.fetch(".", run.first - 1, run.last):           # ◀ ONE SEEK, PER RUN
        if row.field(1) not in wanted:                              # ◀ NEW: skip strays
            continue
        … the identical body from §2, verbatim …

# second phase: completely untouched
```

with

```
contiguous_runs(sorted_ids):                    # main.py:231-234, already in this file
    runs = []
    for id in sorted_ids:
        if runs is empty or runs.last.last + 1 != id:
            runs.append([id])                   # a gap: start a new run
        else:
            runs.last.append(id)                # consecutive: extend
    return runs
```

**`contiguous_runs` is not new code.** The **v1** path in this same file already does exactly
this — it groups ids into runs at `main.py:231-234` and fetches a run at a time at
`main.py:246`. The v2 path simply never picked the pattern up. E is porting a technique that
is already in the file, thirty lines above.

### Why runs work here

The segments do **not** tile the genome. Bubbles put alternatives at the *same* reference
coordinates — in the chr8 fixture, `181810310` and `181810311` are the `A` and the `C` of one
SNP. What is nearly gapless is not the coordinates, it is the **integers**. And the walk
table is indexed on the integers.

Measured over the five committed fixtures:

| fixture | segments | ids | runs | fetches today → batched |
|---|---:|---|---:|---|
| chr1 25301271-25309238 | 770 | 79335081-79335857 | **2** | 770 → **2** |
| chr1 25331046-25331646 | 75 | 79337767-79337921 | **2** | 75 → **2** |
| chr1 25331646-25335796 | 280 | 79332638-79338206 | **5** | 280 → **5** |
| chr8 10079054-10080461 | 92 | 182992415-182992506 | **1** | 92 → **1** |
| chr8 78771162-78771252 | 9 | 181810309-181810317 | **1** | 9 → **1** |

Two of the five are a single unbroken run. The worst case in the set is five fetches instead
of 280.

---

## 4. Exactly three things differ

Everything else is the same code executing on the same rows. It is worth being precise about
the three, because they are the entire risk surface.

**(a) The number of seeks.** 770 → 2. This is the point of the exercise.

**(b) The order rows are parsed in.** Today it is *`S`-line order in the GFA*; batched it is
*ascending segment id*. These are the same order whenever the GFA's `S` lines ascend — and
all five committed fixtures do, with no duplicate ids. It matters because `coord_table` is
built by appending, and the second phase's `sorted(...)` is stable: a tie between two
coordinates is broken by insertion order. So a fixture whose `S` lines were *not* sorted
could in principle emit a differently-ordered `W` line. Cheap insurance: assert the ids
ascend, and fall back to the per-segment path if they do not. The five fixtures then prove
the fast path.

**(c) A filter that did not exist before.** A range fetch can hand back rows for ids the
subgraph does not contain. With *exact* runs it never does — by construction every id inside
a run is wanted — so the `if not in wanted: continue` line is dead code today. It stops being
dead the moment runs are coalesced across gaps (§6), which is why it goes in now.

### And what does not change

- The parse body, character for character. The same splits, the same tuples, the same
  `coord_table` and `dup_table` shapes.
- The `W`-line emission phase. Untouched.
- The duplicate-handling quirks — the `if any(coord == t[0] …): continue`, the silent drops.
  Those are [#76](https://github.com/CAST-genomics/PangenomeAPI/issues/76)'s business and E
  deliberately preserves them, bug-for-bug, so that "byte-identical" is a usable oracle.
- **Memory.** `fetch` returns an *iterator*; a range fetch streams rows one at a time exactly
  as a point fetch does. Nothing is accumulated that was not accumulated before. The only new
  allocation is the id list — 770 integers.
- The atomic-write wrapper in `GenerateWalksMC`, and the `.partial-<pid>-<tid>` naming.

---

## 5. One thing to be careful about

`WalkDerivative` keeps **one tabix handle per thread**, and that is load-bearing
(`main.py:115-168`): a `pysam.TabixFile` is one htslib handle with **one seek position**, and
two live iterators over the same handle will corrupt each other. Today's loop is safe by
accident — the inner `for` over a one-row fetch always runs to completion before the next
begins.

The batched loop must keep that property deliberately: **fully consume a run's iterator
before starting another fetch on the same handle.** The pseudo-code in §3 does. Any later
refactor that, say, tries to interleave two runs, or hands a half-consumed iterator to a
helper that fetches something else, breaks it — and breaks it silently, as wrong coordinates
rather than as an exception.

---

## 6. The tunable we are not turning on yet

Runs are exact: a gap of even one id starts a new fetch. The obvious next question is whether
to **coalesce runs separated by a small gap** — accept some unwanted rows in exchange for
fewer seeks.

The fixtures say: do not bother yet. The worst case is already 5 fetches. And the arithmetic
is unfavourable at scale — chr1 25331646-25335796 holds 280 segments across a span of 5,569
ids, so coalescing its five runs into one fetch would decompress and hand back on the order of
5,569 rows at ~14 KB each to use 280 of them. The filter is cheap (`split("\t", 2)[1]`, no
full parse) but the *decompression* is not.

If it ever earns its place, it is one parameter — coalesce when the gap is ≤ G ids — and G
should be chosen from a measurement, not a guess. Ship G = 0 (exact runs).

---

## 7. What #74 decided

**The lookup dominates, and §3 is increment E.** Roughly a half-day, no new dependency, no
interface change, no ADR.

`perf/walk-lookup-split.py` ran on the server on 2026-09-06 over chr1:25,301,271 — 770
segments, 2 runs. Fetching them one at a time took **90.0 s**; fetching them as two ranges and
running the identical parse took **0.31 s**. The parse itself, isolated on the range side
where no per-fetch cost is mixed into it, is **0.12 s** — a tenth of a percent of today.

The run is recorded in
[`docs/perf/walk-lookup-split-2026-09-06.md`](./perf/walk-lookup-split-2026-09-06.md),
including why the script's own printed `parse` line reads 19% and why that figure understates
the result rather than qualifying it.

So the branch this document was written under — *parse dominates, move ~177,000 field splits
out of the interpreter into `numpy`, `pandas` or a C extension, and write an ADR first* — is
closed. Nothing in §§1–6 changes.

**One thing the measurement does not settle.** The fixture it ran on is nearly gapless: 770
ids across a span of 777. The adversarial case is chr1:25,331,646, where 280 segments are
spread across a span of 5,569 in 5 runs, and a range fetch decompresses on the order of 5,569
rows at ~14 KB each to use 280 of them. Correctness is covered there by the byte-identical
oracle in §8. Whether it is a *speed* win is not, and it is the same measurement that would
set the coalescing parameter §6 ships at zero — so it belongs against the real implementation,
not against the harness.

The third possibility the arms could have surfaced — that the cost is neither, and is the
sheer volume of column 4 — is not ruled out and not raised by these numbers. It would be a
data-pipeline change and not this ticket.

---

## 8. How we know it worked

Two numbers and one oracle.

**Correctness — the oracle.** The `W` lines must be **byte-identical, in the same order,
across all five committed fixtures**. Not "equivalent", not "same set" — identical bytes.
That is what makes this change small enough to be safe: the duplicate quirks, the gap
splitting, the ordering all get pinned in place rather than reasoned about.

**Speed.** `GenerateWalksMC`'s stage time on a ~10 kb uncached region, against the published
30.1 s of a 38.9 s request. Reported the way `docs/perf/increment-b.md` and
`docs/perf/increment-c.md` report theirs.

**Fetch count.** Log the segment count and the run count per request. It is one line, it
makes the win legible in production rather than only in a benchmark, and it is the number
that tells us whether real regions look like the fixtures.
