// What `pgb` requires of a `/seqtubemap` document, written down on this side.
//
// #22 removed the browser emulation and emitted the document from band data
// instead, **against an unchanged client**. That is what makes the increment
// safe to ship alone, and it is a constraint rather than an aspiration: the
// frontend is this ticket's conformance test in production, so a bad deploy
// surfaces as an error card rather than as a diff nobody ran. This file is the
// same check, run before the deploy.
//
// It is *not* a copy of `parseBands.ts`. Two implementations of a parser that
// must agree is precisely the failure mode this whole effort exists to remove,
// and the real cross-repo test is #25's, which runs `pgb`'s own parser over
// fixtures committed here. What this asserts is the narrower thing #22 promised
// not to break, in the terms `pgb` states it:
//
//   1. Bands live in `g.track`, and a band is a `<rect>` or a `<path>`. `pgb`
//      counts them to size its buffers, so the count is part of the contract.
//   2. Every band carries its fill style, its `trackID` and — unless it is a
//      corner, which has never had one — its `trackName`, **contiguous and in
//      that order**. `pgb` matches that run with one regular expression; an
//      attribute inserted into the middle of it breaks every band.
//   3. `trackID` runs 0..n-1 with no gaps, because `pgb` indexes tables by it
//      and rejects the whole document otherwise.
//
// And what the client ignores, which #22 stopped writing: the `color=`
// duplicating the colour already in `style=`, the `class="track{id}"`
// duplicating `trackID`, and the empty `<title>` on every band and segment box.
// Those are asserted absent too — not because their return would break `pgb`,
// but because they are 16.6% of the payload and their absence is what this
// increment bought.
import assert from "node:assert/strict";

// The run `pgb`'s parseBands matches: fill, optional opacity, id, optional name.
// A corner carries no name and a reversal's vertical rectangle no opacity, so
// both are optional — but nothing may come between them.
const BAND_ATTRIBUTES =
  /style="fill: rgb\(\d+, \d+, \d+\);( fill-opacity: [^;"]+;)?" trackID="(\d+)"( trackName="[^"]*")?/;

/** The `<g class="track">` group's contents, which is where the bands are. */
export function strandGroup(document) {
  return group(document, "track");
}

/** The `<g class="node">` group's contents, which is where the segment boxes are. */
export function segmentGroup(document) {
  return group(document, "node");
}

// Neither group nests another, so the first `</g>` after the open is its close.
function group(document, name) {
  const open = `<g class="${name}">`;
  const start = document.indexOf(open);
  assert.notEqual(start, -1, `the document has no g.${name} group`);
  const end = document.indexOf("</g>", start);
  assert.notEqual(end, -1, `the document's g.${name} group is not closed`);
  return document.slice(start + open.length, end);
}

/** Every drawable element of the strand group, as its opening tag. */
export function drawables(document) {
  return [...strandGroup(document).matchAll(/<(?:rect|path)\b[^>]*>/g)].map(([tag]) => tag);
}

/**
 * Throw unless `pgb` can parse this document.
 *
 * @param {string} document
 * @param {object} [bandData] the render's band data, when the caller has it —
 *   the drawable count is checked against it, which is the closest thing to
 *   `pgb`'s own whole-document check that this side can run.
 */
export function assertParseableByPgb(document, bandData) {
  const elements = drawables(document);
  assert.ok(elements.length > 0, "no bands in the document's strand group");

  const ids = new Set();
  for (const element of elements) {
    const match = BAND_ATTRIBUTES.exec(element);
    assert.ok(
      match,
      "a band does not carry the fill-style / trackID / trackName run pgb matches on:\n  " +
        element.slice(0, 240),
    );
    ids.add(Number(match[2]));
  }

  for (let id = 0; id < ids.size; id += 1) {
    assert.ok(ids.has(id), `trackID ${id} is missing; pgb rejects a document with a gap`);
  }

  // The three things the client ignores, and that the emitter stopped writing.
  // The title check is by *place* rather than document-wide: what went is the
  // empty title on every band and every segment box, and a title carrying text
  // is a different element — upstream hangs the sequence of a read's mismatch on
  // one, which this fork never draws but the emitter can still write.
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
      elements.length,
      bandData.bands.length,
      "the strand group's drawable count is not the band count",
    );
  }
}
