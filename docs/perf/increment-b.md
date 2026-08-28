# Increment B — what deleting the browser actually bought

The before-and-after figures for
[#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22), measured on one machine
(Apple silicon, Node v26.7.0) on 2026-08-28. "Before" is commit `399db1e`, the last commit
with `jsdom` in it, measured in a worktree of its own with its own `node_modules`; "after" is
the same commands on the merge of #22.

**Both sides run the same harness.** `perf/rss-split.mjs` gained a call to
`reorderTracksForLayout` in this change, so that it renders what `render.mjs` renders; the
before-side copy was patched the same way before it was run. A comparison between a harness
that reorders and one that does not is a comparison of two different pictures, and the
reorder is worth a third of the bands (#46).

The baseline these are read against is
[`seqtubemap-latency.md`](./seqtubemap-latency.md) §1–9, which was taken on the server rather
than here. Absolute times differ; the ratios are what transfer.

## Retained memory

```sh
node --expose-gc --max-old-space-size=8192 perf/rss-split.mjs \
  perf/fixtures/split-400.json 0 8000 compressed
```

465 strands over 526 segments, 117,207 bands.

| | before | after |
| --- | ---: | ---: |
| retained by `create()` | 1,851.4 MB | **94.9 MB** |
| …of which the emulated document | 1,759.2 MB (**95.0%**) | — |
| …of which the layout | 92.2 MB | 94.9 MB |
| peak RSS | 2,446.5 MB | **472.5 MB** |
| document | 37,881,380 bytes, 235,624 elements | 32,278,102 bytes, **118,079** elements |

**The "after" cell for the document's share is a dash, not a zero.** There is no DOM to
weigh, and a share of zero would be arithmetic on an absence rather than an observation. What
`rss-split.mjs` reports instead is what it can see: nothing is left of `create()` but the
layout, and no `window` or `document` global exists on the far side of the render. The claim
that nothing *can* build one — no file the endpoint runs imports either package, on any input
— is asserted in `tests/node/document-conformance.test.mjs`.

The element count is the other half of the same story: half the elements in the old document
were the empty `<title>` on every band and every segment box.

## The fetch ceiling

The point of the increment, at **production's own heap size** — `main.py:509` spawns the
generator with `--max-old-space-size=8192`:

```sh
node --max-old-space-size=8192 seqtubemap/generate-svg.mjs \
  perf/fixtures/cross.json /tmp/out.svg 0 300000 compressed
```

| | |
| --- | --- |
| before | `FATAL ERROR: Ineffective mark-compacts near heap limit — JavaScript heap out of memory`, after 35.09 s |
| after | 240,007,196 bytes written, in **6.42 s** |

An input that could not be rendered at all now renders, at the same heap the server gives it.
`cross.json` is a synthetic 54 MB fixture rather than a region anyone has requested — the
regions that fail in production are not reproducible here, which is what #41 spent its
measurement establishing — but the failure mode is the one `pgb` sees, and the heap is the
real one.

The same shape at a 1 GB cap, which is the smaller and cheaper version of the demonstration:
`split-400.json` dies with the same error after 5.17 s before, and renders in 0.96 s after.

## Fixed per-request cost

The whole `node seqtubemap/generate-svg.mjs` process over the 13-segment, 90 bp smoke
fixture — the smallest request that exists, so what is being timed is almost entirely the
cost of starting up.

| | before | after |
| --- | ---: | ---: |
| first run (cold caches) | 0.98 s | **0.24 s** |
| warm, best of five | 0.56 s | **0.13 s** |
| warm, worst of five | 0.61 s | 0.15 s |

Roughly **440 ms off every request**, of any size. The server measured 722 ms of fixed cost
([`seqtubemap-latency.md`](./seqtubemap-latency.md) §2: 437.6 ms importing `jsdom` and
`canvas`, 109.0 ms constructing the DOM, 175 ms importing `tubemap.js`); this machine paid
less of it, and what is left after the change is Node's own start plus the `tubemap.js`
import.

`npm test` fell from 6.5 s to 1.8 s on the same hardware, which is the same saving seen 30-odd
times over.

## Payload

The three removals — `color=`, `class="track{id}"` and the empty `<title>` on every band and
every segment box — and nothing else.

| document | before | after | |
| --- | ---: | ---: | ---: |
| `small.svg` | 25,855 | 22,655 | −12.4% |
| `large.svg` | 792,449 | 672,078 | −15.2% |
| `small-normal.svg` | 30,585 | 27,385 | −10.5% |
| `small-pclai.svg` | 26,595 | 22,743 | −14.5% |
| 90 bp real subgraph | 173,958 | 139,493 | −19.8% |
| 600 bp | 2,831,503 | 2,364,524 | −16.5% |
| 1.4 kb | 4,551,321 | 3,782,189 | −16.9% |
| 8.0 kb | 12,480,853 | 10,456,403 | −16.2% |
| 4.2 kb (1,201 strands) | 15,806,046 | 13,186,960 | −16.6% |

−16.6% on the largest is exactly the figure #22 predicted from the measured `<title>` count.

**The diff was checked, not assumed.** Every document above was compared against its old bytes
with those three things textually deleted, and every one matched character for character — the
synthetic goldens through the CLI, the five real subgraphs through `renderTubeMap`. The
committed band-data baselines moved too, and by exactly one thing: an empty `"overlays":[]`,
which the collector now reports and which every real subgraph is (a real subgraph has no
reference offset, so it draws no ruler).

## `nodeWidthOption=normal`, checked separately

This is the one place the increment could have changed geometry, so it was measured rather
than reasoned about. That mode used to size a segment by writing its label into the emulated
document and asking for `getComputedTextLength`, which is the only thing `canvas` was ever
installed for; it now multiplies the glyph count by one monospace advance, 8.401 px at 14 px.

On this machine the two agree **exactly**: `small`'s input at `normal` is byte-identical
before and after, once the three removals are taken out — same 65 drawables, same 19 text
elements, same coordinates. node-canvas resolved Courier New here and Courier New's advance is
1229/2048 em, which is where 8.401 comes from.

What changed is what happens on a host that resolves the font differently, which is why the
mode had no golden before. It has one now: `small-normal.svg`, the only golden that carries
segment labels and the finer 20 bp ruler.

## What was not measured

The endpoint end to end. `generate_svg` is 8.2 s of a 38.9 s 10 kb request on the server, and
what changed here is the part of it that is not layout; confirming the request-level number
needs a deploy, and `release..main` is where that queue lives
([`releasing.md`](../releasing.md)).
