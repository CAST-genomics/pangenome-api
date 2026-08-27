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
One haplotype's route through a **sequence tube map**, named
`sample#haplotype#contig` and coloured by its shipped PCLAI RGB.
_Avoid_: track, path, walk. This one concept has five spellings across the
pipeline — a GFA `W` line calls it a walk, a GFA `P` line and `vg` JSON call it a
path, `tubemap.js` and the emitted `trackID`/`trackName` attributes call it a
track, and the biology calls it a haplotype. Each is correct in its own format;
none of them is what this codebase calls it.

**band**:
The atomic drawable of a **sequence tube map**: one **strand** crossing one
x-interval. A strand is made of many bands, so a band count counts shapes, not
haplotypes.
_Avoid_: ribbon, which reads as the whole strand.

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
specially wherever strands are merged.
