// A band's geometry, as numbers.
//
// The layout used to build each band's `d` attribute as a finished drawing
// command before anything else happened, and `pgb` parsed that string back into
// six floats with a regular expression (`parseBands.ts`). The string was an
// encoding step in the middle of a numeric pipeline and both ends would rather
// have the numbers, so #23 removed it: the layout collects the numbers, and
// `emit-document.mjs` writes the drawing command out of them.
//
// The whole of the claim is that the document did not move. So the strongest
// test here is not that the numbers exist — it is that the numbers `pgb`
// recovers from the emitted document are, exactly and to the bit, the numbers
// the layout held. That is what `the numbers pgb recovers are the numbers the
// layout held` checks, and it is the round trip the ticket asks about.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  BAND_THICKNESS,
  cornerShape,
  curveBand,
  rectBand,
  segmentBox,
  verticalConnector,
} from "../../seqtubemap/band-data.mjs";
import { emitDocument } from "../../seqtubemap/emit-document.mjs";
import { renderTubeMap } from "../../seqtubemap/render.mjs";
import { readBands } from "./pgb-parser.mjs";
import { cases, goldenPath, inputPath, pclaiColorSchemeText, regionFor } from "./golden-cases.mjs";
import { realCases, renderReal } from "./real-cases.mjs";

// The six values a band is, in the order this repository names them. `pgb`
// stores the same band as `x0, y0, width, y1, uTop, uBottom` — the width and the
// two control abscissae normalized against it — which is a decision about a GPU
// buffer rather than about the band, and is made where that buffer is.
const GEOMETRY = ["x0", "y0", "x1", "y1", "controlTop", "controlBottom"];

// A curve and a rect the layout could plausibly have produced, for the unit
// checks below. The rect is flat by construction; the curve is not.
const A_CURVE = {
  strand: 0,
  x0: 100,
  y0: 20,
  x1: 340.5,
  y1: 65,
  controlTop: 268.35,
  controlBottom: 172.15,
  thickness: BAND_THICKNESS,
};
const A_RECT = { strand: 0, x: 100, y: 20, width: 240.5, height: BAND_THICKNESS };

test("a band is six numbers and a strand, whichever shape drew it", () => {
  // The ticket's "degenerate bands drawn as rectangles are handled as the same
  // primitive": a rect is a band whose two edges are horizontal, not a second
  // kind of thing with its own fields. `kind` survives because it says which
  // element the document writes, not what the band is.
  const curve = curveBand(A_CURVE);
  const rect = rectBand(A_RECT);

  for (const band of [curve, rect]) {
    for (const value of GEOMETRY) {
      assert.equal(typeof band[value], "number", `a band carries no ${value}`);
    }
    assert.equal(band.strand, 0);
  }

  assert.equal(curve.kind, "curve");
  assert.equal(rect.kind, "rect");

  // Flat, and its control abscissae are the midpoint — the same reading `pgb`
  // makes of a `<rect>`, said here so the two cannot disagree about it.
  assert.equal(rect.y1, rect.y0);
  assert.equal(rect.x1, A_RECT.x + A_RECT.width);
  assert.equal(rect.controlTop, rect.controlBottom);
  assert.equal(rect.controlTop, rect.x0 + (rect.x1 - rect.x0) * 0.5);
});

test("no band carries a drawing command", () => {
  // The point of the ticket, stated over the shapes rather than over one of
  // them: nothing in the captured data is text a parser has to take apart.
  const bands = [
    curveBand(A_CURVE),
    rectBand(A_RECT),
    verticalConnector({ strand: 0, x: 10, y: 20, width: 7, height: 39 }),
    cornerShape({
      strand: 0,
      x: 439,
      y: 95,
      radius: 7,
      bend: 7,
      thickness: BAND_THICKNESS,
      turn: "bottom",
      direction: "rightward",
    }),
  ];

  for (const band of bands) {
    assert.ok(!("path" in band), `a ${band.kind} band still carries a path string`);
    for (const [name, value] of Object.entries(band)) {
      if (name === "kind" || name === "turn" || name === "direction") continue;
      assert.equal(typeof value, "number", `a ${band.kind} band's ${name} is not a number`);
    }
  }
});

