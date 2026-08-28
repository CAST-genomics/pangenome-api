// What `pgb` requires of a `/seqtubemap` document, restated on this side.
//
// #22 removed the browser emulation and emitted the document from band data
// instead, **against an unchanged client**. That is what makes the increment safe
// to ship alone, and it is a constraint rather than an aspiration: the frontend is
// this ticket's conformance test in production, so a bad deploy surfaces as an
// error card rather than as a diff nobody ran. This file is the same check, run
// before the deploy.
//
// It is *not* a copy of `parseBands.ts`, and the real cross-repo test is still
// [#25](https://github.com/CAST-genomics/PangenomeAPI/issues/25)'s, which runs
// `pgb`'s own parser in `pgb`'s CI over fixtures committed here. Two parsers that
// must agree is the failure mode this whole effort exists to remove. What this
// asserts is the narrower thing: that a document satisfies the grammar `pgb`
// matches on, so a change to the emitter cannot quietly stop producing one.
//
// **The grammar below is transcribed from `pgb/src/tubemap/parseBands.ts`, read on
// 2026-08-28.** It was verified the same day by running that file over all five
// real subgraphs, before and after #22: `pgb` accepted every one and recovered
// bit-identical arrays from both sides. An earlier version of this file was looser
// than the real thing in two ways — it made `fill-opacity` and `trackName`
// optional — which made it pass documents `pgb` would refuse outright. Leniency
// here is worse than useless: it is false assurance about somebody else's gate.
//
// What `pgb` requires, in its own terms:
//
//   1. Bands live in `g.track` — everything before `<g class="node"`. A band is a
//      `<rect>` or a `<path>`, and `pgb` **counts** them with `countOccurrences`.
//   2. Every counted drawable must match the grammar. If fewer match than were
//      counted, `pgb` throws `NonConformingDocument` and **refuses the whole
//      document** — "a half-drawn map looks like a correct map of different data".
//   3. The fill run is exact: `style="fill: rgb(R, G, B); fill-opacity: 1;"`
//      followed immediately by `trackID`, then `trackName`, which must be
//      non-empty. Nothing may come between them.
//   4. `trackID` runs 0..n-1 with no gaps, and stays within Uint16.
//   5. A `<rect>` is exactly `THICKNESS` (15) tall with positive width.
//
// Note what `pgb` deliberately tolerates, because it is the reason #22 could ship
// at all: between `trackName` and the PCLAI attributes it matches `[^>]*?` rather
// than naming `class` and `color`, "so a document that adds an attribute there
// still parses". Removing those two attributes was invisible to it for the same
// reason. Strand names are likewise opaque strings — `pgb` never splits on `#`, so
// `vg`'s phase-block and subrange tails ride through verbatim.
//
// **A shape this layout can draw and `pgb` cannot read.** A reversal's corners and
// vertical rectangles carry no `fill-opacity`, a corner carries no `trackName`, and
// a corner's path is built from quadratics where the grammar wants cubics. Any one
// of those makes the count in rule 2 disagree and refuses the document whole. No
// committed fixture contains a reversal, and none of the five real subgraphs draws
// a single corner — so this is latent rather than live, and it predates #22
// entirely. It is
// [#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52), and
// `document-conformance.test.mjs` pins it with a synthetic reversal.
import assert from "node:assert/strict";

/** `pgb`'s own number pattern (documentGrammar.ts), so the two cannot disagree. */
const N = "(-?[\\d.]+(?:[eE]-?\\d+)?)";

/**
 * The run `pgb` matches on, verbatim from `parseBands.ts`.
 *
 * `fill-opacity: 1;` is a required literal and `trackName` must be non-empty —
 * both are load-bearing, and both were wrong here before 2026-08-28.
 */
const FILL =
  'style="fill: rgb\\((\\d+), (\\d+), (\\d+)\\); fill-opacity: 1;" trackID="(\\d+)"' +
  ' trackName="([^"]+)"' +
  '(?:[^>]*? pclaiX="([^"]*)" pclaiY="([^"]*)" pclaiScore="([^"]*)")?';

const RECT = `<rect x="${N}" y="${N}" width="${N}" height="${N}" ${FILL}`;
const PATH =
  `<path d="M ${N} ${N} C ${N} ${N} ${N} ${N} ${N} ${N} V ${N} ` +
  `C ${N} ${N} ${N} ${N} ${N} ${N} Z" ${FILL}`;

const ELEMENT = new RegExp(`(?:${RECT})|(?:${PATH})`, "g");

/** Every band in a tube map is this tall; `pgb` refuses any other height. */
const THICKNESS = 15;

/** Largest strand id `pgb`'s Uint16 instance buffer can hold. */
const MAX_STRAND_ID = 65535;

/**
 * The bands `pgb` can read out of a document, and how many drawables were there
 * to read. When the two disagree, `pgb` refuses the document whole.
 */
