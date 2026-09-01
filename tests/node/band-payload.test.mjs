// The wire format `/seqtubemap?format=bands` returns.
//
// Two claims are worth testing and one of them is the whole increment:
//
// * the payload is a *complete* description of the picture — the document the
//   endpoint serves today can be written back out of it, band for band, box for
//   box, with nothing but single-precision rounding between the two; and
// * the numbers a client reads out of the bytes are the numbers the layout
//   held, rounded to Float32 and not otherwise touched.
//
// The second is checked against the emitted document through `pgb`'s own
// parser, so the two encodings are compared the way the client compares them
// rather than the way this repository would prefer to.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  FORMAT,
  GEOMETRY_FIELDS,
  KIND_CURVE,
  KIND_RECT,
  MAX_STRAND_ROWS,
  VERSION,
  bandDataFromPayload,
  decodeBandPayload,
  encodeBandPayload,
} from "../../seqtubemap/band-payload.mjs";
import { BAND_THICKNESS, curveBand, rectBand, rgbChannels } from "../../seqtubemap/band-data.mjs";
import { emitDocument } from "../../seqtubemap/emit-document.mjs";
import { renderTubeMap } from "../../seqtubemap/render.mjs";
import { cases, inputPath, pclaiColorSchemeText, regionFor, repoRoot } from "./golden-cases.mjs";
import { realCases, renderReal } from "./real-cases.mjs";
import { readBands } from "./pgb-parser.mjs";

/** Render one golden case in-process, the way the golden test renders it. */
async function renderGolden(testCase) {
  const file = inputPath(testCase);
  const { start, end } = regionFor(JSON.parse(readFileSync(file, "utf8")));
  const scheme = pclaiColorSchemeText(testCase);
  return renderTubeMap({
    inputFile: file,
    start,
    end,
    nodeWidthOption: testCase.nodeWidthOption,
    pclaiColorScheme: scheme === null ? null : JSON.parse(scheme),
  });
}

/** A render of a single strand sent backwards through three segments. */
async function renderReversal() {
  const inputFile = join(mkdtempSync(join(tmpdir(), "tubemap-payload-")), "inverted.json");
  const vg = JSON.parse(readFileSync(join(repoRoot, "tests", "fixtures", "tiny-vg.json"), "utf8"));
  const mapping = vg.path[1].mapping;
  vg.path[1].mapping = [
    ...mapping.slice(0, 2),
    ...mapping
      .slice(2, 5)
      .reverse()
      .map((step) => ({ position: { ...step.position, is_reverse: true } })),
    ...mapping.slice(5),
  ];
  writeFileSync(inputFile, JSON.stringify(vg), "utf8");
  return renderTubeMap({ inputFile, start: 0, end: 69, nodeWidthOption: "compressed" });
}

/**
 * The same band data, put through what the wire does to it — and only that.
 *
 * Two things: every band's geometry goes through Float32, and every strand's
 * colour comes back in the one spelling the document writes, whichever of the
 * two the layout used. A document written from this is what the payload can
 * reproduce exactly.
 */
function throughTheWire(bandData) {
  return {
    ...bandData,
    strands: bandData.strands.map((strand) => ({
      ...strand,
      color: `rgb(${rgbChannels(strand.color).join(", ")})`,
    })),
    bands: bandData.bands.map((band) => {
      if (band.kind !== "rect" && band.kind !== "curve") return band;
      const rounded = { ...band };
      for (const field of GEOMETRY_FIELDS) rounded[field] = Math.fround(band[field]);
      return rounded;
    }),
  };
}

test("the payload opens with its own length, and names the format and version", async () => {
  const { bandData } = await renderGolden(cases[0]);
  const payload = encodeBandPayload(bandData);

  const headerLength = new DataView(payload.buffer, payload.byteOffset, 4).getUint32(0, true);
  const header = JSON.parse(
    Buffer.from(payload.buffer, payload.byteOffset + 4, headerLength).toString("utf8"),
  );

  assert.equal(header.format, FORMAT);
  assert.equal(header.version, VERSION);
  // A reader that knows only "uint32, then that many bytes of JSON" gets the
  // whole map of the rest without knowing anything else about the format.
  assert.ok(header.band.geometry.byteLength > 0);
  assert.equal(payload.byteLength, ((4 + headerLength + 3) & ~3) + header.bodyLength);
});

test("the body is six floats, a strand id and a kind per band", async () => {
  const { bandData } = await renderGolden(cases[0]);
  const { header, geometry, strandIds, kinds } = decodeBandPayload(encodeBandPayload(bandData));

  assert.equal(header.band.count, bandData.bands.length);
  assert.equal(geometry.length, header.band.count * 6);
  assert.equal(strandIds.length, header.band.count);
  assert.equal(kinds.length, header.band.count);

  bandData.bands.forEach((band, index) => {
    GEOMETRY_FIELDS.forEach((field, offset) => {
      assert.equal(geometry[index * 6 + offset], Math.fround(band[field]), `${field} of band ${index}`);
    });
    assert.equal(strandIds[index], band.strand);
    assert.equal(kinds[index], band.kind === "rect" ? KIND_RECT : KIND_CURVE);
  });
});

