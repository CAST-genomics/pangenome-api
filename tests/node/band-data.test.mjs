// The layout's band data, captured alongside the document it currently produces.
//
// The document that /seqtubemap returns is 93.7% emulated browser, and that
// document exists only so the numbers the layout already held can be serialized
// to text and parsed straight back into numbers by the client. Before it can be
// removed, the numbers going into it have to be reachable — which is what
// `getBandData()` makes them.
//
// Nothing observable changes yet, so the claim this file has to carry is not
// "the data looks right" but "the data is enough": enough to rebuild the
// document that is shipping today. It demonstrates that rather than asserting
// it, by reconstructing the document from the captured data alone
// (reconstruct-document.mjs, which is given the data and nothing else) and
// comparing the result against the render byte for byte.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { renderTubeMap } from "../../seqtubemap/render.mjs";
import {
  cases,
  goldenPath,
  inputPath,
  pclaiColorSchemeText,
  regionFor,
  repoRoot,
} from "./golden-cases.mjs";
import { reconstructDocument } from "./reconstruct-document.mjs";

// The smallest of the committed real subgraphs, named for the region it was
// fetched for — which is where the render gets its coordinates, as the endpoint
// does.
const REAL_SUBGRAPH = "subgraph_chr8_78771162_78771252_v2_with_walk";

// One render per case, in this process — the same render the CLI performs, and
// the only way to reach the band data, which is held in memory rather than
// written anywhere. A case's PCLAI colour scheme goes in too, or the render would
// not be the one its golden document was baselined from.
const rendered = new Map();
for (const testCase of cases) {
  const inputFile = inputPath(testCase);
  const { start, end } = regionFor(JSON.parse(readFileSync(inputFile, "utf8")));
  rendered.set(
    testCase.name,
    await renderTubeMap({
      inputFile,
      start,
      end,
      nodeWidthOption: testCase.nodeWidthOption,
      pclaiColorScheme: JSON.parse(pclaiColorSchemeText(testCase)),
    }),
  );
}

for (const testCase of cases) {
  const { document, bandData } = rendered.get(testCase.name);

  test(`the ${testCase.name} render still produces its golden document`, () => {
    // The capture is meant to change nothing about the output, and this render
    // goes through the same code the golden test drives through the CLI. If the
    // two ever disagree, the reconstruction below is being checked against the
    // wrong oracle, and it should say so here rather than there.
    assert.equal(document, readFileSync(goldenPath(testCase), "utf8"));
  });

  test(`the ${testCase.name} document can be rebuilt from its band data alone`, () => {
    // This is the acceptance criterion the ticket asks to be demonstrated
    // rather than asserted: everything below comes out of the band data, and if
    // anything needed to draw the picture were missing from it, these bytes
    // could not be produced.
    const rebuilt = reconstructDocument(bandData);
    assert.ok(
      document.startsWith(rebuilt),
      describeDifference(document, rebuilt),
    );

    // What the reconstruction stops short of is the ruler, which is not band
    // data: the axis line, its ticks and their labels. Everything the band data
    // covers has to be inside the prefix, so the tail must carry no band, no
    // segment box and no group of either.
    const tail = document.slice(rebuilt.length);
    assert.equal(tail.slice(-6), "</svg>");
    for (const marker of ["<g ", "trackID=", "sequence="]) {
      assert.ok(!tail.includes(marker), `${marker} appears after the reconstructed prefix`);
    }
  });

  test(`the ${testCase.name} band data survives a round trip through JSON`, () => {
    // The point of capturing the data is to be able to hand it to somebody
    // else. Plain numbers and strings — no DOM nodes, no live references into
    // the layout, nothing that only means something inside this process.
    const rebuilt = reconstructDocument(JSON.parse(JSON.stringify(bandData)));
    assert.equal(rebuilt, reconstructDocument(bandData));
  });

  test(`the ${testCase.name} band data has one strand row per strand`, () => {
    // The table is the per-band constants sent once. A row per strand is what
    // makes that true; a row per band would be the repetition it exists to
    // remove.
    const { strands, bands } = bandData;
    const ids = new Set(strands.map((strand) => strand.id));
    assert.equal(ids.size, strands.length, "a strand appears in more than one row");

    const namesInDocument = new Set(
      [...document.matchAll(/trackName="([^"]+)"/g)].map((match) => match[1]),
    );
    assert.equal(strands.length, namesInDocument.size);
    assert.ok(bands.length > strands.length * 2, "too few bands to be worth a table");

    for (const band of bands) {
      assert.ok(strands[band.strand], `band ${bands.indexOf(band)} names no strand`);
    }
  });

  test(`the ${testCase.name} band data is in paint order`, () => {
    // Ordering is not incidental: bands are drawn in the order they appear, so
    // a later band draws over an earlier one. The reconstruction above is the
    // real check — it would not be byte-identical if the order were wrong — and
    // this states the count the document and the data have to agree on.
    const trackGroup = document.slice(
      document.indexOf('<g class="track">'),
      document.indexOf('<g class="node">'),
    );
    const shapes = trackGroup.match(/<(?:rect|path)\b/g) ?? [];
    assert.equal(bandData.bands.length, shapes.length);

    // The segment boxes are the only thing in `g.node` at this width — labels
    // and mismatches are drawn in "normal" mode only — so the count is exact.
    // The slice stops at the group's own close: the ruler's arrow is a <path>
    // too, and it is drawn after the group rather than inside it.
    const nodeGroupStart = document.indexOf('<g class="node">');
    const nodeGroup = document.slice(nodeGroupStart, document.indexOf("</g>", nodeGroupStart));
    const boxes = nodeGroup.match(/<path\b/g) ?? [];
    assert.ok(bandData.segments.length > 0, "no segment boxes captured");
    assert.equal(bandData.segments.length, boxes.length);
  });
}

