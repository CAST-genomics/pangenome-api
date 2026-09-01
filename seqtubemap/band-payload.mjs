// The band payload: the wire format `/seqtubemap?format=bands` returns.
//
// The SVG document says every per-strand value once per band — a colour, a name
// and a PCLAI placement re-serialized on each of the 55,053 bands a real
// subgraph draws, which is 41-47% of every response
// (docs/adr/0001-additive-band-format.md) — and says the geometry as a drawing
// command the client parses back into numbers with a regular expression. This
// format says each per-strand value once, in a table the bands point at, and
// says the geometry as the numbers themselves, laid out so that a client can
// build a typed-array view over the bytes it received and hand that straight to
// the GPU. No parse step, no regular expression, no megabytes of text.
//
// The format is specified in `docs/band-format.md`, which is written to be
// enough to write a parser against without reading this file. What follows is
// why it is shaped the way it is; the spec is what it *is*.
//
//   +-------------------+
//   | uint32 LE         |  byte length of the header
//   | header (JSON)     |  dimensions, strand table, segment boxes, section map
//   | padding           |  to the next multiple of 4
//   | geometry          |  Float32 x 6 x band count
//   | strand ids        |  Uint16 x band count
//   | kinds             |  Uint8  x band count
//   +-------------------+
//
// **Columnar, not one interleaved record per band.** The ticket describes the
// body as "six 32-bit floats plus a 16-bit strand id" per band, and that is what
// it holds — but interleaved that is a 26-byte stride, and a Float32Array cannot
// be viewed over a buffer at an offset that is not a multiple of 4. A client
// receiving interleaved records would have to copy them apart with a DataView,
// one field at a time, which is the parse step this format exists to delete.
// Split into columns, each column is a single typed-array view over the received
// bytes: `new Float32Array(buffer, offset, 6 * count)` is the instance buffer.
//
// **What a band does not carry.** Its thickness, because every band in a tube
// map is `BAND_THICKNESS` and that is the constant which makes six numbers
// enough (band-data.mjs). Its opacity, for the same kind of reason: the layout
// paints an alpha below 1 only on reads, and this fork renders none, so an alpha
// that is not 1 throws here rather than being encoded as a value the format has
// no room for. Its colour and its strand's name, which live in the strand table.
//
// **What it does carry beyond the ticket's record**: one byte per band saying
// whether the layout drew it as a `<rect>` or a `<path>`. A client that only
// draws bands can ignore it — the six numbers are the whole shape either way,
// which is what `rectBand` means by "one primitive in two spellings". It is here
// so the payload is a *complete* description of the picture rather than an
// abridged one: the SVG is reconstructible from it, which is what makes
// "the band data is canonical and the document is a rendering of it" true in
// fact and testable in `tests/node/band-payload.test.mjs`.
//
// **A strand's colour is three numbers, not CSS.** The layout spells a colour
// two ways — hex from its palettes, `rgb(r, g, b)` from a PCLAI scheme, and the
// scheme's channels can be fractional — so a client reading the document has to
// parse both and round the way a stylesheet would. The payload says the channels
// themselves, rounded once here by the same function the document rounds with.
//
// **The reversal shapes are not bands** and are not in the body. A corner is
// built from quadratics and a vertical connector is as tall as the reversal is
// deep, so neither fits the six-value grammar (#23, #52). They ride in the
// header as their own lists, each carrying the position it occupies in the draw
// order, because paint order is document order and a client compositing the
// picture needs to know where they fall. No production document contains one.
import { BAND_THICKNESS, rgbChannels } from "./band-data.mjs";

/** The format's name and version, as they appear in the header. */
export const FORMAT = "pangenome-bands";
export const VERSION = 1;

/** The order the six geometry floats appear in, per band. */
export const GEOMETRY_FIELDS = ["x0", "y0", "x1", "y1", "controlTop", "controlBottom"];

/** The kind byte: which element the document draws the band as. */
export const KIND_RECT = 0;
export const KIND_CURVE = 1;

/**
 * The largest strand table this format can address.
 *
 * A band names its strand in 16 bits, so a document with more strand rows than
 * this cannot be encoded — and must say so, rather than wrapping round and
 * colouring bands from the wrong strand. `pgb` holds the same ceiling for the
 * same reason: its instance buffer is a Uint16Array.
 */
export const MAX_STRAND_ROWS = 65536;

/** Every band carries this opacity; see the module comment. */
const BAND_ALPHA = 1;

