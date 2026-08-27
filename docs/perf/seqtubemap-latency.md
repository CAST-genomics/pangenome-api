# `/seqtubemap` latency and payload size

Performance diagnosis of the sequence tube map endpoint. Measured 2026-08-27 against the
live service at `pangenome-api.ucsd.edu:8000`, plus a local stage-timing harness
(Node v26.7.0, darwin 25.5.0).

- Rendered version: <https://claude.ai/code/artifact/71539dd1-fb13-44d0-8468-a3a96e726114>
- Source of the rendered version: [`seqtubemap-latency.html`](./seqtubemap-latency.html)
- Harness: [`perf/`](../../perf/)

**Headline:** a 10 kb region takes **120 seconds** and returns a **10 MB SVG** — and while
it does, it takes the entire API down for every other caller.

---

## 1. What the live API actually does

Five sequential requests against `chr8` from position 78,771,162, growing the region each
time. Everything else held constant: `version=v2`, `pathnumoption=normal`,
`nodewidthoption=compressed`.

| Region | TTFB | Bytes | Tracks | Elements |
| --- | ---: | ---: | ---: | ---: |
| 90 bp | 1.46 s | 177,593 | 464 | 1,201 |
| 300 bp | 7.87 s | 606,428 | 464 | 3,641 |
| 1,000 bp | 1.89 s | 1,300,847 | 464 | 7,553 |
| 3,000 bp | 35.33 s | 3,152,494 | 464 | 18,073 |
| **10,000 bp** | **120.40 s** | **10,071,688** | 464 | 57,225 |

Two readings matter.

**Track count never moves** — 464 at every region size, because that is the haplotype
count, and it multiplies everything downstream.

**Time is wildly nonlinear and noisy**: 1,000 bp came back faster than 300 bp. That
inversion is the one piece of caching in the system leaking through —
`preprocess_gfa_subgraph` is the only artifact checked with `.exists()`, so a
previously-touched region skips the most expensive upstream step.

## 2. Where the time is not

A local harness runs the Node half of the pipeline in isolation, mirroring
`generate-svg.mjs` stage for stage. On a synthetic graph of **36,106 elements** — twice
the size of the real 3,000 bp response — the entire Node stage completes in **1.44 s**:

```
[stage] import:jsdom+canvas    437.6ms  rss=154MB
[stage] jsdom:construct-dom    109.0ms  rss=179MB
[stage] import:tubemap.js      175.6ms  rss=208MB
[stage] io:read-input            0.4ms
[stage] parse:JSON.parse         4.5ms
[stage] convert:vgExtractNodes   0.1ms
[stage] convert:vgExtractTracks  0.7ms
[stage] render:create()        647.2ms  rss=468MB
[stage] serialize:outerHTML     48.4ms
[stage] io:write-svg             9.8ms
                       total 1441.7ms
```

The server spent **35.3 s** producing a *smaller* graph than this. So the SVG generation
stage is roughly **1–2 seconds of it**, and on the order of **34 seconds sits upstream** —
in `gbz-base` subgraph extraction, `SeqTubeGfaProcessor`, `vg convert`, and `vg view -j`.

> This split is **inferred by subtraction, not directly measured.** See §6.

Note the first three lines: **722 ms is fixed cost** — booting JSDOM, node-canvas, and
importing 130 KB of `tubemap.js` — paid on every request no matter how small the region.

## 3. Findings

### One slow request takes down the whole API — *measured*

`seqtubemap` is declared `async def`, but every call inside it is blocking: four
synchronous `subprocess.run` invocations plus the gbz extraction. That blocks the FastAPI
event loop outright.

Confirmed by accident: four unrelated requests issued while the 120 s call was in flight
**all failed with no HTTP status at all**, then succeeded immediately once it finished.
Concurrent requests don't queue, they die.

*`main.py:452`; blocking calls at `:250`, `:273`, `:293`*

### Path aggregation is implemented, but effectively never fires — *measured*

`pathnumoption=compressed` groups haplotypes into `path_summary` keyed on `walk_update` —
**the entire node traversal across the whole region, as one string**. Two haplotypes
collapse only if their walks are byte-identical end to end, so a single SNP anywhere in the
window keeps them apart.

At 1,000 bp, `compressed` and `normal` returned **byte-identical 1,300,847-byte
responses**: nothing collapsed.

This is aggregation at the wrong granularity. Collapsing tracks that agree *between branch
points*, rather than across the entire walk, is what would actually merge those 464 lanes —
and is closer to what a tube map is meant to draw.

*`main.py:212–226`*

### Most of the payload is repeated strings, not geometry — *measured*

In the real 90 bp response:

| Component | Bytes | Share |
| --- | ---: | ---: |
| `style=` attributes | 25,163 | 14% |
| `trackName=` attributes | 24,632 | 13% |
| `d=` path geometry | 14,522 | 8% |