test("a per-strand value appears exactly once", async () => {
  const { bandData, document } = await renderGolden(cases[1]);
  const payload = encodeBandPayload(bandData);
  const { header } = decodeBandPayload(payload);

  // The claim is about the payload, so it is checked over the payload's bytes:
  // a strand's name occurs once in the whole of it, where the document repeats
  // it on every band the strand draws.
  const text = Buffer.from(payload).toString("latin1");
  for (const strand of header.strands) {
    const inPayload = text.split(strand.name).length - 1;
    const inDocument = document.split(strand.name).length - 1;
    assert.equal(inPayload, 1, `${strand.name} appears ${inPayload} times in the payload`);
    assert.ok(inDocument > 1, `${strand.name} appears once in the document too — pick a busier case`);
  }

  // And the thickness and the opacity, which the document says per band and
  // this says per document.
  assert.equal(header.band.thickness, BAND_THICKNESS);
  assert.equal(header.band.alpha, 1);
});

test("every band's strand id resolves into the strand table, with no gaps", async () => {
  for (const name of realCases.slice(0, 2)) {
    const { bandData } = await renderReal(name);
    const { header, strandIds } = decodeBandPayload(encodeBandPayload(bandData));

    const used = new Set(strandIds);
    for (const row of used) {
      assert.ok(header.strands[row] !== undefined, `band names row ${row}, which is not in the table`);
    }
    // No dangling ids in the other direction either: the table's own ids are
    // the dense 0..n-1 `pgb` indexes by.
    const ids = header.strands.map((strand) => strand.id).sort((a, b) => a - b);
    assert.deepEqual(ids, ids.map((_, index) => index));
  }
});

test("the document the endpoint serves can be written back out of the payload", async () => {
  // The strongest thing this format can claim: nothing about the picture is
  // left behind. The only difference permitted between the two is Float32.
  const goldens = await Promise.all(cases.map(renderGolden));
  const renders = [...goldens, await renderReversal()];

  for (const { bandData, document } of renders) {
    const rebuilt = bandDataFromPayload(encodeBandPayload(bandData));
    assert.deepEqual(rebuilt, throughTheWire(bandData));
    assert.equal(emitDocument(rebuilt), emitDocument(throughTheWire(bandData)));

    // Float32 is a real difference and this is what it is: the layout's
    // coordinates are doubles — `138.71428571428573` — and a client receives
    // `138.7142791748047`. So the rebuilt document is the served document to
    // single precision, which is the bar, rather than byte for byte, which
    // 32-bit floats cannot meet and `pgb`'s Float32 instance buffer does not
    // want. `the numbers a client reads are the numbers pgb recovers` is where
    // that equality is checked at the precision it actually holds at.
    assertSameDocument(emitDocument(rebuilt), document, bandData.document.width);
  }
});

/**
 * Two documents that differ only in the precision their numbers carry.
 *
 * Everything that is not a number has to match character for character; every
 * number has to agree to within a Float32's resolution, which is what the wire
 * costs. Compared as numbers rather than as rounded text because rounding
 * decides the wrong way at its own boundary: the layout's `79.648053` and the
 * Float32 `79.648048` are the same band, and no number of significant figures
 * makes them the same string.
 */
const NUMBER = /-?\d+(?:\.\d+)?/g;

function assertSameDocument(actual, expected, extent) {
  assert.equal(actual.replace(NUMBER, "#"), expected.replace(NUMBER, "#"));

  const tolerance = Math.max(1, extent) * 1e-6;
  const theirs = expected.match(NUMBER).map(Number);
  actual.match(NUMBER).forEach((text, index) => {
    const mine = Number(text);
    assert.ok(
      Math.abs(mine - theirs[index]) <= tolerance,
      `number ${index}: ${mine} is not ${theirs[index]} to Float32`,
    );
  });
}

