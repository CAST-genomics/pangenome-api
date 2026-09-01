# The band format

What `/seqtubemap?format=bands` returns, in enough detail to write a parser
against without reading the server.

The endpoint's other format is a **sequence tube map** as an SVG document: every
**band** drawn as an element carrying a drawing command, its **strand**'s colour,
its strand's name and its strand's ancestry placement — the per-strand values
re-serialized once per band, which is 41–47% of the response, and the geometry
as text the client parses back into numbers with a regular expression
([ADR 0001](adr/0001-additive-band-format.md)).

This format says each per-strand value once, in a table the bands point at, and
says the geometry as the numbers themselves, laid out so a client can build
typed-array views over the bytes it received and hand them to the GPU without a
parse step.

`format` is **additive**: omitting it, or passing `format=svg`, returns exactly
what the endpoint returned before, byte for byte. An unrecognised value is
refused with `400` rather than quietly served as SVG.

```
GET /seqtubemap?chrom=chr1&start=25301271&end=25309238&version=v2&format=bands
→ 200 application/octet-stream
```

## Layout

```
offset            bytes         what
0                 4             header length H, uint32 little-endian
4                 H             header, JSON, UTF-8
4 + H             pad to 4      zeros, so the body starts 4-byte aligned
B = ceil4(4 + H)  6 × 4 × N     geometry: float32, six per band
B + 24N           2 × N         strand ids: uint16, one per band
B + 26N           N             kinds: uint8, one per band
                  pad to 4      zeros
```

`N` is `header.band.count`. Every multi-byte value in the body is
**little-endian**. The body's three sections are not written at fixed offsets by
convention — read `byteOffset` and `byteLength` out of the header, which are
relative to `B`, and `header.bodyLength` is the body's total size.

The body is **columnar**, one array per field, rather than one interleaved
26-byte record per band. Interleaved, no `Float32Array` view could be taken over
it: a 26-byte stride is not a multiple of 4, so a client would have to copy the
fields apart one at a time, which is the parse step this format exists to
delete. Split into columns, each column is one view over the bytes that arrived.

### Reading it

```js
const bytes = new Uint8Array(await response.arrayBuffer());
const headerLength = new DataView(bytes.buffer, bytes.byteOffset, 4).getUint32(0, true);
const header = JSON.parse(new TextDecoder().decode(bytes.subarray(4, 4 + headerLength)));

const body = bytes.byteOffset + ((4 + headerLength + 3) & ~3);
const { count, geometry, strandIds, kinds } = header.band;
const xyz = new Float32Array(bytes.buffer, body + geometry.byteOffset, count * 6);
const strand = new Uint16Array(bytes.buffer, body + strandIds.byteOffset, count);
const kind = new Uint8Array(bytes.buffer, body + kinds.byteOffset, count);
```

`seqtubemap/band-payload.mjs` holds a reference reader (`decodeBandPayload`), and
`tests/python/test_seqtubemap_band_format.py` holds the same four lines in
Python.

## The header

```json
{
  "format": "pangenome-bands",
  "version": 1,
  "document": {
    "width": 27953.85714285714,
    "height": 5775,
    "viewBox": "0 -170 27953.85714285714 5775",
    "extent": { "maxXCoordinate": 27903.85714285714, "maxYCoordinate": 5575, "minYCoordinate": -150 }
  },
  "band": {
    "thickness": 15,
    "alpha": 1,
    "count": 8089,
    "geometry": {
      "type": "Float32",
      "fields": ["x0", "y0", "x1", "y1", "controlTop", "controlBottom"],
      "byteOffset": 0,
      "byteLength": 194136
    },
    "strandIds": { "type": "Uint16", "byteOffset": 194136, "byteLength": 16178 },
    "kinds": { "type": "Uint8", "byteOffset": 210314, "byteLength": 8089,
               "values": { "rect": 0, "curve": 1 } }
  },
  "strands": [
    { "id": 0, "name": "GRCh38#0#chr1", "color": [255, 115, 56],
      "pclaiX": 0.12, "pclaiY": -0.43, "pclaiScore": 0.98 }
  ],
  "segments": [
    { "id": "79337767", "outline": "M 11 20 Q 11 11 20 11 …",
      "sequence": "AGAGCCTGTCTT…", "fill": "#ffffff", "fillOpacity": 0.4,
      "stroke": "#000000", "strokeWidth": 2 }
  ],
  "overlays": [],
  "reversals": { "corners": [], "connectors": [] },
  "bodyLength": 218408
}
```

**`format` and `version`** — a reader that does not recognise both should refuse
the response rather than guess at it. `version` changes when the meaning of a
field changes; a new *optional* field does not change it.

**`document`** — the dimensions of the picture the bands are drawn in, in the
layout's own double precision. `viewBox` is `minX minY width height`, and the
coordinate system the geometry is expressed in.

**`band.thickness`** — every band in a tube map is this tall. It is the constant
that makes six numbers enough: the lower edge of a band is its upper edge shifted
down by the thickness. A band of any other thickness is not something this format
can carry, and the server refuses to encode one.

**`band.alpha`** — the opacity every band is drawn at. Said once for the same
reason.

**`strands`** — the **strand** table, one row per strand appearance: `id` is the
layout's own ordering, dense from 0 with no gaps; `name` is the
`sample#haplotype#contig` triple as `vg` produced it, phase block and subrange
included; `color` is three whole channels in 0–255; the three `pclai*` fields are
the strand's ancestry placement, and are `null` where the region has none. A
strand's values appear here once, however many bands it draws.

**`segments`** — the **segment** boxes, in draw order, each with the id, outline
and sequence a client draws and labels from. The outline is a path command
because a segment box is a rounded rectangle rather than a band; there are three
orders of magnitude fewer of them than bands.

