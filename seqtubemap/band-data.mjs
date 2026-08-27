// The band data a sequence tube map render produces: the numbers the layout
// computed, before anything turned them into attribute strings.
//
// Today the layout binds those numbers to elements in an emulated browser
// document and the document is what `/seqtubemap` returns. That document is
// 93.7% of the render's retained memory (docs/adr/0001-additive-band-format.md),
// and it exists only so the result can be serialized to text and parsed straight
// back into numbers by the client. Removing it means first making the numbers
// reachable, which is what this collector is for.
//
// The collector is not a second sink alongside the document. Each draw function
// collects what it is about to draw and then binds *the collected bands* as its
// d3 data, so the two cannot describe different pictures: band order is document
// order because it is the same list, in the same order, read twice.
//
// Shape of the data:
//
//   strands   one row per strand appearance: its id, name, colour, and PCLAI
//             placement. The per-band constants, sent once.
//   bands     one entry per drawn shape, in document order - which is draw
//             order, and therefore paint order: later bands draw on top.
//             `strand` indexes into `strands`.
//               { kind: "rect",   strand, x, y, width, height, alpha? }
//               { kind: "curve",  strand, path, alpha? }
//               { kind: "corner", strand, path }
//             Curves and corners carry the path string the layout built; making
//             those numbers too is a later increment.
//             `alpha` is the band's fill opacity, and is absent on the bands the
//             document has never painted one on: corners, and the vertical
//             rectangles of a reversal. That is a property of the shape rather
//             than of the strand, which is why opacity sits on the band while
//             colour sits on the strand.
//   segments  one entry per drawn segment box, in document order.
//   document  the picture's dimensions, including the viewBox string.

// The margins the document is given around the layout's extent: 50 px of slack
// on the width and height, and 20 px of headroom above the topmost shape.
const MARGIN = 50;
const HEADROOM = 20;

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

  /** Collect a band and return it, for the caller to bind and draw. */
  band(band) {
    this.bands.push(present(band));
    return band;
  }

  /** Collect a segment box and return it, for the caller to bind and draw. */
  segment(segment) {
    this.segments.push(present(segment));
    return segment;
  }

  setExtent(extent) {
    this.document = documentDimensions(extent);
  }

  /** Everything this render produced. Plain data - no DOM, no live references. */
  data() {
    return {
      strands: this.strands,
      bands: this.bands,
      segments: this.segments,
      document: this.document,
    };
  }
}