test("the numbers a client reads are the numbers pgb recovers from the document", async () => {
  // The exact claim, and the one the ticket asks about: band geometry and the
  // document rendered from the same layout agree. Read back through `pgb`'s own
  // parser rather than this repository's idea of one, because the two encodings
  // have to agree where the client compares them — and over all five real
  // subgraphs, 101,742 bands, rather than the smallest one, because "exactly"
  // is a claim about every band there is.
  //
  // Exact equality, not a tolerance: `Math.fround` is the whole of what the
  // wire does to a number, so the payload's value is the document's value
  // rounded once, and nothing else may have happened to it.
  for (const name of realCases) {
    const { bandData, document } = await renderReal(name);
    const { geometry, strandIds, header } = decodeBandPayload(encodeBandPayload(bandData));
    const { matched, counted } = readBands(document);

    assert.equal(matched.length, counted, `pgb could not read the whole of ${name}`);
    assert.equal(matched.length, header.band.count);

    matched.forEach((band, index) => {
      GEOMETRY_FIELDS.forEach((field, offset) => {
        assert.equal(
          geometry[index * 6 + offset],
          Math.fround(band[field]),
          `${field} of band ${index} of ${name}`,
        );
      });
      assert.equal(header.strands[strandIds[index]].id, band.id);
      assert.equal(header.strands[strandIds[index]].name, band.name);
    });
  }
});

test("segment boxes travel whole, with their sequences", async () => {
  const { bandData } = await renderReal(realCases[0]);
  const { header } = decodeBandPayload(encodeBandPayload(bandData));

  assert.deepEqual(header.segments, bandData.segments);
  assert.ok(header.segments.length > 0);
  for (const segment of header.segments) {
    assert.equal(typeof segment.id, "string");
    assert.ok(segment.outline.startsWith("M "), segment.outline);
    assert.match(segment.sequence, /^[ACGTN]+$/);
  }
});

test("a reversal's corners and connectors keep their place in the draw order", async () => {
  const { bandData } = await renderReversal();
  const { header } = decodeBandPayload(encodeBandPayload(bandData));
  const { corners, connectors } = header.reversals;

  assert.ok(corners.length > 0 && connectors.length > 0, "this render drew no reversal");
  // They are not in the body — the body is bands, and neither of these is one.
  assert.equal(header.band.count, bandData.bands.length - corners.length - connectors.length);

  // Where each one sits in the picture is what the `order` carries, and it is
  // the position it held among all the shapes the layout drew.
  for (const shape of [...corners, ...connectors]) {
    const original = bandData.bands[shape.order];
    assert.equal(original.kind, shape.kind);
    assert.equal(original.strand, shape.strand);
  }
});

test("a strand table too large to address is refused, not wrapped", () => {
  const strands = Array.from({ length: MAX_STRAND_ROWS + 1 }, (_, id) => ({
    id,
    name: `strand-${id}`,
    color: "rgb(1, 2, 3)",
  }));

  assert.throws(
    () => encodeBandPayload({ document: {}, strands, bands: [], segments: [], overlays: [] }),
    /16 bits/,
  );
});

test("a band the format cannot carry throws where the layout is still in scope", () => {
  const strands = [{ id: 0, name: "one", color: "rgb(1, 2, 3)" }];
  const base = { document: {}, strands, segments: [], overlays: [] };
  const band = rectBand({ strand: 0, x: 0, y: 0, width: 10, height: BAND_THICKNESS, alpha: 1 });

  // A band pointing outside the table it is sent with: the failure the strand
  // id being an index rather than a name makes possible, caught here.
  assert.throws(
    () => encodeBandPayload({ ...base, bands: [{ ...band, strand: 7 }] }),
    /not a row of the 1-row strand table/,
  );

  // An opacity the header cannot say once for everyone.
  assert.throws(
    () => encodeBandPayload({ ...base, bands: [{ ...band, alpha: 0.4 }] }),
    /opacity 0.4/,
  );

  // A corner names a strand too, even though the document writes no name on
  // one, so a dangling index has to be caught there as well as on a band.
  assert.throws(
    () => encodeBandPayload({ ...base, bands: [{ kind: "corner", strand: 3, x: 0, y: 0, radius: 5, bend: 2, turn: "top", direction: "rightward" }] }),
    /not a row of the 1-row strand table/,
  );

  // A kind nothing knows how to encode, which would otherwise be written as a
  // curve with undefined coordinates — a plausible shape in the wrong place.
  assert.throws(
    () => encodeBandPayload({ ...base, bands: [{ ...band, kind: "spiral" }] }),
    /"spiral" is not one this format can carry/,
  );

  // And the shape of a well-formed one, for contrast.
  const curve = curveBand({
    strand: 0,
    x0: 0,
    y0: 0,
    x1: 10,
    y1: 5,
    controlTop: 5,
    controlBottom: 5,
    thickness: BAND_THICKNESS,
    alpha: 1,
  });
  assert.equal(decodeBandPayload(encodeBandPayload({ ...base, bands: [curve] })).kinds[0], KIND_CURVE);
});

test("a payload that is not one says so", () => {
  const notAPayload = Buffer.alloc(64);
  assert.throws(() => decodeBandPayload(notAPayload), /not a band payload|Unexpected/);
  assert.throws(() => decodeBandPayload(Buffer.alloc(2)), /at least 4 bytes/);
});