/**
 * The band payload for one render's band data.
 *
 * @param {object} bandData  what `renderTubeMap` collected
 * @returns {Uint8Array} the bytes of the response
 */
export function encodeBandPayload(bandData) {
  const { document, strands, bands, segments, overlays } = bandData;

  assertAddressable(strands);

  // The six-value bands, in draw order, and the two reversal kinds alongside
  // them — each remembering where in the draw order it sat, because that is
  // paint order and splitting the list must not lose it.
  const drawn = [];
  const corners = [];
  const connectors = [];
  bands.forEach((band, order) => {
    switch (band.kind) {
      case "rect":
      case "curve":
        assertAlpha(band, order);
        assertStrand(band, order, strands.length);
        drawn.push(band);
        return;
      case "corner":
        assertStrand(band, order, strands.length);
        corners.push({ ...band, order });
        return;
      case "connector":
        assertStrand(band, order, strands.length);
        connectors.push({ ...band, order });
        return;
      default:
        throw new Error(
          `a band of kind "${band.kind}" is not one this format can carry. ` +
            "Every kind band-data.mjs collects has to be encoded here.",
        );
    }
  });

  const count = drawn.length;
  const geometryLength = count * GEOMETRY_FIELDS.length * 4;
  const strandIdsOffset = geometryLength;
  const kindsOffset = strandIdsOffset + count * 2;
  const bodyLength = align4(kindsOffset + count);

  const header = {
    format: FORMAT,
    version: VERSION,
    document,
    band: {
      // Said once, for every band: the two constants that let six numbers
      // describe a band at all.
      thickness: BAND_THICKNESS,
      alpha: BAND_ALPHA,
      count,
      geometry: {
        type: "Float32",
        fields: GEOMETRY_FIELDS,
        byteOffset: 0,
        byteLength: geometryLength,
      },
      strandIds: { type: "Uint16", byteOffset: strandIdsOffset, byteLength: count * 2 },
      kinds: {
        type: "Uint8",
        byteOffset: kindsOffset,
        byteLength: count,
        values: { rect: KIND_RECT, curve: KIND_CURVE },
      },
    },
    strands: strands.map(strandRow),
    segments,
    // Empty in every production document — a real subgraph carries no reference
    // offset, so it gets no ruler and no labels (ADR 0001). Carried anyway,
    // because a payload that silently dropped part of the picture would not be
    // the canonical description of it.
    overlays,
    // Neither is a band; see the module comment.
    reversals: { corners, connectors },
    bodyLength,
  };

  const headerBytes = Buffer.from(JSON.stringify(header), "utf8");
  const bodyOffset = align4(4 + headerBytes.length);
  const payload = new Uint8Array(bodyOffset + bodyLength);
  const view = new DataView(payload.buffer);

  view.setUint32(0, headerBytes.length, true);
  payload.set(headerBytes, 4);

  // Written through a DataView rather than typed-array views, because
  // `bodyOffset` is 4-aligned but the sections inside it need no further
  // assumption, and because this is the one place the byte order is decided:
  // little-endian, said explicitly, on every machine.
  drawn.forEach((band, index) => {
    let at = bodyOffset + index * GEOMETRY_FIELDS.length * 4;
    for (const field of GEOMETRY_FIELDS) {
      view.setFloat32(at, band[field], true);
      at += 4;
    }
    view.setUint16(bodyOffset + strandIdsOffset + index * 2, band.strand, true);
    view.setUint8(bodyOffset + kindsOffset + index, band.kind === "rect" ? KIND_RECT : KIND_CURVE);
  });

  return payload;
}

/**
 * Read a payload back: the header, and typed-array views over the body.
 *
 * This is a client's parser, written on the server side of the wire — the
 * reference implementation `docs/band-format.md` describes and the tests check
 * the encoder against. It copies nothing: the views are windows onto the bytes
 * that arrived, which is the whole point of the format.
 *
 * @param {Uint8Array|ArrayBuffer} payload
 */