export function readBands(document) {
  const trackGroup = strandGroup(document);
  const counted =
    countOccurrences(trackGroup, "<rect") + countOccurrences(trackGroup, "<path");

  const matched = [];
  ELEMENT.lastIndex = 0;
  let match;
  while ((match = ELEMENT.exec(trackGroup)) !== null) {
    const isRect = match[1] !== undefined;
    matched.push(
      isRect
        ? { isRect, height: +match[4], width: +match[3], id: +match[8], name: match[9] }
        : { isRect, id: +match[31], name: match[32] },
    );
  }
  return { counted, matched };
}

/** The `<g class="track">` slice — everything before the segment boxes, as `pgb` cuts it. */
export function strandGroup(document) {
  const open = '<g class="track">';
  const start = document.indexOf(open);
  assert.notEqual(start, -1, "the document has no g.track group");
  // `pgb` slices at `<g class="node"`, not at the group's own close.
  const end = document.indexOf('<g class="node"');
  return document.slice(start + open.length, end === -1 ? undefined : end);
}

/** The `<g class="node">` slice, which is where the segment boxes are. */
export function segmentGroup(document) {
  const start = document.indexOf('<g class="node">');
  assert.notEqual(start, -1, "the document has no g.node group");
  const end = document.indexOf("</g>", start);
  assert.notEqual(end, -1, "the document's g.node group is not closed");
  return document.slice(start + '<g class="node">'.length, end);
}

/** Every drawable element of the strand group, as its opening tag. */
export function drawables(document) {
  return [...strandGroup(document).matchAll(/<(?:rect|path)\b[^>]*>/g)].map(([tag]) => tag);
}

function countOccurrences(text, needle) {
  let total = 0;
  let at = text.indexOf(needle);
  while (at !== -1) {
    total += 1;
    at = text.indexOf(needle, at + needle.length);
  }
  return total;
}

/**
 * Throw unless `pgb` would accept this document.
 *
 * @param {string} document
 * @param {object} [bandData] the render's band data, when the caller has it — the
 *   drawable count is checked against it as well, which catches an emitter that
 *   drops a band and a parser that skips one in the same pass.
 */
export function assertParseableByPgb(document, bandData) {
  assert.ok(document.includes("<svg"), "the response is not an SVG document");
  assert.match(document, /viewBox="[^"]+"/, "the document declares no viewBox");

  const { counted, matched } = readBands(document);
  assert.ok(counted > 0, "the document draws no bands at all; its g.track group is empty");

  // `pgb`'s whole-document gate, and the reason a single unreadable shape is not a
  // cosmetic problem: it refuses everything rather than draw a partial map.
  assert.equal(
    matched.length,
    counted,
    `of the ${counted} drawables in g.track, ${counted - matched.length} are not bands pgb ` +
      "recognises, and pgb refuses a document whole when that count disagrees. " +
      REVERSAL_GAP,
  );

  const ids = new Set();
  for (const band of matched) {
    assert.ok(band.name.length > 0, "a band carries an empty trackName");
    assert.ok(band.id <= MAX_STRAND_ID, `a band carries trackID ${band.id}, above pgb's Uint16 ceiling`);
    if (band.isRect) {
      assert.equal(band.height, THICKNESS, `a rect band is ${band.height} units tall, not ${THICKNESS}`);
      assert.ok(band.width > 0, `a rect band is ${band.width} units wide; width must be positive`);
    }
    ids.add(band.id);
  }

  for (let id = 0; id < ids.size; id += 1) {
    assert.ok(ids.has(id), `trackID ${id} is missing; pgb rejects a document with a gap`);
  }

  // The three things the client ignores, and that the emitter stopped writing.
  // Checked by *place*: what went is the empty title on every band and every
  // segment box, and a title carrying text is a different element — upstream hangs
  // a read's mismatch sequence on one, which this fork never draws but the emitter
  // can still write.
  for (const [name, contents] of [
    ["g.track", strandGroup(document)],
    ["g.node", segmentGroup(document)],
  ]) {
    assert.ok(!contents.includes("<title>"), `the title elements are back in ${name}`);
  }
  assert.ok(!document.includes("<title></title>"), "an empty title element is back");
  assert.ok(!/ class="track\d+"/.test(document), "the duplicate class attribute is back");
  assert.ok(!/ color="/.test(document), "the duplicate colour attribute is back");

  if (bandData) {
    assert.equal(
      counted,
      bandData.bands.length,
      "the strand group's drawable count is not the band count",
    );
  }
}

/**
 * Why a document carrying a reversal would be refused — quoted into the failure
 * above, because that is where somebody will meet it.
 *
 * This is a standing incompatibility between what the layout can draw and what the
 * client can read. It predates #22 and #22 did not change it either way.
 */
export const REVERSAL_GAP =
  "The known cause is a reversal: its corners carry no trackName and are built from " +
  "quadratics where pgb's grammar wants cubics, and neither its corners nor its vertical " +
  "rectangles carry the `fill-opacity: 1;` the grammar requires. No committed fixture " +
  "contains one, and none of the five real subgraphs draws a corner. This is issue #52.";
