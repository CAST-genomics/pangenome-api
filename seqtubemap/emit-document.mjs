// Write a sequence tube map document from band data and nothing else.
//
// This is the sink the browser emulation used to be. The layout computes each
// band's geometry, colour, strand id and strand name; it used to bind all of
// that to elements in a jsdom document, which existed only so the result could
// be serialized to text and parsed straight back into numbers by the client.
// That document was 93.7% of the render's retained memory
// (docs/adr/0001-additive-band-format.md). Now the same numbers are collected as
// data (band-data.mjs) and this module turns them into the bytes.
//
// It is written *against the data*, with no access to the layout: everything it
// emits comes from the strand table, the bands, the segment boxes, the overlays
// and the document's dimensions. It began life as `tests/node/reconstruct-document.mjs`,
// the demonstration #21 shipped that the captured data was sufficient; this is
// that demonstration promoted to the thing that serves traffic.
//
// **The output is held compatible with `pgb`'s existing parser, deliberately.**
// `parseBands.ts` requires
//
//     style="fill: rgb(R, G, B); fill-opacity: 1;" trackID="N" trackName="…"
//
// contiguous and in that order, and counts the drawable elements in `g.track`.
// Both survive here, and `tests/node/document-conformance.test.mjs` is what
// holds them. What the jsdom document also wrote, and this does not, is the
// three things the client ignores: `color=`, which duplicated the colour already
// in `style=`; `class="track{id}"`, which duplicated `trackID`; and the empty
// `<title>` on every band and every segment box — 40,716 of them in one measured
// document. They were 16.6% of the payload.
//
// If a change here has to break that contract, stop and escalate: shipping
// against an unchanged `pgb` is the whole reason this increment is safe to ship
// alone.
//
// Since #23 that includes the geometry itself. The layout used to hand over each
// band's `d` attribute already built; now it hands over the six numbers the
// attribute encoded, and the drawing command is written here — so this module is
// the one place a band becomes a drawing at all.
import { BAND_THICKNESS, rgbChannels } from "./band-data.mjs";

/** The document this band data describes, in full. */
export function emitDocument(bandData) {
  const { document, strands, bands, segments, overlays } = bandData;
  return (
    `<svg id="mysvg" viewBox="${attribute(document.viewBox)}" ` +
    `width="${attribute(document.width)}" height="${attribute(document.height)}" ` +
    `xmlns="http://www.w3.org/2000/svg">` +
    `<g class="track">${bands.map((band) => bandElement(band, strands[band.strand])).join("")}</g>` +
    `<g class="node">${segments.map(segmentElement).join("")}</g>` +
    overlays.map(overlayElement).join("") +
    `</svg>`
  );
}

// Which element a band is drawn as, and the geometry attributes that go on it.
// The band data holds numbers (`band-data.mjs`); the drawing command is built
// here, and nowhere else, which is what "the document is derived from the band
// data" now means down to the `d` attribute.
function bandGeometry(band) {
  switch (band.kind) {
    case "rect":
      return {
        element: "rect",
        // A band's far end is carried as an abscissa and written back as a
        // width. `rectBand` is what holds the two spellings to the same number.
        attributes:
          ` x="${attribute(band.x0)}" y="${attribute(band.y0)}"` +
          ` width="${attribute(band.x1 - band.x0)}" height="${attribute(BAND_THICKNESS)}"`,
      };
    case "connector":
      return {
        element: "rect",
        attributes:
          ` x="${attribute(band.x)}" y="${attribute(band.y)}"` +
          ` width="${attribute(band.width)}" height="${attribute(band.height)}"`,
      };
    case "curve":
      return { element: "path", attributes: ` d="${attribute(curvePath(band))}"` };
    case "corner":
      return { element: "path", attributes: ` d="${attribute(cornerPath(band))}"` };
    default:
      // Loudly, like the builders that made these records: a kind this does not
      // know would otherwise be drawn as a curve with undefined coordinates —
      // a plausible-looking shape in the wrong place, which is the one failure
      // a document nobody diffs must not have.
      throw new Error(
        `a band of kind "${band.kind}" is not one this emitter can draw. ` +
          "Every kind band-data.mjs collects has to be written here.",
      );
  }
}

