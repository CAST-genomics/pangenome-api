# After the stage timings come back ✅ *closed 2026-08-27*

Both halves of the deploy in [`deploy-request.md`](./deploy-request.md) came back — the log
first, the five subgraphs after. The reading is
[§6 of `seqtubemap-latency.md`](./seqtubemap-latency.md); the raw log is
`pangenome-api-sequence-tube-map-logs/seqtubmap-log.txt`.

- ✅ §2 and §6 of [`seqtubemap-latency.md`](./seqtubemap-latency.md) updated. The ~34 s
  upstream figure is now measured at **30.1 s of a 38.9 s 10 kb request**, and attributed to
  `GenerateWalksMC` rather than to `gbz-base` or `vg`.
- ✅ Increment **D** re-ranked in [`seqtubemap-plan.md`](./seqtubemap-plan.md). The `vg`
  round trip is 1.6% of a slow request — it is a provisioning cleanup, not a perf fix. A new
  increment **E** takes its old place.
- ✅ Rendered report updated in place at
  `https://claude.ai/code/artifact/71539dd1-fb13-44d0-8468-a3a96e726114`.
- ✅ **Task 2 landed separately**, after the log. All five pipeline intermediates are
  committed at [`tests/fixtures/seqtubemap/`](../../tests/fixtures/seqtubemap/), each matched
  to its `pgb` golden output on strand count. `*.gfa*` is gitignored repo-wide, so they are
  exempted by an explicit negation — a sixth fixture must go in that same directory or it
  will be silently ignored.

## What the log actually looked like

Worth recording, because the shape documented here beforehand was wrong in two ways.

`gfa_process` does not appear — the call is commented out (`main.py:679-680`), and
`get_pclai_color_scheme` sits in the emitted line instead. A real line:

```
[stage-timing] chr8:78920000-78930000 span=10000bp v2 path=normal width=compressed
cached=False total=38.887s subgraph_extract=30.077s gfa_to_vg=0.071s vg_to_json=0.563s
get_pclai_color_scheme=0.0s generate_svg=8.176s json_mb=11.59 svg_mb=16.64
```

Each line also appears two to five times, once per handler on the logger, and
`grep '\[stage-timing\]'` does not dedupe them. Read `total=` and the timestamp together to
tell genuine repeats from duplicated ones.

The line immediately above each one matters as much as the line itself:

```
Subgraph contains 381 nodes and 464 paths
Used 0.042 seconds
```

That is `SubgraphMC` timing itself from inside `subgraph_extract`. It is what let §6 split
the 30.077 s between the gbz query and `GenerateWalksMC`, and without it the stage would
still be unattributed.
