# The fixture exchange — both encodings, for `pgb` to parse

The two repositories are one contract in two halves: this one produces documents
and band payloads, [`pgb`](https://github.com/CAST-genomics/pgb) parses them.
Nothing checked that they agreed until #25, and a wire-format break reached the
frontend as an error card at best and a **silently wrong picture** at worst.

These ten files are the exchange. Five regions, each in both encodings, out of
**one render** each:

| file | what it is |
| --- | --- |
| `<stem>.bands` | the band payload, exactly what `/seqtubemap?format=bands` returns |
| `<stem>.paired.svg.gz` | the document the same request returns without `format` |

A payload and a document are only an oracle for each other if they came out of
one render, which is what `.paired` says — `pgb`'s word, because five documents
fetched from the server in August sit in its fixture directory under the bare
stem, from a layout two increments ago.

## The five, and what they cost

| stem | region | strands | bands | payload | document | committed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `stm-chr8-78771162-78771252` | chr8:78,771,162-78,771,252 (90 bp) | 464 | 592 | 0.07 MB | 0.14 MB | 0.01 MB |
| `stm-chr1-25331046-25331646` | chr1:25,331,046-25,331,646 (600 bp) | 369 | 8,089 | 0.28 MB | 2.36 MB | 0.26 MB |
| `stm-chr8-10079054-10080461` | chr8:10,079,054-10,080,461 (1.4 kb) | 463 | 13,246 | 0.43 MB | 3.78 MB | 0.42 MB |
| **`stm-node-5514-chr1-25301271-25309238`** | chr1:25,301,271-25,309,238 (8.0 kb) | 383 | 35,020 | 1.16 MB | 10.46 MB | 1.11 MB |
| **`stm-node-5520-chr1-25331646-25335796`** | chr1:25,331,646-25,335,796 (4.2 kb) | 1,201 | 44,795 | 1.41 MB | 13.19 MB | 1.41 MB |
| | | | **101,742** | **3.35 MB** | **29.93 MB** | **3.22 MB** |

The last two are `pgb`'s fetch ceiling, which is the regime that actually fails
(#13) and the reason the exchange is not just the 90 bp region. The documents are
gzipped — 29.93 MB is not committable and 3.21 MB is, the same trade the band-data
baselines next door make — and the payloads are not, because they are already
numbers and a client receives them as they sit here.

**The file names are `pgb`'s**, not this repository's, so that handing them over
is a copy and not a translation. The mapping to the subgraph each was rendered
from is in [`tests/node/exchange-cases.mjs`](../../node/exchange-cases.mjs); two
regions are named there after the **minigraph node** whose tube map they are
(`5514`, `5520`) because that is what `pgb` calls them.

## Re-generating them

```
npm run fixtures:exchange
cp tests/fixtures/exchange/* ../pgb/src/tubemap/__tests__/fixtures/
```

No server, no `vg`, no graph data and no network: every input is committed in
[`../seqtubemap/`](../seqtubemap/README.md) — the subgraph, the region, and the
PCLAI colour scheme, which are the three inputs a render takes. About two seconds
for all five, on a large heap.

It is deterministic down to the gzip — a re-run with nothing changed rewrites the
same bytes and leaves no diff — so a diff here is always something that moved.

**When.** Whenever a change here moves what the endpoint serves: the band payload
encoder, the document emitter, or the layout that feeds them. **Both commands, in
the same window.** A payload this repository no longer serves is a fixture `pgb`
is green about for nothing, which is the failure mode the exchange exists to
remove, wearing a passing test.

Do not re-generate to make a test pass. The diff is the point: a change to the
wire bytes that nobody intended shows up here as a fixture changing in a commit
that claimed not to.

## What holds them honest

**Here**, [`tests/node/exchange-fixtures.test.mjs`](../../node/exchange-fixtures.test.mjs)
renders the same inputs and asserts three things: the committed payload is the
bytes this encoder writes, the committed document is the text this emitter
writes, and the committed pair describes one picture — every band's six floats,
read out of the payload, are the numbers `pgb`'s parser recovers from the
document, rounded once to Float32 and not otherwise touched.

**There**, `src/tubemap/__tests__/parseBandPayload.test.ts` parses its copy with
`parseBandPayload.ts` — a reader written from
[`docs/band-format.md`](../../../docs/band-format.md), **not a vendored copy of
this repository's parser**, which is the whole point of putting the test in the
repository whose parser it is.

Altering a fixture fails both, and that is a standing test rather than a story:
`exchange-fixtures.test.mjs` nudges band 0's `x1` of the 90 bp payload by one part
in 10⁴ — too small to see, far too large to be rounding — and asserts the pair
check notices. Run against the real files on 2026-09-02, the same nudge makes this
side name the first differing byte (55,932) and `pgb`'s reader put the band 16.59
ulp from where the document puts it.

## Verified against `pgb`'s reader — 2026-09-02

These exact bytes, through `parseBandPayload.ts` and `parseBands.ts` at `pgb`
`fde52e3`, over all 101,742 bands:

* band count, frame, `centre`, strand names and `pclaiScore`s: equal;
* band ordinates, directions and strand ids: equal exactly;
* segment boxes: equal exactly, all 1,219 of them;
* abscissae and widths: within **one Float32 ulp** — worst 0.86, 0.86, 0.44,
  0.86, 0.86 by the table's order, which reproduces the figures `pgb`'s own
  fixture notes record. The residue is the format and neither parser: the payload
  rounds to Float32 on the wire and `pgb` then derives `width` from the rounded
  ends, while the document parser derives it in double and rounds once.

## How these relate to the pairs `pgb` captured from the live server

`pgb`'s committed copies were **captured from the deployed endpoint** on
2026-09-02, by two `curl`s differing in one parameter, rather than generated
here. Its `fixture.ts` documents that capture, and it is the stronger pairing for
its purpose: those are the bytes the app itself receives.

The two sets are not identical, and the difference is worth knowing before
reaching for one to explain the other:

Measured against `pgb`'s copies, 2026-09-02:

* **The payload bodies are byte-identical** — every float, strand id and kind, on
  all five. So are the header's `document` dimensions and all 1,219 segment boxes.
  The geometry these fixtures exist to pin does not depend on which side generated
  them.
* **Every strand name differs, in one way**: the live graph's walks append the
  reference range, `HG03688#1#CM086800.1#0[25397889-25398120]` against this side's
  `HG03688#1#CM086800.1#0`. The `.gfa` subgraphs committed here were pulled on
  2026-08-27 and predate that. A name is a name of its own capture, on both sides,
  and neither is wrong about the region — and `pgb` splits a name on `#` and
  renders what it is handed, so the difference is a longer label and nothing more.
* **Five strands of the 2,880 differ in colour and `pclaiScore`** — one each in the
  600 bp and 8.0 kb regions, three in the 4.2 kb one. They were unplaced when the
  PCLAI schemes here were recovered and carry a placement on the server now. Every
  other row's colour is identical.

Which is also why re-generating here does not make the server's output stale, and
why a strand name is the one field of these fixtures that should not be read as a
claim about what the server returns today.