/**
 * A band's outline: along the upper edge, down by the thickness, back along the
 * lower edge, closed.
 *
 * Both cubics' control ordinates repeat the endpoints and the lower edge is the
 * upper edge shifted by `BAND_THICKNESS`, so the six numbers plus the constant
 * say the whole shape. `pgb`'s `assertGrammar` checks that redundancy on the way
 * back in, over the document this writes.
 */
function curvePath({ x0, y0, x1, y1, controlTop, controlBottom }) {
  const bottom0 = y0 + BAND_THICKNESS;
  const bottom1 = y1 + BAND_THICKNESS;
  return (
    `M ${x0} ${y0}` +
    ` C ${controlTop} ${y0} ${controlTop} ${y1} ${x1} ${y1}` +
    ` V ${bottom1}` +
    ` C ${controlBottom} ${bottom1} ${controlBottom} ${bottom0} ${x0} ${bottom0}` +
    " Z"
  );
}

/**
 * A reversal's quarter turn, from the near abscissa out to the bend and back.
 *
 * The two turns are the same shape read in opposite directions - the top one
 * reaches to the far abscissa first and the bottom one to the near - and the two
 * *directions* are mirror images, which is what the sign is. Written as one
 * builder rather than four, because four templates that must stay in step is how
 * the layout wrote it and is the reason a corner is hard to read at all.
 */
function cornerPath({ x, y, radius, bend, turn, direction }) {
  const sign = direction === "leftward" ? -1 : 1;
  const middle = x + radius * sign;
  const far = middle + bend * sign;
  const bottom = y + BAND_THICKNESS;

  if (turn === "bottom") {
    return (
      `M ${x} ${y} Q ${middle} ${y} ${middle} ${y - radius}` +
      ` H ${far} Q ${far} ${bottom} ${x} ${bottom} Z `
    );
  }
  return (
    `M ${x} ${y} Q ${far} ${y} ${far} ${bottom + radius}` +
    ` H ${middle} Q ${middle} ${bottom} ${x} ${bottom} Z `
  );
}

function bandElement(band, strand) {
  const { element, attributes: geometry } = bandGeometry(band);

  // A band paints an opacity when it has one. Corners never do, and neither do
  // the vertical rectangles of a reversal.
  const style =
    band.alpha === undefined
      ? css({ fill: cssColor(strand.color) })
      : css({ fill: cssColor(strand.color), "fill-opacity": band.alpha });

  // The fill style, the strand id and the strand name, contiguous and in that
  // order: this run is what `pgb`'s parseBands matches on, and nothing may be
  // inserted into it.
  return (
    `<${element}${geometry} style="${attribute(style)}"` +
    ` trackID="${attribute(strand.id)}"` +
    // A corner names no strand: the layout builds it without a name, and the
    // document has never carried one on it.
    (band.kind === "corner" ? "" : attr("trackName", strand.name)) +
    ` pclaiX="${attribute(orNone(strand.pclaiX))}"` +
    ` pclaiY="${attribute(orNone(strand.pclaiY))}"` +
    ` pclaiScore="${attribute(orNone(strand.pclaiScore))}"></${element}>`
  );
}

function segmentElement(segment) {
  const style = css({
    fill: cssColor(segment.fill),
    "fill-opacity": segment.fillOpacity,
    stroke: cssColor(segment.stroke),
    "stroke-width": segment.strokeWidth,
  });
  return (
    `<path id="${attribute(segment.id)}" d="${attribute(segmentOutline(segment.box))}"` +
    `${attr("sequence", segment.sequence)} style="${attribute(style)}"></path>`
  );
}

