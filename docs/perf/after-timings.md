# After the stage timings come back

Follow-ups for me, once Cici returns the log from
[`deploy-request.md`](./deploy-request.md).

- Fill in §2 and close §6 of [`seqtubemap-latency.md`](./seqtubemap-latency.md), where the
  ~34 s upstream figure is currently marked as inferred by subtraction rather than measured.
- Re-rank increment **D** in [`seqtubemap-plan.md`](./seqtubemap-plan.md) — it's the only
  one gated on this. A-C are correct regardless of where the upstream time goes.
- Update the rendered report **by passing its URL**
  (`https://claude.ai/code/artifact/71539dd1-fb13-44d0-8468-a3a96e726114`); publishing
  without it forks the link into a second artifact.

## Reading the log

Each `/seqtubemap` request prints one line. To pull them out of whatever she sends:

```sh
grep '\[stage-timing\]' seqtubemap-log.txt
```

Shape of a line:

```
[stage-timing] chr8:78900000-78900090 span=90bp v2 path=normal width=compressed
cached=False total=8.412s subgraph_extract=6.1s gfa_process=1.2s gfa_to_vg=0.4s
vg_to_json=0.5s generate_svg=0.2s json_mb=0.4 svg_mb=0.3
```

Check `cached=False` on all three before trusting them — a cached subgraph skips
`subgraph_extract`, which is the stage in question. If any line says `cached=True`, that
region had been requested before and needs re-running at shifted coordinates.
