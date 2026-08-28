# Golden tube map documents

Two synthetic subgraphs, one of them rendered three times, and the exact documents
the sequence tube map generator produces from them.
`tests/node/generate-svg.golden.test.mjs` renders each case and asserts the result
is **byte-identical** to the committed document.

| case | input | strands | spine segments | golden |
| --- | --- | ---: | ---: | ---: |
| `small` | `small.vg.json` | 7 | 12 | 22 KB |
| `large` | `large.vg.json` | 121 | 40 | 656 KB |
| `small-normal` | `small.vg.json`, at `nodeWidthOption=normal` | 7 | 12 | 27 KB |
| `small-pclai` | `small.vg.json` + `pclai-color-scheme.json` | 7 | 12 | 22 KB |

All but `small-normal` are rendered with `nodeWidthOption=compressed`, the
endpoint's own default (`main.py:720`).

`normal` is a live value of the same query parameter, and until
[#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22) it could not be
goldened at all: it sized each segment by writing the label into the emulated
browser document and asking for `getComputedTextLength`, so the bytes depended on
which fonts the host had. #22 deleted the browser, and with it the measurement —
the label is monospace, so its width is its glyph count times one advance. That
makes the mode deterministic, and `small-normal` is what now pins it. It is also
the only golden carrying segment labels and the finer 20 bp ruler, because
`normal` is the only mode that draws either.

Byte-identity is the bar because the increments this test guards
([#13](https://github.com/CAST-genomics/PangenomeAPI/issues/13) B, C and D)
expect *zero* change in the output: they replace how the document is produced —
capturing the layout's output, removing the browser emulation, turning geometry
from strings into numbers — while the geometry itself stays put. A weaker
assertion would not catch the failure those increments can actually have.

The `large` case exists so that strand handling is under test at all. Seven
strands would go on passing if strand layout or ordering collapsed; 121 is the
same order of magnitude as a real subgraph's 369–464, at a size still reasonable
to commit.

## The PCLAI colour scheme case

The generator takes an optional sixth argument, a PCLAI colour scheme as JSON
(`seqtubemap/generate-svg.mjs`). Production passes it whenever `minigraphnode` is
set (`main.py:767`), and when it is present it takes over strand colour entirely —
each strand is drawn in its scheme colour, or light grey if the scheme does not
mention it (`seqtubemap/tubemap.js:2503`). It also puts the scheme's coordinates
and confidence score on every strand element as `pclaiX`, `pclaiY` and
`pclaiScore`.

`small-pclai` renders **the same input as `small`** through that argument, with
the scheme committed beside the fixtures as `pclai-color-scheme.json` rather than
inlined in the case list, so the generator's actual input is a file a reader can
open. Sharing `small`'s input is the point: the two documents differ only by the
scheme, so any difference in strand colour is the scheme's doing. That is what
makes [#13](https://github.com/CAST-genomics/PangenomeAPI/issues/13)'s claim that
strand colour "passes through untouched" through increments B and C checkable
rather than asserted — recolouring is explicitly out of scope there, and a golden
is how out-of-scope becomes enforced.

Because the input is borrowed, `small-pclai` has no seed of its own: re-baselining
writes `small.vg.json` once, from `small`.

The scheme carries all three shapes an entry can take: strands with a PCLAI
colour, one with the grey no-coordinate entry the endpoint emits when
`x_coord == "."` (`main.py:684`), and strands the scheme does not mention, which
fall back to light grey. The last two are the *same* grey, so colour alone cannot
show that both are covered — the `pclaiX`, `pclaiY` and `pclaiScore` attributes
can, and a second test checks those. Between them, a scheme that quietly stopped
being applied fails loudly rather than just re-baselining.

## These are synthetic, and reproducible

The two inputs come from the seeded generator in
[`perf/gen-vg-json.mjs`](../../../perf/gen-vg-json.mjs) — a reference spine with
bubbles hanging off it and haplotypes choosing an allele at each. The seeds and
parameters live in [`tests/node/golden-cases.mjs`](../../node/golden-cases.mjs),
and the test re-derives each input from them and checks it against the committed
bytes, so a fixture nobody can rebuild fails the suite.

Synthetic because they are meant to be: seeded, small enough to read in a diff,
and rebuildable by anyone from the parameters alone. The real subgraphs are
covered too, but not from here — see the next section.

## The real inputs, and where they are pinned

The five real `.gfa` subgraphs in [`../seqtubemap/`](../seqtubemap/README.md) — including
the two at `pgb`'s fetch ceiling, which are the regime that actually fails and the reason
the synthetic cases are not enough — are pinned by
[`tests/node/real-subgraph.band.test.mjs`](../../node/real-subgraph.band.test.mjs), against
**band data** baselined beside each subgraph as `<name>.band.json.gz`.

Not a golden document, and nothing lives in this directory for them. Two tests here used to
be written against a recaptured SVG from the server and skipped with a stated reason
waiting for one to appear at `real/<name>.svg`. That was the wrong artifact to wait for:
[`docs/adr/0001`](../../../docs/adr/0001-additive-band-format.md) makes the band data
canonical and the document derived from it, so a baselined document pins the derived
artifact — a weaker guarantee, at 35.84 MB across the five against 2.33 MB of gzipped
numbers. The documents are still checked, but as something *rebuilt from* the baseline and
compared in full, which is a stronger claim than byte-identity against a capture.

That test also renders all three inputs a real request carries, the PCLAI colour scheme
included, which the synthetic `small-pclai` case covers only in miniature. See
[`../seqtubemap/README.md`](../seqtubemap/README.md) for where each input came from and what
the baselines cost on disk.

## Re-baselining

When an increment *is* meant to change the output, re-baseline deliberately:

```
npm run baseline:golden
```

That rewrites both the inputs (from their seeds) and the documents, and leaves
the diff in the working tree. Review it as part of that increment — the whole
point of the test is that a golden document changing in a commit which claimed
not to change behaviour is visible in the diff.

The real subgraphs' band data has its own script, `npm run baseline:bands`, because
the two cost different things: the synthetic goldens re-render in about a second,
and the five real ones take minutes and want a large heap.

Never re-baseline to make a red test go green. A byte difference is either a
change the increment intended, in which case the diff is evidence for the review,
or it is the regression this test exists to catch.

## What it needs to run

Nothing. No `vg`, no graph data, no network — the inputs are committed and the
generator reads nothing else. `npm ci` is the only prerequisite, and since
increment B it installs two packages rather than five: `jsdom` and `canvas` left
with the emulated document.

Memory used to be the one real requirement, and it came from the real subgraphs
rather than from these. It no longer dominates: a 4.2 kb layout that peaked
around 2.3 GB now peaks around 466 MB, of which none is a document. `npm test`
still raises the heap, because the layout itself is the remaining cost and the
default is 4 GB on some hosts and less on others.

## A note on `.gitignore`

The repository ignores `*.svg*` and `*.JSON*`, so these files survive only
because `!tests/fixtures/**` (`.gitignore:34`) is the last matching rule. A
golden document put anywhere outside `tests/fixtures/` would be silently
un-addable.