/**
 * A segment box's outline: four quarter-circle corners, joined by the straight
 * runs the box is long enough to have.
 *
 * Written here since #66, out of the five numbers the box travels as — the same
 * move #23 made for the bands, and for the same reason. The layout used to build
 * this string itself and hand it over finished.
 *
 * **A run appears only where there is room for one.** A box exactly `2 · radius`
 * wide is two corners meeting, with no top or bottom edge between them, and the
 * document writes no `L` for an edge of no length. That is not a rare case: it
 * is how most segment boxes of a real subgraph are drawn, since most segments
 * are short.
 *
 * **This moved the SVG route's bytes, by one ulp, in a handful of places**, and
 * the goldens were re-baselined for it. The layout used to walk the outline as a
 * running position — `x += pixelWidth`, `x += 9`, then back down again — so it
 * printed the same edge twice, one ulp apart, whenever those steps did not undo
 * each other exactly: `225.85714285714286` along the top and `225.8571428571429`
 * along the bottom of one box. Four to eight numbers per golden document, each
 * within 1.5e-16 of what it was, and no command anywhere changed. A box has one
 * left edge, so a document written from the numbers writes it once — which is
 * the whole of #66's argument, arriving in the SVG route as well: the string was
 * never quite the numbers.
 *
 * The same rounding is why the run test is `>` and not `>` some tolerance. One
 * box of the five real subgraphs — 1 of 1,219 — comes out 18 + 4.5e-13 wide
 * where its two corners are 18, because neither `x - 9` nor `x + 9` is exact,
 * so it is written with two straight runs of that length instead of none. A
 * tolerance would spell that box the shorter way, and it would be the first of
 * the nine tolerant comparisons this ticket exists to delete from the client.
 * The numbers are what the box is; this draws what they say.
 */
function segmentOutline({ left, top, right, bottom, radius }) {
  const run = right - left > 2 * radius;
  const rise = bottom - top > 2 * radius;

  // Clockwise from the top-left corner's lower end, which is where the layout
  // started it and therefore where the bytes start it.
  return (
    `M ${left} ${top + radius} Q ${left} ${top} ${left + radius} ${top}` +
    (run ? ` L ${right - radius} ${top}` : "") +
    ` Q ${right} ${top} ${right} ${top + radius}` +
    (rise ? ` L ${right} ${bottom - radius}` : "") +
    ` Q ${right} ${bottom} ${right - radius} ${bottom}` +
    (run ? ` L ${left + radius} ${bottom}` : "") +
    ` Q ${left} ${bottom} ${left} ${bottom - radius}` +
    (rise ? ` L ${left} ${top + radius}` : "")
  );
}

// The ruler and the segment labels, which are neither bands nor segment boxes.
// Their attributes arrive as an ordered list because the order is part of the
// bytes, and their values are already text.
function overlayElement({ element, attributes, text, title }) {
  const open =
    `<${element}` +
    attributes.map(([name, value]) => ` ${name}="${attribute(value)}"`).join("");
  const children =
    (text === undefined ? "" : content(text)) +
    (title === undefined ? "" : `<title>${content(title)}</title>`);
  return `${open}>${children}</${element}>`;
}

// An attribute the layout may not have a value for. The document leaves such an
// attribute off entirely rather than writing an empty one, so an unnamed strand
// or a segment with no sequence has no attribute at all.
function attr(name, value) {
  return value === null || value === undefined ? "" : ` ${name}="${attribute(value)}"`;
}

function orNone(value) {
  return value === null ? "None" : value;
}

function css(declarations) {
  return Object.entries(declarations)
    .map(([property, value]) => `${property}: ${value};`)
    .join(" ");
}

// The layout names colours as hex; a stylesheet says them as `rgb()`, and the
// document has always carried the stylesheet's spelling.
//
// A channel is rounded to a whole number on the way out, because `pgb`'s grammar
// matches `rgb\((\d+), (\d+), (\d+)\)` and refuses the whole document over a
// single band it cannot read. A PCLAI scheme supplies its channels as floats —
// the walks file carries them that way and `bandage_graph.py` parses them with
// `float()` — so a region whose scheme holds e.g. 228.5 emits a colour no client
// can parse. This is not new rounding: the emulated document rounded here too,
// in jsdom's CSS serializer, half away from zero, and this reproduces that.
function cssColor(color) {
  const channels = rgbChannels(color);
  return channels === null ? color : `rgb(${channels.join(", ")})`;
}

// A non-breaking space is written as an entity wherever it appears — in an
// attribute or in text — and is spelled `\u00a0` here because on the page it is
// indistinguishable from an ordinary space, which is *not* escaped. The golden
// bytes depend on the difference.
const NBSP = /\u00a0/g;

// The escaping an XML serializer applies inside an attribute value.
function attribute(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(NBSP, "&nbsp;");
}

// And inside text content, where a quote is ordinary and the angle brackets are not.
function content(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(NBSP, "&nbsp;");
}
