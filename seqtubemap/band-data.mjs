// The band data a sequence tube map render produces: the numbers the layout
// computed, before anything turned them into attribute strings.
//
// The layout used to bind those numbers to elements in an emulated browser
// document, and that document was what `/seqtubemap` returned — 93.7% of the
// render's retained memory (docs/adr/0001-additive-band-format.md), existing
// only so the result could be serialized to text and parsed straight back into
// numbers by the client. #21 made the numbers reachable through this collector;
// #22 deleted the document and pointed `emit-document.mjs` at the collector
// instead.
//
// So this is not a sink alongside the document — it is the only description of
// the picture there is. Each draw function collects what it draws and draws
// nothing else, which is why band order is document order: the emitter walks
// this list, in this order.
//
// Shape of the data:
//
//   strands   one row per strand appearance: its id, name, colour, and PCLAI
//             placement. The per-band constants, sent once.
//   bands     one entry per drawn shape, in document order - which is draw
//             order, and therefore paint order: later bands draw on top.
//             `strand` indexes into `strands`.
//               { kind: "rect",     strand, x0, y0, x1, y1, controlTop, controlBottom, alpha? }
//               { kind: "curve",    strand, x0, y0, x1, y1, controlTop, controlBottom, alpha? }
//               { kind: "corner",   strand, x, y, radius, bend, turn, direction }
//               { kind: "connector", strand, x, y, width, height }
//             `alpha` is the band's fill opacity, and is absent on the bands the
//             document has never painted one on: corners, and the vertical
//             rectangles of a reversal. That is a property of the shape rather
//             than of the strand, which is why opacity sits on the band while
//             colour sits on the strand.
//   segments  one entry per drawn segment box, in document order.
//   overlays  the handful of elements a document carries besides its bands and
//             segment boxes - the ruler's axis, ticks and labels, and the
//             segment sequence labels "normal" width mode draws. One entry per
//             element, in document order, each an element name and its
//             attributes as an ordered list of pairs, because attribute order
//             is part of the bytes. Production documents contain none of these:
//             a real subgraph carries no reference offset, so it gets no ruler
//             (docs/adr/0001-additive-band-format.md).
//   document  the picture's dimensions, including the viewBox string.
//
// A band is six numbers and a strand id.
//
// The layout used to build each band's `d` attribute as a finished drawing
// command - `"M … C … V … C … Z"` - and `pgb` parsed it straight back into six
// floats with a regular expression. The string was an encoding step in the
// middle of a numeric pipeline, so #23 removed it: the numbers are collected
// here and `emit-document.mjs` writes the drawing command out of them.
//
// The six are `x0, y0` and `x1, y1` - the two ends of the band's upper edge -
// and `controlTop, controlBottom`, the control abscissae of the upper and lower
// edges. Every surveyed band conforms to that grammar with a **constant
// thickness** (`BAND_THICKNESS`), which is what makes six enough: the lower edge
// is the upper edge shifted down by it, and both cubics' control ordinates
// repeat the endpoints. That was measured across 127,101 strand paths, and it is
// what `pgb` refuses a document over rather than what it hopes for
// (`parseBands.ts`, ADR `0002` in that repository). A band the layout draws off
// that grammar throws here, where the layout that produced it is still in scope,
// rather than reaching a client that would refuse the whole document.
//
// `curve` and `rect` are one primitive in two spellings, not two shapes. A rect
// is the degenerate band - level, so any control abscissa reproduces it and the
// midpoint is taken - and `pgb` reads it back into the same six values. `kind`
// survives because it says which element the document writes.
//
// **The two reversal shapes are outside that grammar**, and are their own kinds
// rather than bands with impossible numbers. A corner is a quarter turn built
// from quadratics; a vertical connector is a rect as tall as the reversal is
// deep, which is not `BAND_THICKNESS` and is not meant to be. `pgb` cannot read
// either one today and refuses any document containing one - which is issue #52,
// and is where what they mean on the band route gets decided.
//
// Strand ids are dense and positional. A strand's `id` is the position the
// layout gave it (reorderTracksForLayout in tubemap.js), it reaches the client
// as the document's `trackID`, and the client indexes tables by it: `pgb`'s
// parseBands rejects the whole document with "trackID must run from 0 upward
// with no gaps" if the set of ids is not exactly 0..n-1.
//
// Nothing about the layout guarantees that on its own. `createTubeMap` splices
// hidden strands out of the array *after* ids are assigned, so a strand dropped
// there would leave a hole, and the failure would surface in the other
// repository as an unparseable document rather than here. `assertDenseStrandIds`
// is what turns the accident into a checked invariant; see the test in
// tests/node/band-data.test.mjs.

