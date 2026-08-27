# Golden tube map documents

Two synthetic subgraphs and the exact documents the sequence tube map generator
produces from them. `tests/node/generate-svg.golden.test.mjs` renders each input
and asserts the result is **byte-identical** to the committed document.

| case | strands | spine segments | input | golden |
| --- | ---: | ---: | ---: | ---: |
| `small` | 7 | 12 | 4.9 KB | 25 KB |
| `large` | 121 | 40 | 231 KB | 774 KB |

Both are rendered with `nodeWidthOption=compressed`, the endpoint's own default
(`main.py:720`). It is also the only width mode that can be goldened: `normal`
sizes each segment by measuring its label with the platform's fonts, so its bytes
differ between a developer's machine and CI. The smoke test next door covers
`normal` without asserting on bytes.

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

## These are synthetic, and reproducible

Both inputs come from the seeded generator in
[`perf/gen-vg-json.mjs`](../../../perf/gen-vg-json.mjs) — a reference spine with
bubbles hanging off it and haplotypes choosing an allele at each. The seeds and
parameters live in [`tests/node/golden-cases.mjs`](../../node/golden-cases.mjs),
and the test re-derives each input from them and checks it against the committed
bytes, so a fixture nobody can rebuild fails the suite.

Synthetic because the real inputs are not available: the five `.gfa` subgraphs in
[`../seqtubemap/`](../seqtubemap/README.md) came off the live server, but their
matching golden documents live in `pgb` and were captured before a change in how
strands are named — the pair does not line up today (see that README's last
section). When they do, these cases should be joined by, or replaced with, cases
built on real inputs.

## The real inputs, and `real/`

Two tests in the suite are written against the **real** subgraphs at `pgb`'s fetch
ceiling — `chr1:25,331,646-25,335,796` and `chr1:25,301,271-25,309,238`, committed in
[`../seqtubemap/`](../seqtubemap/README.md) — because those are the regime that
actually fails, and the synthetic cases only stand in for them. They **skip with a
stated reason** rather than being deferred, and start running the moment a document
appears at `real/<fixture-name>.svg`.

Nothing is there today, for two reasons. `pgb`'s five golden documents predate a
change in how strands are named and do not line up with these inputs (that
README's "Two conventions" section). And a self-baselined document for either
region is roughly **12 MB** — measured, not estimated — which is not a thing to
commit. When the naming mismatch is resolved on one side or the other, this is
where the resulting documents go.

Unlike the synthetic cases, the real ones take their region from the fixture's
filename. That is where the endpoint gets it too: it rebuilds the cache path from
the query parameters, so the coordinates in the name are the coordinates of the
request.

## Re-baselining

When an increment *is* meant to change the output, re-baseline deliberately:

```
npm run baseline:golden
```

That rewrites both the inputs (from their seeds) and the documents, and leaves
the diff in the working tree. Review it as part of that increment — the whole
point of the test is that a golden document changing in a commit which claimed
not to change behaviour is visible in the diff.

Never re-baseline to make a red test go green. A byte difference is either a
change the increment intended, in which case the diff is evidence for the review,
or it is the regression this test exists to catch.

## What it needs to run

Nothing. No `vg`, no graph data, no network — the inputs are committed and the
generator reads nothing else. `npm ci` for `jsdom` and `canvas` is the only
prerequisite, and that goes away with increment B.

## A note on `.gitignore`

The repository ignores `*.svg*` and `*.JSON*`, so these files survive only
because `!tests/fixtures/**` (`.gitignore:34`) is the last matching rule. A
golden document put anywhere outside `tests/fixtures/` would be silently
un-addable.
