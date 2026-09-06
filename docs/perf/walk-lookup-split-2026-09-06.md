# The lookup, not the parse — 2026-09-06

The result of [#74](https://github.com/CAST-genomics/PangenomeAPI/issues/74), run on the
server against the real walk derivative. It decides the shape of
[#75](https://github.com/CAST-genomics/PangenomeAPI/issues/75) and therefore of increment
**E**, and the answer is unambiguous: **the cost is the tabix lookup.**

`docs/increment-e-batched-walk-reads.md` §3 is increment E as written. No ADR — no dependency
is added and no interface changes.

## Raw output

Verbatim, as `perf/walk-lookup-split.py` printed it. Read the note below it before quoting
any line of it.

```
(base) [xbu@pangenome-api ~/pangenome-api]$ python3 perf/walk-lookup-split.py tests/fixtures/seqtubemap/subgraph_chr1_25301271_25309238_v2_with_walk.gfa
tests/fixtures/seqtubemap/subgraph_chr1_25301271_25309238_v2_with_walk.gfa
  770 segments, ids 79335081-79335857, span 777
  2 contiguous run(s) -> 770 point fetches become 2
  walks: /data/xbu/hprc-v2.0-mc-grch38-v2.2.walk.gz

 point+parse   90.031 s    116.9 ms/segment   770 rows, 6.8 MB
       point   73.219 s     95.1 ms/segment   770 rows, 6.8 MB
 range+parse    0.306 s      0.4 ms/segment   770 rows, 6.8 MB
       range    0.185 s      0.2 ms/segment   770 rows, 6.8 MB

  parse             16.811 s   (19% of today)
  point-vs-range    73.035 s   (81% of today) <- what batching removes

  today             90.031 s
  batched            0.306 s   293.8x
```

## Reading this output

**The `parse` line is wrong, and it is the script's fault, not the machine's.** The script
derives the parse cost by subtracting across the two point arms — `point+parse − point` =
16.811 s. The same parse, over the same 770 rows, into the same tables, measured across the
two range arms is `range+parse − range` = 0.306 − 0.185 = **0.121 s**. Both figures are
medians of three passes, so neither is a single-shot fluke.

21.8 ms/segment against 0.157 ms/segment is a factor of 139 for identical work. The two arms
differ in exactly one respect — 770 fetches versus 2 — so the 16.8 s is not parse work that
batching would leave behind. It is *more lookup cost*, and it appears only when the fetches
are pointwise.

The subtraction the script performs is only valid if a row costs the same to hand back in
either arm. This run is the evidence that it does not. Taking the parse from the range side,
where no per-fetch overhead is mixed into it, the real split is:

| | | |
| --- | ---: | ---: |
| parse | ~0.12 s | 0.1% of today |
| lookup | ~89.9 s | 99.9% of today |

Which is the same verdict the printed 19/81 gives, only more so.

## What this does and does not say

**The ratio is the finding.** The script warms the page cache before timing, deliberately and
in a comment, so that the arms are compared against each other rather than against whichever
ran first. Its absolutes are not the published numbers and are not meant to be: 116.9
ms/segment here against the 65–79 ms/segment in
[`seqtubemap-latency.md`](./seqtubemap-latency.md), *with* a warm cache, is on its own enough
to say the two are not comparable in either direction.

**So `293.8x` is not a speedup, and must not be published as one.** It divides a warm 0.306 s
by a warm 90.031 s on one fixture. Increment E's real number is
`GenerateWalksMC`'s stage time on a cold ~10 kb region against the published 30.1 s of a 38.9
s request, and it gets measured when #75 ships, the way
[`increment-b.md`](./increment-b.md) and [`increment-c.md`](./increment-c.md) report theirs.

**This was the favourable fixture.** chr1:25,301,271 is 770 segments across a span of 777 in
**2 runs** — very nearly gapless. The adversarial one is chr1:25,331,646: 280 segments across
a span of 5,569 in **5 runs**, where a range fetch decompresses on the order of 5,569 rows at
~14 KB each to use 280 of them. It has not been run. Correctness there is covered regardless
— #75's acceptance is byte-identical `W` lines across all five committed fixtures, that one
included — but whether batching is a *speed* win on a sparse region is still open, and it is
the same measurement that would set the gap-coalescing parameter §6 of the increment E
document ships at zero. Better taken against #75's real implementation than against this
harness.

**The dup count did not come back.** #74 asked for
[#76](https://github.com/CAST-genomics/PangenomeAPI/issues/76)'s number — how often the
silent `continue` at `main.py:373` fires — out of the same run, and the output carries no
count. #76 stays blocked on it. It does not block #75, which pins the behaviour byte for byte
by construction.