// The margins the document is given around the layout's extent: 50 px of slack
// on the width and height, and 20 px of headroom above the topmost shape.
const MARGIN = 50;
const HEADROOM = 20;

/**
 * How thick every band in a tube map is.
 *
 * Constant, and load-bearing: it is the value that lets six numbers describe a
 * band, so it is said once here rather than carried on every one of the 55,053
 * bands a real subgraph draws. `pgb` holds the same constant and refuses a
 * document whose bands are any other thickness (`THICKNESS`, parseBands.ts).
 *
 * The layout can in principle produce another: a strand carrying a `freq` field,
 * or a read, is drawn narrower (`calculateTrackWidth`). No document this
 * repository has ever seen contains one - every band of all five real subgraphs
 * and every golden is exactly 15 - and this fork draws no reads at all, since
 * `render.mjs` passes none. So the case is unreachable rather than merely
 * unobserved, and the builders below throw on it rather than encode a band the
 * numbers do not describe.
 */
export const BAND_THICKNESS = 15;

/**
 * One band of the layout's curved kind, as numbers.
 *
 * @param {object} shape
 * @param {number} shape.strand         index into the strand table
 * @param {number} shape.x0             near end of the upper edge
 * @param {number} shape.y0
 * @param {number} shape.x1             far end of the upper edge
 * @param {number} shape.y1
 * @param {number} shape.controlTop     control abscissa of the upper edge
 * @param {number} shape.controlBottom  control abscissa of the lower edge
 * @param {number} shape.thickness      checked against `BAND_THICKNESS`, not carried
 * @param {number} [shape.alpha]        fill opacity, where the document paints one
 */
export function curveBand({
  strand,
  x0,
  y0,
  x1,
  y1,
  controlTop,
  controlBottom,
  thickness,
  alpha,
}) {
  assertThickness(thickness, "curve");
  return present({ kind: "curve", strand, x0, y0, x1, y1, controlTop, controlBottom, alpha });
}

/**
 * The same band, drawn flat.
 *
 * Takes the layout's own spelling - a corner and an extent - and stores the six
 * values every band has. The control abscissae are the midpoint, which is what
 * `pgb` fills in for a `<rect>`: both edges are level, so any abscissa
 * reproduces the shape and the two sides may as well agree on which.
 *
 * @param {object} shape
 * @param {number} shape.strand
 * @param {number} shape.x       left edge
 * @param {number} shape.y       upper edge
 * @param {number} shape.width
 * @param {number} shape.height  checked against `BAND_THICKNESS`, not carried
 * @param {number} [shape.alpha]
 */
export function rectBand({ strand, x, y, width, height, alpha }) {
  assertThickness(height, "rect");

  const x1 = x + width;

  // The document writes a rect as an abscissa and a width, and the band data
  // holds two abscissae, so the round trip turns on `(x + width) - x` giving
  // back exactly `width`. It does for every band in every fixture here - the
  // layout's coordinates are far below the magnitude where it stops - and a band
  // that lands where it does not is a band whose width the document would round,
  // which is the silent mis-encoding this whole change must not introduce.
  if (x1 - x !== width) {
    throw new Error(
      `a band at x=${x} is ${width} units wide, which cannot be written down and read ` +
        `back: x + width - x gives ${x1 - x}. The layout has produced coordinates too ` +
        "large for a width to survive being carried as two abscissae.",
    );
  }

  const middle = x + (x1 - x) * 0.5;

  return present({
    kind: "rect",
    strand,
    x0: x,
    y0: y,
    x1,
    y1: y,
    controlTop: middle,
    controlBottom: middle,
    alpha,
  });
}

/**
 * One quarter turn of a reversal.
 *
 * Not a band: it is built from quadratics and it is the shape `pgb` refuses a
 * document over (#52). Its numbers are the layout's own parameters, which is
 * what the document is written back out of.
 *
 * @param {object} shape
 * @param {number} shape.strand
 * @param {number} shape.x          abscissa the turn starts from
 * @param {number} shape.y          the ordinate it turns at
 * @param {number} shape.radius     the bend's radius
 * @param {number} shape.bend       how far past the radius the turn reaches
 * @param {number} shape.thickness  checked against `BAND_THICKNESS`, not carried
 * @param {"top"|"bottom"} shape.turn            which end of the reversal this is
 * @param {"rightward"|"leftward"} shape.direction  which way it reaches
 */
export function cornerShape({ strand, x, y, radius, bend, thickness, turn, direction }) {
  assertThickness(thickness, "corner");
  return { kind: "corner", strand, x, y, radius, bend, turn, direction };
}

