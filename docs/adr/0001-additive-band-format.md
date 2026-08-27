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

**C** — the path builder emits floats rather than strings, the binary body appears, and
`pgb`'s parser changes for the first time.

**D** — delete the `vg convert` / `vg view -j` round trip. Gated on measuring
`subgraph_extract` on the live server; if upstream extraction dominates, this is noise.

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
  MB. The matching *inputs* do not exist outside the live server and must be obtained; see
  [`docs/perf/deploy-request.md`](../perf/deploy-request.md).
- **`seqtubemap/tubemap.js` is declared a fork.** It is an unmarked 4,000-line vendored copy
  of `vgteam/sequence-tube-map`, carrying upstream's eslint header and no provenance. B
  removes its DOM sink, so the re-sync option is gone in fact; the header comment makes it
  gone on paper too.
