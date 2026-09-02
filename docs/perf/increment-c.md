# Increment C — what publishing the numbers actually bought

The before-and-after for [#23](https://github.com/CAST-genomics/PangenomeAPI/issues/23) and
[#24](https://github.com/CAST-genomics/PangenomeAPI/issues/24), and the record of 2026-09-02,
the day `pgb` read the format off the live server.

Companion to [`increment-b.md`](./increment-b.md), which is the same document for **B**. B
deleted the browser without changing a byte of the response; C changed the response and did
not touch the layout. That split is deliberate — it is why #23 could come out byte-identical,
with B's own output as its oracle.

The state is tagged: **`increment-c`**, annotated, on `origin`, at `f9b05f6`.
`git tag -n99 increment-c` is the short version of this document.

## What the response became

Measured with `perf/band-payload-sizes.mjs` over the five committed real subgraphs on
2026-09-02, after #66 took the segment outlines out of the header.

| region | span | bands | SVG | band payload | ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| chr8:78,771,162-78,771,252 | 90 bp | 592 | 0.13 MB | 0.07 MB | 1.9× |
| chr1:25,331,046-25,331,646 | 600 bp | 8,089 | 2.25 MB | 0.27 MB | 8.5× |
| chr8:10,079,054-10,080,461 | 1.4 kb | 13,246 | 3.61 MB | 0.41 MB | 8.8× |
| chr1:25,301,271-25,309,238 | 8.0 kb | 35,020 | 9.97 MB | **1.10 MB** | 9.0× |
| chr1:25,331,646-25,335,796 | 4.2 kb | 44,795 | 12.58 MB | 1.35 MB | 9.3× |

**The projection was right and slightly pessimistic.** ADR 0001 predicted ~1.5 MB against
10.07 MB on the 8.0 kb subgraph; the measurement is 1.10 MB against 9.97 MB.

**The ratio is smallest where the response is smallest**, which is not a disappointment but
the format working as designed: a 592-band payload is almost all strand table, and the strand
table is the part that does not shrink with the picture. 464 rows are 0.05 MB whether they
describe 592 bands or 44,795. The saving is per-band, so it arrives in proportion to the
bands — which is exactly the regime where the old format was unusable.

**Where the bytes now sit**, on the 8.0 kb subgraph: 0.20 MB of header (768 segment boxes at
0.16 MB, the 383-row strand table at 0.05 MB) and 0.90 MB of body. The body is three typed
columns — `Float32 × 6`, `Uint16`, `Uint8` per band — and the geometry column is `pgb`'s GPU
instance buffer with no parse step at all.

### What #66 moved

A segment box travelled as the path command that draws it. Replacing it with the five numbers
behind it took the 8.0 kb header from 0.35 MB to 0.20 MB and the whole response from 1.25 MB
to 1.10 MB — 8.0× to 9.0×. Less than the 0.21 MB the outlines cost, because five keys and five
doubles are 0.06 MB of it.

That was the **last string in the payload a client had to parse back into numbers**, which is
the whole increment's argument applied one level down from the bands.

## What did not move

**#23 changed no bytes at all.** All four goldens, all five real subgraphs and the synthetic
reversal came out byte-identical, so the golden tests took no re-baselining. The band-data
baselines *were* re-baselined deliberately — they are what pins the representation that
changed — and shrank from 2.33 MB to 1.87 MB gzipped.

**#24 changed no bytes on the SVG route.** `format` is additive: omit it, or pass
`format=svg`, and the response is what it was, checked over the endpoint rather than merely
intended. An unrecognised value is refused with 400 before any stage runs.

**#66 did move the SVG route, by 4-8 numbers per golden document.** The layout walked a box's
outline as a running position, so it printed the same edge twice one ulp apart —
`225.85714285714286` along the top, `225.8571428571429` along the bottom. Each moved number is
within 1.5e-16 of what it was, with no command and no element altered. No five numbers can
reproduce those bytes, and that same ulp is why `pgb` needed nine tolerant comparisons; a
tolerance on this side would have been the first of the comparisons the change exists to
delete.

## The claim that matters

`tests/node/band-geometry.test.mjs`: the numbers `pgb` recovers from each emitted document
are, to the bit, the numbers the layout held. **Exact equality, not a tolerance.**

Everything above is bytes, and bytes are a consequence rather than a target. This is the
assertion the increment actually rests on — that a smaller response is the *same* response.

## On the real server, 2026-09-02

`pgb` requested `?format=bands` from the deployed API and drew from the result. **First
exercise of the format anywhere but a test, and the first consumer the format has ever had.**

That answers the standing risk behind ADR 0001's additive design — that the server would
publish a format nothing adopted — and it is the reason the server stopped going back to
`release`: C needs a live band route to be read against.

### Three corrections came back the other way

All three were found by writing `pgb`'s reader (`pgb`#151) from
[`band-format.md`](../band-format.md) rather than from the encoder, which is what a spec
written to be read without the server is for. None could have been found on this side.

| | what the spec said | what the payload sends |
| --- | --- | --- |
| [#67](https://github.com/CAST-genomics/PangenomeAPI/pull/67) | `pclaiScore: 0.98` | `"993"` — and `"impainted"` on strands that *are* placed |
| [#70](https://github.com/CAST-genomics/PangenomeAPI/issues/70) | `fillOpacity: 0.4`, `strokeWidth: 2` | `"0.4"`, `"2px"` |
| [#66](https://github.com/CAST-genomics/PangenomeAPI/issues/66) | a box as a path command | five numbers |

The first two are the same defect twice: a field that is text in the payload and a number in
the spec, so a reader trusting the spec produces `NaN` — a category turned into a bad number,
and a border laid at `NaN` width, which in CSS is an ignored declaration rather than an error.
**Silent both times.** The document moved for both; the payload did not, and `version` stayed
1.

## What is still not measured

- **Production latency, on either side.** No `[stage-timing]` line has been read off the
  server since 2026-08-27. The server now runs the current code continuously, so this needs
  somebody to go and look, not a deploy — see the roadmap's *Verifying the whole thing*.
- **Payload behaviour over a real network.** The sizes above are local. Nobody has measured
  1.35 MB of `Float32` arriving at a browser over the wire, against 12.58 MB of XML.
- **Coverage of the 2026-09-02 read.** Which regions `pgb` drew from band data, and whether
  any were in the fetch-ceiling regime, was not recorded.
- **The contract.** [#25](https://github.com/CAST-genomics/PangenomeAPI/issues/25) is what
  keeps the two sides from drifting; the three corrections above are what drift looks like
  when a human catches it instead.