test("a band that is not the constant thickness fails loudly", () => {
  // Every band in every surveyed document is exactly this thick, which is what
  // lets six values describe one — and it is what `pgb` refuses a document over
  // (`THICKNESS`, parseBands.ts). A layout that produced another thickness would
  // otherwise be silently mis-encoded into a band that is not the band it drew.
  assert.throws(
    () => curveBand({ ...A_CURVE, thickness: 4 }),
    /4 units thick.*every band in a tube map is 15/s,
  );
  assert.throws(
    () => rectBand({ ...A_RECT, height: 4 }),
    /4 units thick.*every band in a tube map is 15/s,
  );
  assert.throws(
    () => cornerShape({ strand: 0, x: 1, y: 1, radius: 7, bend: 7, thickness: 4, turn: "bottom", direction: "rightward" }),
    /4 units thick.*every band in a tube map is 15/s,
  );
});

test("a band whose width would not survive being written down fails loudly", () => {
  // A rect is written as `x` and a width and read back as two abscissae, so the
  // one arithmetic the round trip depends on is that `x0 + width` gives back
  // exactly `width` when `x0` is subtracted from it again. It does for every
  // band in every fixture here — but it stops being true at magnitudes float64
  // cannot hold both ends of, and a band silently a fraction of a unit wide in
  // the wrong place is exactly what this ticket must not introduce.
  assert.throws(
    () => rectBand({ ...A_RECT, x: 1e17, width: 0.5 }),
    /cannot be written down and read back/,
  );
});

test("a vertical connector is not a band, and says so", () => {
  // The reversal shapes are the one place the six-value grammar does not reach,
  // and CONTEXT.md's **band** — "one strand crossing one x-interval" — is not
  // what either of them is. A connector is a tall rect, 19 and 39 units in the
  // synthetic inversion below, so it carries its own height and is a kind of its
  // own rather than a band of an impossible thickness. `pgb` cannot read either
  // shape today; what a corner and a connector mean on the band route is #52.
  const connector = verticalConnector({ strand: 0, x: 10, y: 20, width: 7, height: 39 });
  assert.equal(connector.kind, "connector");
  assert.equal(connector.height, 39);
  for (const value of GEOMETRY) {
    assert.ok(!(value in connector), `a vertical connector claims to have a band's ${value}`);
  }
});

// One render per case — the same renders `band-data.test.mjs` and
// `real-subgraph.band.test.mjs` drive, over both the synthetic goldens and the
// five real subgraphs, so the claim below covers 121 strands over a 40-segment
// spine *and* 1,201 strands over 768 segments.
for (const testCase of cases) {
  test(`the numbers pgb recovers from the ${testCase.name} document are the numbers the layout held`, async () => {
    const inputFile = inputPath(testCase);
    const { start, end } = regionFor(JSON.parse(readFileSync(inputFile, "utf8")));
    const { document, bandData } = await renderTubeMap({
      inputFile,
      start,
      end,
      nodeWidthOption: testCase.nodeWidthOption,
      pclaiColorScheme: JSON.parse(pclaiColorSchemeText(testCase)),
    });

    assert.equal(document, readFileSync(goldenPath(testCase), "utf8"), "the golden document moved");
    assertRecoveredExactly(document, bandData);
  });
}

for (const name of realCases) {
  test(`the numbers pgb recovers from ${name} are the numbers the layout held`, async () => {
    const { document, bandData } = await renderReal(name);
    assertRecoveredExactly(document, bandData);
  });
}

/**
 * Every band `pgb` reads out of the document is, to the bit, the band the layout
 * collected.
 *
 * Exact equality and not a tolerance: a decimal written by `String` and read
 * back by `Number` is the same float64, so anything short of identity here is a
 * coordinate that moved.
 */
function assertRecoveredExactly(document, bandData) {
  const { counted, matched } = readBands(document);
  assert.equal(matched.length, counted, "pgb could not read every drawable in g.track");
  assert.equal(matched.length, bandData.bands.length, "the document and the band data disagree on the band count");
  assert.ok(matched.length > 0, "the document draws no bands");

  let flat = 0;
  for (const [at, recovered] of matched.entries()) {
    const band = bandData.bands[at];
    for (const value of GEOMETRY) {
      assert.equal(
        recovered[value],
        band[value],
        `band ${at} (${band.kind}) came back with ${value} ${recovered[value]}, not ${band[value]}`,
      );
    }
    if (recovered.isRect) flat += 1;
  }

  // Both shapes are present, or the check above covers one of them.
  assert.ok(flat > 0, "no band was drawn flat, so the degenerate case is untested here");
  assert.ok(flat < matched.length, "every band was drawn flat, so the curve is untested here");

  // And the document is still exactly what the numbers say it is, through JSON —
  // which is the wire #24 puts them on.
  //
  // On its own this line proves little: the document *is* emitted from the band
  // data, so comparing a re-emission against it is the degenerating oracle ADR
  // `0002` warns about. What it adds is the round trip through JSON, and what
  // carries the real weight is above it — the golden bytes for the synthetic
  // cases, and `real-subgraph.band.test.mjs` for the five real ones, which
  // rebuilds each document from the baseline on disk rather than from the render
  // it just performed.
  assert.equal(emitDocument(JSON.parse(JSON.stringify(bandData))), document);
}