`style=` is `fill: rgb(211, 211, 211); fill-opacity: 1;` written out hundreds of times.
`trackName=` is each track's full name — e.g. `NA20806#1#CM102444.1#0[80060344-80060632]` —
duplicated per element. Element counts: 599 `<title>`, 517 `<rect>`, 82 `<path>`, 2 `<g>`,
1 `<svg>`.

### A browser is emulated server-side to emit XML — *measured*

To run the browser visualization component on the server, `generate-svg.mjs` stands up a
full JSDOM document with `pretendToBeVisual: true`, plus a node-canvas instance whose only
job is backing a monkey-patched `getComputedTextLength` for text measurement — then
discards all of it and takes `.outerHTML` as a string.

Nothing is rasterized; the cost is DOM emulation, and it is the **722 ms fixed floor** on
every request.

Caveat: the layout math in `create()` is real work that has to happen somewhere. What is
gratuitous is routing it through a DOM — not that it happens.

*`seqtubemap/generate-svg.mjs`*

### Result caching is not the fix — *ruled out*

The code deletes every intermediate *and the finished SVG* after each response, so
identical repeat requests recompute from scratch — 3.18 s then 3.01 s for the same region.

That looks like an easy win, but scientists poke arbitrary nodes across a loaded graph and
rarely repeat a specific retrieval, so a cache would almost never hit. **Ruled out on
access-pattern grounds** — recorded here because the deletion looks like obvious dead
weight to anyone reading the code cold.

*`main.py:485`*

## 4. Why 464 lanes is the multiplier

Every haplotype gets its own ~15 px row regardless of whether it differs from its
neighbours anywhere in the window. At 90 bp that produces a **7,080 px-tall** image; at
10 kb it produces 57,225 elements.

A local sweep holding tracks at 464 while growing the graph:

| Spine nodes | `create()` | SVG | Elements | Peak RSS |
| ---: | ---: | ---: | ---: | ---: |
| 40 | 656 ms | 4.92 MB | 38,167 | 514 MB |
| 150 | 1,975 ms | 15.49 MB | 119,053 | 1,222 MB |
| 600 | 7,662 ms | 57.32 MB | 441,121 | 3,879 MB |
| **2,400** | **OOM** | — | — | **6 GB heap exhausted** |

These are synthetic graphs and diverge more than real haplotypes do, so treat the absolute
numbers as an upper bound. The shape is the point: **memory, not CPU, is what ends the
run.**

## 5. The harness

Four files in [`perf/`](../../perf/). No genomics toolchain required — they exercise the
JSON→SVG boundary directly, so none of `data.path`, `tools.path`, or the HPRC graph files
need to be provisioned.

| File | Purpose |
| --- | --- |
| `gen-vg-json.mjs` | Deterministic synthetic vg JSON: reference spine, bubbles, haplotypes. Tunable `spineNodes`, `haplotypes`, `bubbleRate`, `altFreq`, `seqLen`, `seed`. |
| `stage-timer.mjs` | Mirrors `generate-svg.mjs` stage for stage, timing each and measuring output composition. Runs as its own process because `tubemap.js` holds module-level layout state. Emits progress to stderr so a crash still names the stage that died. |
| `bench.mjs` | Sweeps one graph dimension at a time; `--input=real.json` takes a real fixture. |
| `cross.mjs` | The tracks × nodes cross term, which is the case that matters. |

```sh
node perf/stage-timer.mjs <input.json> <out.svg> <start> <end> <nodeWidthOption>
node perf/bench.mjs --axis=spine
SPINES=40,150,600 HAPS=464 ALT=0.08 node perf/cross.mjs
```

`perf/fixtures/` is gitignored — the sweeps generate hundreds of MB.

## 6. The one gap, and how to close it

The ~34 s upstream figure in §2 is **inferred by subtraction**. Everything else in this
document is a direct observation.

Server-side stage timers are now in place (`stage_timing()` in `main.py`, wrapping all five
pipeline calls). Each request emits one greppable line:

```
[stage-timing] chr8:78771162-78781162 span=10000bp v2 path=normal width=compressed
cached=False total=118.442s subgraph_extract=94.1s gfa_process=12.3s gfa_to_vg=4.8s
vg_to_json=6.1s generate_svg=1.2s json_mb=42.7 svg_mb=9.6
```

*(Illustrative values — the real ones are what we're after.)*

```sh
grep '\[stage-timing\]' <logfile>
```

`cached=` reports whether `preprocess_gfa_subgraph` already existed, which is what caused
the 1000 bp-faster-than-300 bp inversion above; without it the numbers are uninterpretable.
`json_mb`/`svg_mb` are captured before the background delete task fires.

Capture a spread — 90 bp, 3 kb, 10 kb — each against a **fresh region** so `cached=False`,
because the cached path skips the stage most likely to dominate. That result either confirms
the ~34 s upstream inference or overturns it, and tells you whether the first real fix
belongs in `gbz-base` extraction or the `vg` conversion hop.

---

*Live-API timings are single samples on a shared service and carry real variance. The local
harness is deterministic and repeatable.*
