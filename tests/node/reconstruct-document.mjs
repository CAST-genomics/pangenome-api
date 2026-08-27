// Rebuild a sequence tube map document from band data and nothing else.
//
// This exists to demonstrate a claim, not to serve traffic: that the data
// captured in `seqtubemap/band-data.mjs` is sufficient to reconstruct the
// document the layout currently builds. The emitter that replaces the browser
// emulation is a later increment; this is the proof that it can be written.
//
// So it is deliberately written *against the data*, with no access to the
// layout: everything it emits comes from the strand table, the bands, the
// segment boxes and the document's dimensions. If something needed to draw the
// picture were missing from the band data, this file could not compile it, and
// the test that uses it would fail with a byte offset.
//
// What it does not cover is the ruler — the axis, ticks and labels a fixture
// with a reference offset gets. Those are not bands, they are not segment
// boxes, and production documents contain none of them (see
// docs/adr/0001-additive-band-format.md, "There are zero `<text>` and zero
// `<line>` elements"). The caller compares the reconstruction against the
// document's leading bytes for that reason.

/** The document that this band data describes, up to the end of the segment boxes. */
export function reconstructDocument(bandData) {
  const { document, strands, bands, segments } = bandData;
  return (
    `<svg id="mysvg" viewBox="${attribute(document.viewBox)}" ` +
    `width="${attribute(document.width)}" height="${attribute(document.height)}" ` +
    `xmlns="http://www.w3.org/2000/svg">` +
    `<g class="track">${bands.map((band) => bandElement(band, strands[band.strand])).join("")}</g>` +
    `<g class="node">${segments.map(segmentElement).join("")}</g>`
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
  return (
    `<${element}${geometry} style="${attribute(style)}"` +
    // A corner names no strand: the layout builds it without a name, and the
    // document has never carried one on it.
    ` trackID="${attribute(strand.id)}"` +
    (band.kind === "corner" ? "" : attr("trackName", strand.name)) +
    ` class="track${attribute(strand.id)}" color="${attribute(strand.color)}"` +
    ` pclaiX="${attribute(orNone(strand.pclaiX))}"` +
    ` pclaiY="${attribute(orNone(strand.pclaiY))}"` +
    ` pclaiScore="${attribute(orNone(strand.pclaiScore))}">` +
    `<title></title></${element}>`
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
    `${attr("sequence", segment.sequence)} style="${attribute(style)}">` +
    `<title></title></path>`
  );
}

// An attribute the layout may not have a value for. d3 removes an attribute
// whose value is null or undefined rather than writing an empty one, so an
// unnamed strand or a segment with no sequence has no attribute at all.
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
function cssColor(color) {
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(color);
  if (!hex) return color; // already `rgb(r, g, b)` — what a PCLAI scheme supplies
  const [r, g, b] = hex.slice(1).map((pair) => parseInt(pair, 16));
  return `rgb(${r}, ${g}, ${b})`;
}

// The escaping an XML serializer applies inside an attribute value.
function attribute(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/ /g, "&nbsp;");
}
