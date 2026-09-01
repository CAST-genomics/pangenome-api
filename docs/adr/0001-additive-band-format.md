---
status: accepted
date: 2026-08-27
measured: 2026-08-27
---

# `/seqtubemap` gains a band format alongside the SVG, and the band data becomes canonical

The endpoint renders a **sequence tube map** by booting a headless browser, building a
jsdom document and serializing it to XML — so that its one consumer, `pgb`, can parse the
XML back into the numbers the layout already held. Measurement says that emulation is
**93.7% of the memory** and roughly half the bytes. We are adding `?format=bands`, which
returns those numbers directly, and inverting which of the two is the source of truth: the
band data becomes canonical and the SVG becomes a rendering of it.

The format is **additive**. The existing URL keeps returning SVG, so the API and `pgb` never
have to deploy in lockstep, and the SVG remains the oracle the band payload is checked
against.

## The measurements

Four, all taken 2026-08-27 and reproducible from [`perf/`](../../perf/). The full write-up
is [`docs/perf/seqtubemap-latency.md`](../perf/seqtubemap-latency.md).

**The DOM is the memory, not the layout.** `perf/rss-split.mjs` marks retained heap either
side of `tubemap.js`'s `create()`, then tears the document down and marks again. What the
DOM releases is what the DOM was holding:

| fixture | `create()` retained | DOM share | layout share |
| --- | ---: | ---: | ---: |
| spine 150 × 464 strands | 567.6 MB | **530.7 MB (93.5%)** | 36.9 MB |
| spine 400 × 464 strands | 1522.7 MB | **1427.5 MB (93.7%)** | 95.2 MB |

The layout is ~15× smaller than the document built to hold it, and holds no DOM references.
This is why large nodes cannot be fetched at all: roughly 43% of catalogued nodes fail, and
the ceiling is the DOM.

**Between 41% and 47% of every response is redundancy.** Byte census over the five golden
documents in `pgb`'s `src/tubemap/__tests__/fixtures/`:

| | 90 bp | 600 bp | node 5520 (13.56 MB) |
| --- | ---: | ---: | ---: |
| `d=` — the geometry | 15.0% | 28.1% | 29.9% |
| `style=` — one of ~464 rgb triples | 16.4% | 14.5% | 14.2% |
| `trackName=` — one of ~464 names | 11.4% | 10.3% | 10.1% |
| `color=` — *the same rgb as `style`, written twice* | 8.6% | 7.6% | 7.5% |
| `class="track{id}"` — the same integer as `trackID` | 5.4% | 4.8% | 4.8% |
| `<title></title>` — empty, 40,716 of them | 5.0% | 4.4% | 4.3% |
| **redundant** | **46.9%** | **41.5%** | **40.8% (5.53 MB)** |

Everything but `d=` is either a per-strand constant re-serialized on every band, or carries
nothing at all. The geometry — the only genuinely per-band content — is under a third of the
payload.

**There are zero `<text>` and zero `<line>` elements in production output.** No labels, no
legend, no axis. The document is bands and segment boxes and nothing else, which is what
makes "derive the SVG from the band data" lossless rather than a compromise.

**The geometry never needed a DOM.** At `seqtubemap/tubemap.js:3599` the `d` attribute is
bound as `(d) => d.path` — already a complete `"M … C … Z"` string, computed before any
element exists. jsdom's entire contribution is to hold that string and hand it back.

## What is served

`?format=bands` returns a JSON header and a binary body in one response:

- **header** — the viewBox, and the ~464-row strand table: `trackID`, rgb, `trackName`,
  `pclaiX/pclaiY/pclaiScore`. Transmitted once instead of once per band.
- **body** — `Float32 × 6 + Uint16` per band. `pgb` builds `InstancedBufferGeometry` from
  typed arrays, so this is a copy into the GPU buffer with no parse step at all.
- **segment boxes** — id, outline, sequence, which `parseSegmentBoxes.ts` reads today.

At the 10 kb region that is roughly **1.5 MB against the SVG's 10.07 MB**, with the client's
regex pass deleted rather than shrunk.

## How it lands

Four increments, each shippable alone.

**A** — the two endpoints are `async def` (`main.py:470`, `:527`) and neither awaits
anything; every pipeline stage is a blocking `subprocess.run`, so one slow request stalls
every concurrent one. FastAPI runs a plain `def` endpoint in a threadpool. Deleting the word
`async` twice is the fix, and it fixes `/json` at the same time.

