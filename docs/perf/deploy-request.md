# Deploy request — stage timing on the live API

A ready-to-send message asking whoever operates `pangenome-api.ucsd.edu` to deploy the
timing branch and return three log lines.

**Why this exists:** the `[stage-timing]` instrumentation is new code on
`perf/seqtubemap-diagnosis`. The live server cannot produce these numbers as it stands, so
the ask is "deploy this branch, hit three URLs, send a grep" — not "run something for me".

**Why not measure locally:** this machine is arm64 and `docker-compose.yml` pins
`platform: linux/amd64`, so a local container runs under x86 emulation. That inflates the
native binaries (`vg`, `gbz-base`) unevenly — exactly the stages being measured. Local
Docker is fine for developing the fix, not for timing it. See
[`seqtubemap-plan.md`](./seqtubemap-plan.md) Step 0.

Tone below is pitched as a peer asking a colleague. Adjust to fit.

---

**Subject: Small ask — deploy a logging-only branch to pangenome-api and send me three log lines?**

Hi —

I've been digging into why `/seqtubemap` is so slow, and I've got it narrowed down but I'm
stuck on one measurement I can't take from outside. Could I ask ~10 minutes of your time?

**What I've found so far:** a 10 kb region takes **120 seconds** and returns a **10 MB
SVG**. I've confirmed the SVG-rendering step is only ~1–2 s of that, so roughly **34
seconds is somewhere upstream** — in the gbz-base query, the GFA rewrite, `vg convert`, or
`vg view -j`. I can't tell which from outside the server, and that one fact determines where
the fix goes.

**The ask:** I've pushed a branch that adds timing instrumentation around each pipeline
stage:

```
perf/seqtubemap-diagnosis    (CAST-genomics/PangenomeAPI)
```

It's **logging only** — a context manager that records elapsed time, plus one log line per
request. No change to any output, response, or pipeline behaviour. The relevant commit is
`ab3e5b0`.

If you could deploy it and hit these three regions (deliberately chosen as ones nobody's
queried, so they don't hit the cached subgraph path):

```
https://pangenome-api.ucsd.edu:8000/seqtubemap?chrom=chr8&start=78900000&end=78900090&version=v2&pathnumoption=normal&nodewidthoption=compressed
https://pangenome-api.ucsd.edu:8000/seqtubemap?chrom=chr8&start=78910000&end=78913000&version=v2&pathnumoption=normal&nodewidthoption=compressed
https://pangenome-api.ucsd.edu:8000/seqtubemap?chrom=chr8&start=78920000&end=78930000&version=v2&pathnumoption=normal&nodewidthoption=compressed
```

…then send me the output of:

```sh
grep '\[stage-timing\]' <logfile>
```

Three lines, looking roughly like:

```
[stage-timing] chr8:78920000-78930000 span=10000bp v2 path=normal width=compressed
cached=False total=118.442s subgraph_extract=94.1s gfa_process=12.3s gfa_to_vg=4.8s
vg_to_json=6.1s generate_svg=1.2s json_mb=42.7 svg_mb=9.6
```

That's everything I need — I can take it from there.

**One heads-up:** the third request may take up to ~2 minutes, and while it runs the API is
unresponsive to everything else. That's not the instrumentation; it's an existing bug I
found (the endpoint is `async` but does blocking work, so one slow request stalls the event
loop). Worth running at a quiet time.

Happy to walk through any of this, or do the deploy myself if you'd rather give me access.

Thanks!

---

## Notes on sending

**The "logging only" claim is what gets this approved quickly, and it is accurate.** The
change wraps existing calls in `with` blocks and adds one `log.info`. If they want to
verify: `git show ab3e5b0 -- main.py` is a 65-line diff readable in a minute.

**Keep the access offer.** If the answer is yes, this favour stops being needed every time —
and inheriting this project, that access is worth having regardless.

**The three regions are chosen to be uncached.** `preprocess_gfa_subgraph` is the one
artifact the code caches, and a previously-queried region skips the most expensive upstream
step — which is why the original measurements showed 1,000 bp returning faster than 300 bp.
If these regions turn out to have been queried before, any three unqueried ones work; what
matters is that the log line reports `cached=False`.

## What to do with the reply

1. Paste the three lines into [`seqtubemap-latency.md`](./seqtubemap-latency.md), replacing
   the inferred split in §2 and closing §6.
2. Update the published artifact **by passing its URL** — publishing without it forks the
   link into a second artifact.
3. Re-rank the roadmap in [`seqtubemap-plan.md`](./seqtubemap-plan.md) Step 3 if the numbers
   disagree with the current ordering. In particular: if `subgraph_extract` dominates,
   deleting the `vg` round trip wins less than its effort suggests, and the work moves to
   how the `gbz-base` query is issued.