test("the document's dimensions come from the band data", () => {
  const { document, bandData } = rendered.get("large");
  const { width, height, viewBox, extent } = bandData.document;

  assert.match(document, new RegExp(` viewBox="${escapeForRegExp(viewBox)}" `));
  assert.match(document, new RegExp(` width="${escapeForRegExp(String(width))}" `));
  assert.match(document, new RegExp(` height="${escapeForRegExp(String(height))}"`));
  // The extent the margins were added to, kept so a consumer can tell where the
  // layout actually ends rather than inferring it back out of the viewBox.
  assert.ok(extent.maxXCoordinate > 0);
  assert.ok(extent.maxYCoordinate > extent.minYCoordinate);
});

test("a strand's colour and placement are on the strand, not on every band", () => {
  const { bandData } = rendered.get("large");
  for (const strand of bandData.strands) {
    assert.equal(typeof strand.id, "number");
    assert.equal(typeof strand.name, "string");
    assert.match(strand.color, /^(#[0-9a-f]{6}|rgb\(\d+, \d+, \d+\))$/i);
    // No PCLAI scheme is loaded for these fixtures, so every placement is
    // absent — as null, which is what the document writes as "None".
    assert.equal(strand.pclaiX, null);
    assert.equal(strand.pclaiY, null);
    assert.equal(strand.pclaiScore, null);
  }
  for (const band of bandData.bands) {
    assert.ok(!("color" in band), "a band carries a colour of its own");
    assert.ok(!("name" in band), "a band carries a strand name of its own");
  }
});

test("a real subgraph's document is rebuilt from its band data, in full", async () => {
  // The synthetic fixtures above are shaped like a subgraph; this one is a
  // subgraph — 464 strands, fetched from the live server (see
  // tests/fixtures/seqtubemap/README.md). It carries no ruler, which is what
  // production documents look like, so here the reconstruction accounts for
  // every byte of the document rather than for its leading ones.
  const { document, bandData } = await renderTubeMap({
    inputFile: join(repoRoot, "tests", "fixtures", "seqtubemap", `${REAL_SUBGRAPH}.json`),
    start: 78771162,
    end: 78771252,
    nodeWidthOption: "compressed",
  });

  const rebuilt = reconstructDocument(bandData);
  assert.ok(document.startsWith(rebuilt), describeDifference(document, rebuilt));
  assert.equal(document.slice(rebuilt.length), "</svg>");
  assert.ok(bandData.strands.length > 400, `only ${bandData.strands.length} strands`);
});

test("an inversion's corners and vertical rectangles are captured too", async () => {
  // No committed fixture contains an inversion, and an inversion is the only
  // thing that produces corner bands — or a rectangle the document paints no
  // opacity on. So one is made here, by sending a single strand backwards
  // through three segments of the smoke fixture, which is exactly what a
  // reversal is.
  const inputFile = join(mkdtempSync(join(tmpdir(), "tubemap-inverted-")), "inverted.json");
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

  const { document, bandData } = await renderTubeMap({
    inputFile,
    start: 0,
    end: 69,
    nodeWidthOption: "compressed",
  });

  const corners = bandData.bands.filter((band) => band.kind === "corner");
  assert.ok(corners.length > 0, "the inverted input produced no corner bands");
  assert.ok(
    bandData.bands.some((band) => band.kind === "rect" && band.alpha === undefined),
    "the inverted input produced no rectangle without an opacity",
  );

  // The layout builds a corner without a strand name — which is why the
  // document carries none on it. The band data must still say which strand the
  // corner belongs to: it points at the strand's own row, named like any other,
  // rather than at a second nameless row for the same strand.
  const ids = bandData.strands.map((strand) => strand.id);
  assert.equal(new Set(ids).size, ids.length, "a strand appears in more than one row");
  for (const corner of corners) {
    const strand = bandData.strands[corner.strand];
    assert.equal(typeof strand.name, "string", "a corner points at a nameless strand");
    assert.ok(document.includes(`trackName="${strand.name}"`));
  }

  assert.ok(
    document.startsWith(reconstructDocument(bandData)),
    describeDifference(document, reconstructDocument(bandData)),
  );
});

test("a strand's PCLAI placement reaches the strand table", async () => {
  // The fixtures above are rendered without a PCLAI colour scheme, which is the
  // one case where every placement is absent — so on its own it would leave the
  // placement columns of the table asserted only against null. This renders with
  // a scheme in the shape main.py builds: rgb, an x/y coordinate pair, and a
  // score, keyed by "sample#haplotype#contig". A strand the scheme does not
  // cover keeps its light grey and has no placement.
  const covered = "HG10000#1#chr1";
  const inputFile = inputPath(cases[0]);
  const { start, end } = regionFor(JSON.parse(readFileSync(inputFile, "utf8")));
  const { document, bandData } = await renderTubeMap({
    inputFile,
    start,
    end,
    nodeWidthOption: cases[0].nodeWidthOption,
    pclaiColorScheme: { [covered]: [[12, 34, 56], [1.5, -2.5], 0.875] },
  });

  const placed = bandData.strands.find((strand) => strand.name === covered);
  assert.deepEqual(placed, {
    id: placed.id,
    name: covered,
    color: "rgb(12, 34, 56)",
    pclaiX: 1.5,
    pclaiY: -2.5,
    pclaiScore: 0.875,
  });

  for (const strand of bandData.strands) {
    if (strand.name === covered) continue;
    assert.equal(strand.color, "rgb(211, 211, 211)", `${strand.name} kept a palette colour`);
    assert.equal(strand.pclaiX, null);
    assert.equal(strand.pclaiScore, null);
  }

  // And the document is still exactly what the table says it is — including the
  // "None" it writes where a placement is absent.
  const rebuilt = reconstructDocument(bandData);
  assert.ok(document.startsWith(rebuilt), describeDifference(document, rebuilt));
  assert.ok(document.includes(`pclaiX="1.5" pclaiY="-2.5" pclaiScore="0.875"`));
});

function escapeForRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function describeDifference(document, rebuilt) {
  let at = 0;
  while (at < document.length && at < rebuilt.length && document[at] === rebuilt[at]) at += 1;
  const context = 120;
  return (
    `the reconstruction diverges from the document at byte ${at} ` +
    `(${rebuilt.length} bytes rebuilt, ${document.length} in the document)\n` +
    `  document:      ...${document.slice(at, at + context)}\n` +
    `  reconstructed: ...${rebuilt.slice(at, at + context)}\n` +
    "The band data is missing something the document says, or says it differently."
  );
}