**B** — capture the d3 data joins instead of appending, derive the SVG from the band data,
and delete `jsdom` and `canvas` from `package.json`. **B is held byte-compatible with
`pgb`'s existing parser as a deliberate constraint, not a coincidence** —
`parseBands.ts` requires `style="fill: rgb(R, G, B); fill-opacity: 1;" trackID="N"
trackName="…"` contiguous and in that order, and counts `<rect>` + `<path>` in `g.track`.
Dropping `color=`, `class=`, and the empty `<title>` children changes none of that. So B is
a server-only change against an unchanged client, and `pgb` becomes its conformance test: a
bad B shows up as an error card rather than as a diff nobody ran.

> *Amended 2026-08-28: **B has landed**, and the constraint held.* The layout collects its
> numbers into `seqtubemap/band-data.mjs` and `seqtubemap/emit-document.mjs` writes the
> document from them; `jsdom` and `canvas` are gone from `package.json`, and no file the
> endpoint runs imports either. The three removals are exactly the three named above and
> nothing else: every committed golden and all five real subgraphs were checked to be
> byte-identical to their old documents with `color=`, `class="track{id}"` and
> `<title></title>` deleted, which is **16.2-19.8%** of the payload. The numbers this
> predicted, measured: retained memory in `create()` **1,851.4 MB → 94.9 MB** and peak RSS
> **2,446.5 MB → 472.5 MB** on `perf/fixtures/split-400.json`, where 95.0% of the before-side
> figure was the emulated document and the after-side figure is all layout; the smallest
> possible request **0.56 s → 0.13 s** warm; and `perf/fixtures/cross.json`, which died with
> `heap out of memory` at production's own 8 GB heap, now renders a 240 MB document in 6.4 s.
> The record is [`docs/perf/increment-b.md`](../perf/increment-b.md).

**C** — the path builder emits floats rather than strings, the binary body appears, and
`pgb`'s parser changes for the first time.