/**
 * A reversal's vertical connector: the rect that spans between its two turns.
 *
 * As tall as the reversal is deep - 19 and 39 units in the synthetic inversion
 * the tests build - so it carries its own height rather than borrowing the
 * band's. Like a corner, `pgb` cannot read it (#52).
 *
 * @param {object} shape
 * @param {number} shape.strand
 * @param {number} shape.x
 * @param {number} shape.y
 * @param {number} shape.width
 * @param {number} shape.height
 * @param {number} [shape.alpha]
 */
export function verticalConnector({ strand, x, y, width, height, alpha }) {
  return present({ kind: "connector", strand, x, y, width, height, alpha });
}

/**
 * One segment box, as the five numbers that describe it.
 *
 * Every box the layout draws is a rounded rectangle — four quarter-circle
 * corners of one radius, joined by straight runs — and it has these five numbers
 * before it builds anything. It used to travel as the path command they were
 * built into (`M 11 20 Q 11 11 20 11 …`), which a client took apart again with a
 * regular expression: the same encoding step in the middle of a numeric pipeline
 * that #23 removed from the bands, one shape down (#66). The numbers travel and
 * `emit-document.mjs` writes the drawing command out of them.
 *
 * A box narrower or shorter than the two corners it is drawn with is not a
 * rounded rectangle, and five numbers that say one thing while the layout drew
 * another is the silent mis-encoding this must not introduce. So it throws here,
 * where the layout that produced it is still in scope, rather than reaching a
 * client that would draw a shape the server never drew.
 *
 * @param {object} box
 * @param {number} box.left    the box's edges, in the document's own coordinates
 * @param {number} box.top
 * @param {number} box.right
 * @param {number} box.bottom
 * @param {number} box.radius  the corner radius, the same at all four corners
 */
export function segmentBox({ left, top, right, bottom, radius }) {
  for (const [name, value] of Object.entries({ left, top, right, bottom, radius })) {
    if (!Number.isFinite(value)) {
      throw new Error(
        `a segment box's ${name} is ${value}, which is not a number. A box travels as ` +
          "five numbers, so a layout quantity that never arrived would otherwise reach " +
          "the client as null and be drawn as a rectangle nobody laid out.",
      );
    }
  }
  if (radius <= 0) {
    throw new Error(
      `a segment box has a corner radius of ${radius}, and every box the layout draws ` +
        "is drawn with rounded corners. A radius that is not positive describes no arc.",
    );
  }
  if (right - left < 2 * radius || bottom - top < 2 * radius) {
    throw new Error(
      `a segment box ${right - left} wide and ${bottom - top} tall is not a rounded ` +
        `rectangle with a corner radius of ${radius}: its two corners alone are ` +
        `${2 * radius}. The layout has drawn a box these five numbers do not describe.`,
    );
  }
  return { left, top, right, bottom, radius };
}

function assertThickness(thickness, kind) {
  if (thickness === BAND_THICKNESS) return;
  throw new Error(
    `a ${kind} band is ${thickness} units thick, and every band in a tube map is ` +
      `${BAND_THICKNESS}. Six numbers describe a band only because the thickness is ` +
      "constant, and pgb refuses a document whose bands are any other thickness. " +
      "The layout draws a narrower band for a strand carrying a `freq` field and for a " +
      "read, neither of which this fork renders.",
  );
}

/** The document's dimensions for a layout that ended up with this extent. */
export function documentDimensions({ maxXCoordinate, maxYCoordinate, minYCoordinate }) {
  const width = maxXCoordinate + MARGIN;
  const height = maxYCoordinate - minYCoordinate + MARGIN;
  return {
    width,
    height,
    viewBox: `0 ${minYCoordinate - HEADROOM} ${width} ${height}`,
    extent: { maxXCoordinate, maxYCoordinate, minYCoordinate },
  };
}

// A property the layout has no value for is absent, not undefined: the document
// leaves such an attribute off entirely, and the band data has to survive a
// round trip through JSON, which drops undefined values anyway.
function present(record) {
  for (const key of Object.keys(record)) {
    if (record[key] === undefined) delete record[key];
  }
  return record;
}

export class BandCollector {
  constructor() {
    this.reset();
  }

  reset() {
    this.strands = [];
    this.bands = [];
    this.segments = [];
    this.overlays = [];
    // The extent a render that draws nothing has, so that an empty render still
    // reports the dimensions its document would be given.
    this.document = documentDimensions({
      maxXCoordinate: 0,
      maxYCoordinate: 0,
      minYCoordinate: 0,
    });
    this.rowByKey = new Map();
  }