// A segment box lost its drawing command in #66, for the same reason a band lost
// its own in #23: every one of them is a rounded rectangle and the layout has
// the five numbers before it builds the string. What is checked here is the same
// claim as above, one shape down — that the numbers and the picture agree — read
// back out of the document by a parser that knows nothing about how it was
// written.
for (const name of realCases) {
  test(`every segment box of ${name} is the rectangle its numbers say`, async () => {
    const { document, bandData } = await renderReal(name);
    const drawn = readSegmentBoxes(document);

    assert.equal(drawn.length, bandData.segments.length, "the document and the band data disagree on the box count");
    assert.ok(drawn.length > 0, "the document draws no segment boxes");

    let twoArc = 0;
    for (const [at, box] of drawn.entries()) {
      const { box: numbers } = bandData.segments[at];
      assert.deepEqual(box.corners, numbers, `segment box ${at} is not the rectangle it travels as`);
      if (box.spelling === "two-arc") twoArc += 1;
    }

    // The spelling that has no straight run along its top or bottom edge — a box
    // exactly two corners wide — is most of them, and is the one a client parsing
    // the string had to carry a second grammar for. Both spellings have to appear
    // here, or this covers one of them.
    assert.ok(twoArc > 0, "no box was drawn in the two-arc spelling");
    assert.ok(twoArc < drawn.length, "every box was drawn in the two-arc spelling");
  });
}

/**
 * The segment boxes a document draws, recovered from the path commands.
 *
 * Deliberately naive: it takes the coordinate pairs of the path and reads the
 * rectangle off their extremes, knowing nothing about the order the arcs and
 * straight runs are written in. That is what makes it an independent check of
 * the five numbers rather than the emitter's own arithmetic played back.
 */
function readSegmentBoxes(document) {
  const group = document.slice(document.indexOf('<g class="node">'));
  return [...group.matchAll(/<path id="[^"]*" d="([^"]*)"/g)].map(([, d]) => {
    const numbers = d.match(/-?\d+(?:\.\d+)?/g).map(Number);
    const xs = numbers.filter((_, at) => at % 2 === 0);
    const ys = numbers.filter((_, at) => at % 2 === 1);
    const [left, right] = [Math.min(...xs), Math.max(...xs)];
    const [top, bottom] = [Math.min(...ys), Math.max(...ys)];
    return {
      // The path opens on the left edge, a radius below the top corner, so the
      // radius is readable without knowing which arc command drew it.
      corners: { left, top, right, bottom, radius: ys[0] - top },
      // Which spelling drew it: a straight run between the first two corners
      // means the box is wider than the two of them, and there is a top edge
      // to draw. Without one the two arcs meet and the command has no `L`
      // there at all.
      spelling: / L /.test(d.split(" Q ")[1]) ? "three-arc" : "two-arc",
    };
  });
}

test("a box the layout draws that is not a rounded rectangle throws where the layout is still in scope", () => {
  // The five numbers say a rounded rectangle or they say nothing: a box
  // narrower than the two corners it is drawn with is not a shape this can
  // encode, and a client handed those numbers would draw a rectangle the server
  // never drew. Caught here, where the layout that produced it is in scope, for
  // the same reason a band of the wrong thickness is.
  const box = { left: 11, top: 11, right: 76, bottom: 5564, radius: 9 };
  assert.deepEqual(segmentBox(box), box);

  // Exactly two corners wide is a box — it is the spelling most real boxes are
  // drawn in — and narrower than that is not.
  assert.deepEqual(segmentBox({ ...box, right: 29 }).right, 29);
  assert.throws(() => segmentBox({ ...box, right: 28 }), /not a rounded rectangle/);
  assert.throws(() => segmentBox({ ...box, bottom: 28 }), /not a rounded rectangle/);
  assert.throws(() => segmentBox({ ...box, left: 100 }), /not a rounded rectangle/);

  // And a number that is not one, which is how a box built from an undefined
  // layout quantity would otherwise reach the wire as `null`.
  assert.throws(() => segmentBox({ ...box, top: undefined }), /top/);
  assert.throws(() => segmentBox({ ...box, radius: 0 }), /radius/);
});