> *Amended 2026-08-31: **C's first half has landed** ([#23](https://github.com/CAST-genomics/PangenomeAPI/issues/23)).*
> The layout no longer builds a `d` attribute: `seqtubemap/band-data.mjs` collects the six
> numbers it encoded — `x0, y0, x1, y1` and the two control abscissae — and
> `emit-document.mjs` writes the drawing command out of them. The thickness is the constant
> this ADR's survey found, said once rather than on every band, and a band of any other
> thickness now throws where the layout that drew it is still in scope rather than reaching
> a client that would refuse the whole document. **Output did not move**: all four goldens
> and all five real subgraphs are byte-identical, and so is the synthetic reversal, so the
> golden tests took no re-baselining. The band-data baselines were re-baselined, deliberately,
> because they are what pins the representation that changed. The wire format and the
> `format` parameter are still to come, in
> [#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24), and that is where `pgb`'s
> parser changes.
>
> Two shapes are outside the six-value grammar and are collected as their own kinds rather
> than forced into it: a reversal's **corners**, built from quadratics, and its **vertical
> connectors**, which are as tall as the reversal is deep. `pgb` cannot read either one
> today — that is [#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52), which
> predates this — and #24 is where what they mean on the band route gets decided.

> *Amended 2026-09-01: **C has landed** ([#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24)).*
> `/seqtubemap?format=bands` returns a JSON header and a binary body; the format is
> specified in [`docs/band-format.md`](../band-format.md), written to be enough to write a
> parser against without reading the server. Omitting the parameter returns the document
> byte for byte, and an unrecognised `format` is refused with a 400 before any stage runs
> rather than quietly served as SVG.
>
> **The projection was right and slightly pessimistic.** This ADR predicted "roughly 1.5 MB
> against the SVG's 10.07 MB" from the band count and the record width. The nearest thing
> that can be measured from a checkout is the committed 7,967 bp subgraph, whose document is
> 9.97 MB — a document of the size the projection was about, rather than a region of the span
> it named — and its payload is **1.25 MB**. The five real subgraphs run
> 1.9× at 90 bp to 9.0× at 44,795 bands, and the ratio is smallest where the response is
> smallest: the 90 bp region draws 592 bands over 464 strands, so its payload is almost all
> strand table. `perf/band-payload-sizes.mjs` reproduces the table.
>
> Three decisions the ADR left open, and how they went:
>
> * **The body is columnar, not one interleaved record per band.** Interleaved, the record
>   is 26 bytes, and a `Float32Array` cannot be viewed over a buffer at an offset that is
>   not a multiple of 4 — so a client would have to copy the fields apart one at a time,
>   which is the parse step this whole change exists to delete. Split into a float32
>   column, a uint16 column and a uint8 column, each is one view over the bytes that
>   arrived, and the geometry column *is* the instance buffer.
> * **A strand's colour travels as three whole channels**, not as CSS. The layout spells a
>   colour two ways and a PCLAI scheme can supply fractional channels — the live chr7
>   failure of 2026-08-28 — so the rounding happens once, on the server, in the same
>   function the document rounds with.
> * **The reversal shapes ride in the header, not the body** ([#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52)),
>   each carrying the position it held in the draw order, because paint order is document
>   order. No production response contains one, and a client may reasonably refuse a
>   response whose `reversals` are non-empty rather than implement two shapes it will not
>   meet. This is what #24 was to decide, and it decides it without asking `pgb` to grow
>   anything.
>
> One byte per band is carried beyond the ticket's record: which element the document draws
> the band as. A client can ignore it — the six numbers are the whole shape either way —
> and it is what makes the SVG reconstructible from the payload, so *"the band data is
> canonical and the document is a rendering of it"* is a fact the tests check rather than
> an intention.

**D** — delete the `vg convert` / `vg view -j` round trip. Gated on measuring
`subgraph_extract` on the live server; if upstream extraction dominates, this is noise.

> *Amended 2026-08-27, after the measurement.* Upstream does dominate — `subgraph_extract` is
> 77% of a 10 kb request, and the `vg` round trip is **1.6%**. D is noise as a performance
> item, and stands only as a provisioning and architecture cleanup. The upstream cost turned
> out to be `GenerateWalksMC` rather than `gbz-base`, which is a new increment outside this
> ADR; see [the plan](../perf/seqtubemap-plan.md).

## Considered and rejected

**Mutating the existing URL in place** — hoisting the per-strand constants out of every band
without adding a format. Cheaper to write and strictly worse to ship: the two repos would
have to deploy in lockstep, and it buys a byte reduction without touching the DOM that
causes the ceiling.

**Replacing SVG outright.** Loses the oracle at exactly the moment it is needed, and there
is no reason to force the client to move before it is ready.

**Two sinks over one layout** — the SVG sink and a band collector side by side. Keeps jsdom
alive forever for a route nobody calls, and makes drift a matter of discipline. Deriving one
from the other makes drift impossible by construction.

**JSON rather than a binary body.** Roughly 3–4 MB where binary is 1.5 MB, and it keeps a
full parse on the client that typed arrays remove entirely.

**Carrying `pathnumoption` onto the band route.** `pathnumoption=compressed`
(`main.py:212–226`) keys on the entire walk across the region, so one SNP prevents any
collapse — measured byte-identical to `normal` at 1000 bp. Fixing it would merge strands,
which is a change to the *data* and out of scope. It stays as-is on the SVG route and does
not exist on the band route; carrying a parameter that has never changed an output into a
new format is how dead code becomes permanent.

## Consequences

- **`pgb`'s ADR 0002 loses its largest accepted cost.** That decision accepted being
  *"coupled to an upstream at the level of drawing primitives"* — reading `d` attributes
  against a path grammar and rebuilding the picture from inferred numbers. Once the server
  publishes the numbers, the inference is gone. ADR 0002 is amended rather than left
  contradicted.
- **The band data is canonical.** Where the two encodings disagree, the SVG is wrong.
- **Correctness is `parseBands`-equivalence, not byte-identity** — except in B, where
  byte-compatibility is the constraint that lets the repos move independently.
- **Golden fixtures**: `pgb` already commits five real documents spanning 0.29 MB to 13.56
  MB. The matching *inputs* were obtained from the live server on 2026-08-27 and are
  committed at [`tests/fixtures/seqtubemap/`](../../tests/fixtures/seqtubemap/), matched to
  their outputs on strand count. **B's oracle is end-to-end.**
- **`seqtubemap/tubemap.js` is declared a fork.** It is an unmarked 4,000-line vendored copy
  of `vgteam/sequenceTubeMap`, carrying upstream's eslint header and no provenance. B
  removes its DOM sink, so the re-sync option is gone in fact; the header comment makes it
  gone on paper too. *As of B this is past tense: the DOM sink is removed.*
- **The document carries a handful of elements that are not bands.** The ruler — an axis,
  its ticks and their labels — and, in `nodeWidthOption=normal`, one text label per segment.
  They are not band data, so the collector keeps them as `overlays`: an element name and its
  attributes, in document order. Production documents contain none of them, because a real
  subgraph carries no reference offset; they exist so that the synthetic fixtures, which do,
  still render. `?format=bands` has no reason to carry them.
- **`nodeWidthOption=normal` measures its labels arithmetically.** It used to write the label
  into the emulated document and ask for `getComputedTextLength`, which is the only thing
  `canvas` was ever installed for. The label is set in a monospace face, so the width is the
  glyph count times one advance — 8.401 px at 14 px, the same constant the other width modes
  already use. It also makes that mode deterministic across machines, which it was not
  before: it depended on which fonts the host had.