**`overlays`** — the ruler and the per-segment labels, when the render drew any:
an element name, its attributes as ordered pairs, and its text. **Empty in every
production response** — a real subgraph carries no reference offset, so it gets
no ruler — and carried only so the payload is a complete description of the
picture.

**`reversals`** — see below.

## A band

Six floats and a strand id. Read band `i` as:

| field | meaning |
| --- | --- |
| `x0`, `y0` | the near end of the band's upper edge |
| `x1`, `y1` | the far end of the band's upper edge |
| `controlTop` | the control abscissa of the upper edge's cubic |
| `controlBottom` | the control abscissa of the lower edge's cubic |

and `strandIds[i]` is a **row index into `strands`** — not a `trackID`. The two
coincide in practice, since a strand has one row; read the row and take its `id`
if you need the layout's number.

The whole outline, with `T = header.band.thickness`:

```
M x0 y0
C controlTop y0  controlTop y1  x1 y1
V y1 + T
C controlBottom (y1 + T)  controlBottom (y0 + T)  x0 (y0 + T)
Z
```

Both cubics' control ordinates repeat the endpoints, and the lower edge is the
upper edge shifted by `T`. That redundancy is why six numbers say the whole
shape, and it was measured across 127,101 strand paths before it was relied on.

`kinds[i]` says whether the server drew the band as a `<rect>` (0) or a `<path>`
(1) in the SVG format. **A client drawing bands can ignore it**: a rect is the
degenerate band — both edges level, so any control abscissa reproduces it — and
the six numbers are the whole shape either way. It is carried so that the SVG
document is reconstructible from the payload, which is what makes the band data
canonical and the document a rendering of it.

### Precision

The geometry is `Float32`. The layout computes in doubles, so a coordinate
arrives rounded: `138.71428571428573` becomes `138.7142791748047`. That is the
format's one lossy step and it is deliberate — a GPU instance buffer is float32,
so the rounding would happen on the client anyway. Everything else (the
dimensions, the strand table, the segment outlines) travels at full precision as
JSON.

### The shapes that are not bands

A **reversal** — a strand doubling back on itself — draws two shapes that are
outside the six-value grammar: **corners**, quarter turns built from quadratics,
and **vertical connectors**, rectangles as tall as the reversal is deep rather
than `thickness` tall. They are not in the body. They ride in
`reversals.corners` and `reversals.connectors` as JSON objects carrying the
layout's own parameters, each with an `order`: the position it occupied among
all the shapes the render drew.

Draw order is paint order — later shapes draw over earlier ones. To recover the
full order: place each reversal shape at its `order`, then fill the remaining
positions, in ascending order, with the body's bands in body order.

**No production response contains one.** None of the five real subgraphs draws a
reversal, and a client may reasonably refuse a response whose `reversals` are
non-empty (as `pgb` does today —
[#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52)) rather than
implement two shapes it will not meet.

## What is refused

| condition | response |
| --- | --- |
| `format` is neither `svg` nor `bands` | `400`, naming the value and what would have been accepted |
| more than 65,536 strand rows | the render fails and the request gets `502` naming the stage; the server refuses to encode rather than wrap a 16-bit id round |
| a band thicker or thinner than `thickness`, or at an opacity other than `alpha` | the same — the header says these once, so a shape that disagrees with them cannot be carried |
| a strand coloured in a spelling that is neither `#rrggbb` nor `rgb(r, g, b)` | the same |

Each of these is refused where the layout that produced it is still in scope, so
the error names the cause rather than surfacing in the client as an unreadable
response.

## Measured

Five real subgraphs, rendered through `renderTubeMap` and encoded both ways,
2026-09-01. `perf/band-payload-sizes.mjs` reproduces the table.

| region | span | strands | bands | SVG | band payload | ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chr8:78,771,162-78,771,252 | 90 bp | 464 | 592 | 0.13 MB | 0.07 MB | 1.9× |
| chr1:25,331,046-25,331,646 | 600 bp | 369 | 8,089 | 2.25 MB | 0.28 MB | 8.1× |
| chr8:10,079,054-10,080,461 | 1.4 kb | 463 | 13,246 | 3.61 MB | 0.43 MB | 8.4× |
| chr1:25,301,271-25,309,238 | 8.0 kb | 383 | 35,020 | 9.97 MB | **1.25 MB** | 8.0× |
| chr1:25,331,646-25,335,796 | 4.2 kb | 1,201 | 44,795 | 12.58 MB | 1.40 MB | 9.0× |

ADR 0001 projected "roughly 1.5 MB against the current 10.07 MB" at the 10 kb
region from the band count and the record width. Measured on the 8.0 kb subgraph
that stands for it: **1.25 MB against 9.97 MB**. The projection was right and
slightly pessimistic.

The ratio is smallest on the smallest region, and that is the shape of the win
rather than a defect: the 90 bp subgraph draws 592 bands over 464 strands, so its
payload is almost entirely the strand table — said once, but said in full. Where
the response is large enough to be a problem, the bands dominate and the strand
table is a rounding error.

On the 8.0 kb region the header is 0.35 MB of the 1.25 MB and the body is
0.90 MB. What the header spends it on is the **segment boxes** — 0.30 MB for
768 of them, of which 0.21 MB is their outlines, written as path commands — with
the 383-row strand table at 0.045 MB and the sequences themselves at 0.011 MB.
So the per-strand redundancy this format set out to remove is gone, and what is
left on the JSON side is the segment outlines: a smaller, later question than
the one this format answers, and one that touches three orders of magnitude
fewer shapes than the bands do.
