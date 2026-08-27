# The ask for Cici — one deploy, two things to send back

Two things are needed from the live server before the `/seqtubemap` work can be verified,
and both come from the same deploy, so they go in one message rather than two.

1. **Stage timings for three fresh regions** — the last unmeasured number in the effort.
2. **The pipeline intermediates for five regions** — the missing half of the golden
   fixtures.

**Why this can't be done locally.** This machine is arm64 and `docker-compose.yml` pins
`platform: linux/amd64`, so a local container runs under x86 emulation — which inflates the
native binaries (`vg`, `gbz-base`) unevenly, and those are exactly the stages being
measured. Local Docker is fine for *developing* the fix, not for timing it. Separately, the
three `.walk.gz` files are team-generated derivatives rather than public HPRC downloads, and
the server won't boot without all three.

**Status.** PR [#12](https://github.com/CAST-genomics/PangenomeAPI/pull/12) carries the
`[stage-timing]` instrumentation. It is logging only — no behaviour change — and the diff is
reviewable in a minute (`git show ab3e5b0 -- main.py`). The message below is a comment on
that PR, or a Slack message pointing at it; it is written as a peer asking a colleague, so
adjust the tone to taste.

---

**Subject: Two things off one deploy — stage timings + five fixture dumps**

Hi Cici —

I've been digging into why `/seqtubemap` is slow and I've got it down to one unmeasured
number plus one missing artifact. Both come off the same deploy, so I've bundled them.
Maybe 15 minutes of your time.

**What I've found.** A 10 kb region takes **120 seconds** and returns a **10 MB** SVG. Two
measurements say where most of that goes:

- **93.7% of the render's memory is the jsdom document**, not the layout — measured by
  tearing the DOM down and watching what's released, at two fixture sizes. That's why big
  nodes can't be fetched at all; the ceiling is the DOM.
- **41–47% of every response carries no information** — measured across five real documents
  from 0.29 MB to 13.6 MB. Per-strand constants re-serialized on every band, `color=`
  duplicating the rgb already in `style=`, `class=` duplicating `trackID`, and 40,716 empty
  `<title>` elements in one document.

The plan is in
[`docs/adr/0001-additive-band-format.md`](https://github.com/CAST-genomics/PangenomeAPI/blob/perf/seqtubemap-diagnosis/docs/adr/0001-additive-band-format.md).
Short version: `/seqtubemap` gains `?format=bands` that returns the numbers directly. It's
**additive** — the existing URL keeps returning SVG, unchanged, so nothing has to deploy in
lockstep. There's also a two-word fix I'd like to land first, separately: both endpoints are
`async def` and neither awaits anything, so one slow request currently stalls every
concurrent one. Deleting the word `async` twice makes FastAPI run them in a threadpool. That
one helps `/json` as much as `/seqtubemap`.

**Ask 1 — deploy PR #12 and send me a grep.** It's logging only; it adds one line per
request. Then hit three URLs, each against a **fresh region** so `cached=False` — the cached
path skips the stage I most suspect:

```
https://pangenome-api.ucsd.edu:8000/seqtubemap?chrom=chr8&start=78900000&end=78900090&version=v2&pathnumoption=normal&nodewidthoption=compressed
https://pangenome-api.ucsd.edu:8000/seqtubemap?chrom=chr8&start=78910000&end=78913000&version=v2&pathnumoption=normal&nodewidthoption=compressed
https://pangenome-api.ucsd.edu:8000/seqtubemap?chrom=chr8&start=78920000&end=78930000&version=v2&pathnumoption=normal&nodewidthoption=compressed
```

Then:

```sh
grep '\[stage-timing\]' <logfile>
```

Fair warning: the 10 kb one will hold the API for around two minutes. That's the
event-loop bug above, not something the instrumentation introduced — but pick a quiet
moment.

Three lines is all I need. They tell me whether the time is in the `gbz-base` query, the GFA
rewrite, or the `vg` hop, and that decides whether one of the four planned changes is worth
doing at all.

**Ask 2 — the intermediates for five regions.** `pgb` has five committed golden tube maps,
but only the *outputs*. To test the server end-to-end I need what produced them: the
`postprocess_gfa_subgraph` (or the vg JSON, either works) for:

| region | size |
| --- | ---: |
| `chr8:78,771,162-78,771,252` | 0.29 MB |
| `chr1:25,331,046-25,331,646` | 3.37 MB |
| `chr8:10,079,054-10,080,461` | 3.97 MB |
| `chr1:25,301,271-25,309,238` (node 5514) | 12.92 MB |
| `chr1:25,331,646-25,335,796` (node 5520) | 13.56 MB |

Any way you can get them to me is fine. With those, `pgb`'s existing fixtures become a real
end-to-end test and I can verify the rework against known-good output rather than against
my own synthetic data.

Happy to jump on a call and do the deploy together if that's easier than doing it
asynchronously.

Thanks —
Doug

---

## When the timings come back

- Fill in §2 and close §6 of [`seqtubemap-latency.md`](./seqtubemap-latency.md), where the
  ~34 s upstream figure is currently marked as inferred by subtraction rather than measured.
- Re-rank increment **D** in [`seqtubemap-plan.md`](./seqtubemap-plan.md) — it's the only
  one gated on this. A-C are correct regardless of where the upstream time goes.
- Update the rendered report **by passing its URL**
  (`https://claude.ai/code/artifact/71539dd1-fb13-44d0-8468-a3a96e726114`); publishing
  without it forks the link into a second artifact.
