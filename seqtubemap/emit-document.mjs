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

function bandElement(band, strand) {
  const geometry =
    band.kind === "rect"
      ? ` x="${attribute(band.x)}" y="${attribute(band.y)}"` +
        ` width="${attribute(band.width)}" height="${attribute(band.height)}"`
      : ` d="${attribute(band.path)}"`;

  // A band paints an opacity when it has one. Corners never do, and neither do
  // the vertical rectangles of a reversal.
  const style =
    band.alpha === undefined
      ? css({ fill: cssColor(strand.color) })
      : css({ fill: cssColor(strand.color), "fill-opacity": band.alpha });

  const element = band.kind === "rect" ? "rect" : "path";
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
    `<path id="${attribute(segment.id)}" d="${attribute(segment.outline)}"` +
    `${attr("sequence", segment.sequence)} style="${attribute(style)}"></path>`
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
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(color);
  if (!hex) return wholeChannels(color); // already `rgb(r, g, b)` — what a PCLAI scheme supplies
  const [r, g, b] = hex.slice(1).map((pair) => parseInt(pair, 16));
  return `rgb(${r}, ${g}, ${b})`;
}

// `rgb(r, g, b)` with each channel a whole number in 0..255, as a stylesheet
// would serialize it. Anything that is not that spelling is left alone.
function wholeChannels(color) {
  const rgb = /^rgb\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)$/.exec(String(color));
  if (!rgb) return color;
  const channels = rgb.slice(1).map((channel) => {
    const value = Math.round(Number(channel));
    return Math.min(255, Math.max(0, value));
  });
  return `rgb(${channels.join(", ")})`;
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