export function decodeBandPayload(payload) {
  const bytes = payload instanceof Uint8Array ? payload : new Uint8Array(payload);
  const buffer = bytes.buffer;
  const base = bytes.byteOffset;

  if (bytes.byteLength < 4) {
    throw new Error(`a band payload is at least 4 bytes; this one is ${bytes.byteLength}`);
  }

  const headerLength = new DataView(buffer, base, 4).getUint32(0, true);
  const header = JSON.parse(
    Buffer.from(buffer, base + 4, headerLength).toString("utf8"),
  );
  if (header.format !== FORMAT) {
    throw new Error(`not a band payload: format is "${header.format}", not "${FORMAT}"`);
  }
  if (header.version !== VERSION) {
    throw new Error(`band payload version ${header.version}; this reader knows ${VERSION}`);
  }

  const bodyOffset = base + align4(4 + headerLength);
  const { count, geometry, strandIds, kinds } = header.band;

  return {
    header,
    geometry: new Float32Array(buffer, bodyOffset + geometry.byteOffset, count * 6),
    strandIds: new Uint16Array(buffer, bodyOffset + strandIds.byteOffset, count),
    kinds: new Uint8Array(buffer, bodyOffset + kinds.byteOffset, count),
  };
}

/**
 * The band data a payload describes, in the shape `emit-document.mjs` takes.
 *
 * Not part of the wire contract — it is how the tests ask "is the picture still
 * the same picture", by writing the document back out of what a client would
 * have received and comparing it to the one the server serves. The geometry
 * comes back through Float32, so the numbers are the layout's rounded to single
 * precision and nothing else.
 */
export function bandDataFromPayload(payload) {
  const { header, geometry, strandIds, kinds } = decodeBandPayload(payload);
  const { corners, connectors } = header.reversals;

  const total = header.band.count + corners.length + connectors.length;
  const bands = new Array(total);
  for (const shape of [...corners, ...connectors]) bands[shape.order] = shape;

  let index = 0;
  for (let order = 0; order < total; order += 1) {
    if (bands[order] !== undefined) continue;
    const at = index * 6;
    bands[order] = {
      kind: kinds[index] === KIND_RECT ? "rect" : "curve",
      strand: strandIds[index],
      x0: geometry[at],
      y0: geometry[at + 1],
      x1: geometry[at + 2],
      y1: geometry[at + 3],
      controlTop: geometry[at + 4],
      controlBottom: geometry[at + 5],
      alpha: header.band.alpha,
    };
    index += 1;
  }

  // The `order` a reversal shape rode in on is transport, not picture: it says
  // where the shape goes, and once it is there it has served its purpose.
  for (const band of bands) delete band.order;

  return {
    document: header.document,
    // Back into the spelling `emit-document.mjs` takes. The document writes
    // `rgb(r, g, b)` for a colour of either spelling, so nothing is lost by
    // having travelled as channels.
    strands: header.strands.map((strand) => ({
      ...strand,
      color: `rgb(${strand.color.join(", ")})`,
    })),
    bands,
    segments: header.segments,
    overlays: header.overlays,
  };
}

/**
 * One row of the strand table, as it goes on the wire.
 *
 * The layout's own row, with the colour resolved to channels. Everything else
 * passes through: the id `pgb` indexes by, the `sample#haplotype#contig#…` name
 * `vg` produced, and the PCLAI placement, each said once for the whole document.
 */
function strandRow(strand) {
  const color = rgbChannels(strand.color);
  if (color === null) {
    throw new Error(
      `strand ${strand.id} is coloured "${strand.color}", which is neither #rrggbb ` +
        "nor rgb(r, g, b). The band payload says a colour as its three channels, so " +
        "a spelling it cannot read is one it cannot carry.",
    );
  }
  return { ...strand, color };
}

function align4(bytes) {
  return (bytes + 3) & ~3;
}

function assertAddressable(strands) {
  if (strands.length <= MAX_STRAND_ROWS) return;
  throw new Error(
    `this document has ${strands.length} strand rows, and a band names its strand ` +
      `in 16 bits, which addresses ${MAX_STRAND_ROWS}. The band format cannot carry ` +
      "this document; request it as SVG, or widen the strand id — silently wrapping " +
      "would colour bands from the wrong strand.",
  );
}

function assertStrand(band, order, rows) {
  const { strand } = band;
  if (Number.isInteger(strand) && strand >= 0 && strand < rows) return;
  throw new Error(
    `the band at position ${order} names strand row ${strand}, which is not a row of ` +
      `the ${rows}-row strand table. Every band must resolve into the table it is ` +
      "sent with.",
  );
}

function assertAlpha(band, order) {
  if (band.alpha === BAND_ALPHA) return;
  throw new Error(
    `the band at position ${order} is drawn at opacity ${band.alpha}, and every band ` +
      `in a tube map is drawn at ${BAND_ALPHA}. The opacity is said once in the ` +
      "header rather than on every band, so a band of any other opacity is one this " +
      "format cannot carry. The layout draws one only for a read, which this fork " +
      "does not render.",
  );
}