  /**
   * The index of the strand row for a shape, adding the row if it is new.
   *
   * A row is a strand *appearance* - an id and a colour. In practice that is
   * one row per strand; a strand only gets a second row if something recolours
   * part of it, and then the extra row is the truth about the picture rather
   * than a defect in the table.
   *
   * Not every shape knows its strand's name: the layout builds the corners of a
   * reversal without one. Such a shape still finds its strand's row - by id and
   * colour - and the row keeps the name and placement the strand's other bands
   * supplied, which is the point of a table the bands can point at.
   */
  strand({ id, name, color, pclaiX, pclaiY, pclaiScore }) {
    const key = `${id} ${color}`;
    const index = this.rowByKey.get(key);
    if (index === undefined) {
      this.rowByKey.set(key, this.strands.length);
      this.strands.push(present({ id, name, color, pclaiX, pclaiY, pclaiScore }));
      return this.strands.length - 1;
    }
    const row = this.strands[index];
    if (row.name === undefined && name !== undefined) {
      Object.assign(row, { name, pclaiX, pclaiY, pclaiScore });
    }
    return index;
  }

  /** The strand row a band belongs to. */
  strandOf(band) {
    return this.strands[band.strand];
  }

  /**
   * Collect one shape, built by `curveBand`, `rectBand`, `cornerShape` or
   * `verticalConnector` — which is where its numbers are checked against the
   * grammar, before it is collected at all.
   *
   * Nothing is re-checked here. A record that reached this list some other way
   * is caught at the other end instead: `emit-document.mjs` knows the four kinds
   * and throws on a fifth, rather than drawing it as something plausible.
   */
  band(band) {
    this.bands.push(band);
    return band;
  }

  /** Collect a segment box and return it, for the caller to bind and draw. */
  segment(segment) {
    this.segments.push(present(segment));
    return segment;
  }

  /**
   * Collect one overlay element.
   *
   * `attributes` is a list of pairs rather than an object because the document
   * writes them in the order they were set, and that order is part of the
   * bytes. Values are stringified here, so a collected overlay survives a round
   * trip through JSON as the very text the document will carry.
   */
  overlay({ element, attributes, text, title }) {
    this.overlays.push(
      present({
        element,
        attributes: attributes.map(([name, value]) => [name, String(value)]),
        text: text === undefined ? undefined : String(text),
        title: title === undefined ? undefined : String(title),
      }),
    );
  }

  setExtent(extent) {
    this.document = documentDimensions(extent);
  }

  /** Everything this render produced. Plain data - no DOM, no live references. */
  data() {
    assertDenseStrandIds(this.strands);
    return {
      strands: this.strands,
      bands: this.bands,
      segments: this.segments,
      overlays: this.overlays,
      document: this.document,
    };
  }
}

/**
 * Throw unless the strand ids are exactly 0..n-1.
 *
 * Checked here rather than left to the client, because here the layout that
 * produced the hole is still in scope: a document that fails this is one `pgb`
 * refuses outright, and a failure in this repository names the cause.
 *
 * A strand may hold more than one row - a recolouring gives it a second - so it
 * is the *set* of ids that must be dense, not the row count.
 */
export function assertDenseStrandIds(strands) {
  const ids = new Set(strands.map((strand) => strand.id));
  for (let id = 0; id < ids.size; id += 1) {
    if (!ids.has(id)) {
      const highest = Math.max(...ids);
      throw new Error(
        `strand ids must run from 0 upward with no gaps: ${ids.size} strands, ` +
          `numbered up to ${highest}, with ${id} missing. ` +
          "A strand was dropped after reorderTracksForLayout numbered it.",
      );
    }
  }
}

/**
 * A colour's three channels, each a whole number in 0..255 — or null for a
 * spelling this does not recognise, which a caller then carries verbatim.
 *
 * Here rather than in either sink, because both need it and neither owns it.
 * The document writes a colour as CSS `rgb(r, g, b)`; the band payload writes
 * it as three numbers, since a client building a GPU buffer wants numbers and
 * asking it to parse the two spellings the layout uses — hex from the palettes,
 * `rgb()` from a PCLAI scheme, whose channels can be fractional — would be
 * handing it the parse step that format exists to delete. One rounding, in one
 * place, so the two encodings cannot disagree about a colour.
 */
export function rgbChannels(color) {
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(color);
  if (hex) return hex.slice(1).map((pair) => parseInt(pair, 16));

  const rgb = /^rgb\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)$/.exec(String(color));
  if (!rgb) return null;
  return rgb.slice(1).map((channel) => {
    const value = Math.round(Number(channel));
    return Math.min(255, Math.max(0, value));
  });
}
