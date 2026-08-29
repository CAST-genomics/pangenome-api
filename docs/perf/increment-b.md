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

## Over HTTP, through the real endpoint

Everything above is measured below HTTP. The same before-and-after was then run through two
isolated API instances on ports 8100 and 8101 — real FastAPI handler, real caching branch,
real Node subprocess — serving the five committed subgraphs. The method, and the one stand-in
that limits what it proves, are in
[`local-endpoint-harness.md`](./local-endpoint-harness.md).

| region | TTFB before | TTFB after | speedup | bytes before | bytes after | change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 90 bp | 0.646 s | **0.213 s** | 3.0× | 166,675 | 138,340 | −17.0% |
| 600 bp | 0.982 s | **0.278 s** | 3.5× | 2,738,884 | 2,352,410 | −14.1% |
| 1.4 kb | 1.226 s | **0.331 s** | 3.7× | 4,391,887 | 3,757,885 | −14.4% |
| 8.0 kb | 2.376 s | **0.735 s** | 3.2× | 12,090,267 | 10,408,507 | −13.9% |
| 4.2 kb | 2.561 s | **0.589 s** | 4.3× | 15,285,418 | 13,122,049 | −14.2% |

All five response bodies are byte-identical to the pre-#22 ones once the three removals are
deleted, with unchanged drawable counts, and all five satisfy `pgb`'s parsing contract. The
endpoint's own stage timer puts the whole saving in `generate_svg` — every other stage is
unchanged.

The reductions are ~14% rather than ~16.6% because these requests carry no `minigraphnode`, so
every PCLAI attribute is the short literal `None`.

## Checked against `pgb`'s own parser

Everything above tests the document against *this* repository's statement of what `pgb`
requires. On 2026-08-28 that statement was replaced by the real thing: `pgb` is checked out
alongside, and `src/tubemap/parseBands.ts` and `parseSegmentBoxes.ts` were run directly over
the five real subgraphs rendered by both the pre- and post-#22 code.

**All five accepted, before and after.** And more than accepted — `pgb` recovers *bit-identical
arrays* from the two sides:

| fixture | bands | strands | geometry floats | recovered arrays |
| --- | ---: | ---: | ---: | --- |
| chr8 90 bp | 592 | 464 | 3,552 | identical |
| chr1 600 bp | 8,089 | 369 | 48,534 | identical |
| chr8 1.4 kb | 13,246 | 463 | 79,476 | identical |
| chr1 8.0 kb | 35,020 | 383 | 210,120 | identical |
| chr1 4.2 kb | 44,795 | 1,201 | 268,770 | identical |

Compared element by element: `geometry`, `strandIds`, `bandDirections`, `bandCount`,
`strandColors`, `strandNames`, `strandPlacements`, `strandScores`, `strandCount`, `content`,
`centre`, and the segment boxes from `parseSegmentBoxes`. This is the bar the roadmap names as
the strongest available — *"run the client's own parser over before and after, and diff the
recovered arrays"* — met with the client's own code rather than a description of it.

Two things came out of reading that parser, both recorded rather than acted on here:

- `tests/node/pgb-parser.mjs` **was looser than the real gate** and has been tightened to
  match. It had made `fill-opacity` and `trackName` optional; `pgb` requires both, literally.
- A reversal draws shapes `pgb` cannot read at all, and its whole-document gate then refuses
  the document rather than degrading it. Latent — no committed fixture draws a corner — and it
  predates #22 in both directions. Filed as
  [#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52).

## Rendered, and looked at

Everything above establishes that the documents are *correct* — the right bytes, and arrays
`pgb` recovers identically from both sides. None of it establishes that they *render*, which
is the one thing a byte comparison cannot reach.

On 2026-08-29 all five real subgraphs were rendered on a developer machine with
`npm run render:fixtures` — no server, no graph data, no `vg`, no Docker — and the resulting
documents loaded into `pgb`'s static-document dev harness.

| document | bytes | strands | bands | render |
| --- | ---: | ---: | ---: | ---: |
| chr8 90 bp | 138,340 | 464 | 592 | 0.12 s |
| chr1 600 bp | 2,352,410 | 369 | 8,089 | 0.07 s |
| chr8 1.4 kb | 3,757,885 | 463 | 13,246 | 0.11 s |
| **chr1 8.0 kb** | **10,408,507** | 383 | 35,020 | **0.38 s** |
| **chr1 4.2 kb, 1,201 strands** | **13,122,049** | 1,201 | 44,795 | **0.27 s** |

Each was also rendered with its PCLAI colour scheme, the argument production passes whenever
`minigraphnode` is set; those are 0.1-0.6% larger and are the variants a real node click
produces.

**The two at the fetch ceiling render correctly.** Those are the bold rows — the regime #13
exists for, and the sizes that fail in production. Confirmed visually, not by diff.

This closes the correctness argument for #22 at both ends of the size range. It says nothing
about production latency: these render in tenths of a second here because nothing local pays
for extraction, and because the heap failure mode is gone. What a researcher actually
experiences still depends on the deploy — `release..main` is where that queue lives
([`releasing.md`](../releasing.md)).

## What was not measured

The endpoint on the server. `generate_svg` is 8.2 s of a 38.9 s 10 kb request there, against a
graph this machine does not have and through a `vg` this machine cannot run; confirming the
production number needs a deploy, and `release..main` is where that queue lives
([`releasing.md`](../releasing.md)).
