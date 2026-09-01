# PangenomeAPI — Context

The backend of the Pangenome Browser. It extracts a region of a human pangenome
graph and returns it in the form its one consumer — [`pgb`](https://github.com/CAST-genomics/pgb) —
needs: graph structure for the 3D view, and a **sequence tube map** for looking
inside a single **node**.

This glossary is shared with `pgb`'s [`CONTEXT.md`](https://github.com/CAST-genomics/pgb/blob/main/CONTEXT.md)
and the two must not diverge. Where a word here differs from what the upstream
tools (GFA, `vg`, `tubemap.js`) spell it, that spelling is listed under _Avoid_:
it stays correct *inside* the tool's own file format, and stops at this codebase's
boundary.

**Illustrated**: [`docs/lexicon.html`](./docs/lexicon.html) annotates one real tube
map with **segment**, **strand**, **band**, **pivot strand**, **node** and
**region**, so each word can be pointed at rather than only read. Rendered at
<https://claude.ai/code/artifact/eb3ad4a1-d1cb-44b9-a3b8-7c6e7cc12726>. It is
abridged *from* this file — where the two disagree, this file wins.

## Language

**pangenome graph**:
A graph whose vertices are stretches of DNA and whose paths are the assembled
haplotypes of many individuals. Two are served: **minigraph-cactus** and
**minigraph**, each in a **v1** and a **v2** build.

**node**:
A vertex of the coarse graph `pgb` draws in 3D — one haplotypic stretch of DNA,
addressed by an oriented id such as `141452+`. This is what the `minigraphnode`
parameter names.
_Avoid_: using bare "node" for the finer vertices inside a tube map — those are
**segments**. The two granularities appear in the same URL, which is exactly why
the distinction is written down. **minigraph node** is the deliberate alias to
reach for wherever a tube map is also in scope.

**segment**:
A vertex *inside* a **sequence tube map** — one stretch of sequence in the
minigraph-cactus subgraph that a **node** collapses. Typically tiny; most are
single-base variants.
_Avoid_: node (this codebase's meaning), and `vg`'s "node". A GFA `S` line is a
segment in the GFA, which is the one place the word already agrees.

**strand**:
One haplotype's route through a **sequence tube map**, identified by the triple
`sample#haplotype#contig` and coloured by its shipped PCLAI RGB. The triple is
the whole of a strand's identity: one haplotype fragmented across a **region**
contributes several GFA `W` lines but remains one strand.
_Avoid_: track, path, walk. This one concept has five spellings across the
pipeline — a GFA `W` line calls it a walk, a GFA `P` line and `vg` JSON call it a
path, `tubemap.js` and the emitted `trackID`/`trackName` attributes call it a
track, and the biology calls it a haplotype. Each is correct in its own format;
none of them is what this codebase calls it.
_Avoid_ also: treating `vg`'s longer spelling as the name. `vg` appends its own
phase block and subrange to the triple — `sample#haplotype#contig#0[9659985-9661740]`
— and that string travels the wire verbatim, because rewriting it would make this
codebase's documents disagree with the tool that produced them. It is `vg`
metadata riding on the identity, not part of it; the codebase truncates back to
the triple only where it looks something up, such as a PCLAI colour.

**pivot strand**:
The **strand** the layout arranges every other strand around — it fixes segment
order and orientation, and the rest are threaded against it. **GRCh38** where
present. Which strand this is changes the picture, not the data: the same
**subgraph** laid out around a different pivot draws the same **segments** and
the same **strands** in a different arrangement, at a different size.
_Avoid_: leaving it implicit. A pivot chosen by whatever order the strands
happened to arrive in is a picture that moves for reasons the reader cannot see.

**band**:
The atomic drawable of a **sequence tube map**: one **strand** crossing one
x-interval. A strand is made of many bands, so a band count counts shapes, not
haplotypes.
_Avoid_: ribbon, which reads as the whole strand.

**band payload**:
What `/seqtubemap?format=bands` returns: the same picture as the SVG document, said as
the numbers themselves — a JSON header carrying the frame, the **strand** table and the
segment boxes, then a columnar body of six `Float32`s, a `Uint16` and a `Uint8` per
**band**. Specified in [`docs/band-format.md`](./docs/band-format.md). Additive: omitting
`format` returns the document byte for byte. The band data is canonical and the document
is a rendering of it.
_Avoid_: "the binary format", which names how it is spelled rather than what it carries —
the header is JSON.

**reversal**:
The shape a **strand** doubling back on itself draws: a pair of **corners** — quarter
turns built from quadratics — and a **vertical connector**, a rectangle as tall as the
reversal is deep rather than `thickness` tall. Outside the six-value **band** grammar, so
they ride in the header's `reversals` rather than in the body, each with the `order` it
occupied among the shapes the render drew. No production response contains one, and a
client may reasonably refuse a response whose `reversals` are non-empty.
_Avoid_: using it for an inverted haplotype. A reversal is a fact about the drawing; an
inversion is a fact about the biology, and the haplotypes that traverse an inversion are
drawn out of ordinary bands.

**sequence tube map**:
A base-resolution picture of what is inside one **node** — its **segments** laid
along an axis with every **strand** threaded through them.

**subgraph**:
The slice of a **pangenome graph** covering one requested region. The unit this
API extracts, transforms and serves; never the whole graph.

**region**:
A `chrom`, `start`, `end` triple in GRCh38 coordinates. The address of every
request.

**assembly**:
One sequenced individual's genome. Contributes two **strands** per chromosome to
the graph — one per haplotype.

**GRCh38**:
The linear reference the graphs are built against and every **region** is
expressed in. Present in the graph as **strands** of its own, and treated
specially wherever strands are merged — and, as the **pivot strand**, wherever
they are laid out.
