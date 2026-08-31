// The contract #22 ships under: the browser emulation went, and `pgb` did not
// change.
//
// The document is now written from band data by `seqtubemap/emit-document.mjs`,
// with no emulated browser document anywhere in the process. That is only safe
// to ship alone because the bytes the client reads are unchanged in every way
// the client looks at them — so what the client looks at is written down, in
// `pgb-parser.mjs`, and checked here against the committed goldens.
//
// The drawable counts below are the load-bearing numbers. They were measured on
// the goldens **as they stood before this increment**, when the document was
// still a serialized jsdom tree, and they are pinned here rather than derived
// from the render so that a change to the count cannot re-baseline itself away.
// `pgb` sizes its buffers from that count; if it moves, the picture moved.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { cases, goldenPath, repoRoot } from "./golden-cases.mjs";
import { assertParseableByPgb, drawables, readBands, strandGroup } from "./pgb-parser.mjs";

// Measured on the jsdom-era goldens, at commit 399db1e. `small-normal` had no
// golden then — the mode was not deterministic enough to have one — so its count
// was taken by running that commit's generator over `small`'s input at
// `nodeWidthOption: "normal"`, which is what the case does.
const DRAWABLES_BEFORE = {
  small: 65,
  large: 2549,
  "small-normal": 65,
  "small-pclai": 65,
};

for (const testCase of cases) {
  test(`the ${testCase.name} golden is a document pgb can parse`, () => {
    assertParseableByPgb(readFileSync(goldenPath(testCase), "utf8"));
  });

  test(`the ${testCase.name} golden draws the same shapes it did before jsdom went`, () => {
    assert.equal(
      drawables(readFileSync(goldenPath(testCase), "utf8")).length,
      DRAWABLES_BEFORE[testCase.name],
    );
  });
}

test("the fill style, the strand id and the strand name stay contiguous", () => {
  // Stated once more on its own, because it is the single thing most likely to
  // be broken by a well-meaning edit to the emitter: an attribute inserted
  // between the style and the trackID reads to `pgb` as a document with no
  // bands in it at all, and the emitter would still look right.
  const golden = readFileSync(goldenPath(cases[0]), "utf8");
  const band = drawables(golden).find((element) => element.includes("trackName="));
  assert.ok(band, "no named band in the golden");
  assert.match(
    band,
    /style="fill: rgb\(\d+, \d+, \d+\); fill-opacity: [^;"]+;" trackID="\d+" trackName="[^"]*"/,
  );
});

test("the browser emulation is gone from the dependency manifest", () => {
  const manifest = JSON.parse(readFileSync(join(repoRoot, "package.json"), "utf8"));
  const dependencies = Object.keys(manifest.dependencies ?? {});
  for (const emulation of ["jsdom", "canvas"]) {
    assert.ok(!dependencies.includes(emulation), `${emulation} is still a dependency`);
  }
});

test("no emulated document is constructed, so it retains nothing", async () => {
  // The memory assertion the ticket asks for. 93.7% of a render's retained
  // memory used to be the jsdom document; the honest way to show that share is
  // now zero is to show that nothing ever builds one. A render runs to
  // completion and produces a document `pgb` can read, and no window and no
  // document global exist on the far side of it — the render did not stand one
  // up, and did not tear one down either, because there was never one to tear.
  //
  // `perf/rss-split.mjs` is the same claim in megabytes, over a region large
  // enough for the number to mean something.
  const { renderTubeMap } = await import("../../seqtubemap/render.mjs");
  const { document, bandData } = await renderTubeMap({
    inputFile: join(repoRoot, "tests", "fixtures", "tiny-vg.json"),
    start: 0,
    end: 69,
    nodeWidthOption: "compressed",
  });
  assert.ok(bandData.bands.length > 0, "the render drew nothing");
  assertParseableByPgb(document, bandData);

  assert.equal(globalThis.document, undefined, "something left a document global behind");
  assert.equal(globalThis.window, undefined, "something left a window global behind");
});

test("nothing in the render path can reach the browser emulation", () => {
  // The globals above say no emulated document was built on this input. This
  // says none can be built on any input: no file the endpoint runs imports
  // either package, so there is no path — lazy, conditional or otherwise — that
  // reaches one.
  const renderPath = readdirSync(join(repoRoot, "seqtubemap"))
    .filter((name) => /\.(mjs|js)$/.test(name))
    .map((name) => join(repoRoot, "seqtubemap", name));
  assert.ok(renderPath.length >= 5, "the render path went missing");

  for (const file of renderPath) {
    const source = readFileSync(file, "utf8").replace(/^\s*\/[/*].*$/gm, "");
    for (const emulation of ["jsdom", "canvas"]) {
      assert.ok(
        !new RegExp(`(import|require)\\b[^\\n]*["']${emulation}["']`).test(source),
        `${file} imports ${emulation}`,
      );
    }
  }
});

test("a document that lost the run pgb matches on is caught", () => {
  // The conformance check has to be able to fail. This is the exact regression
  // the increment was most at risk of: the attributes still all present, still
  // all correct, and no longer contiguous. `pgb` matches the fill run with one
  // regular expression, so an attribute inserted into the middle of it does not
  // break one band — it breaks every band, and `pgb` refuses the document whole.
  const golden = readFileSync(goldenPath(cases[0]), "utf8");
  const reordered = golden.replace(/ trackID="(\d+)"/g, ' class="track$1" trackID="$1"');
  assert.throws(() => assertParseableByPgb(reordered), /are not bands pgb recognises/);
});

test("a reversal draws shapes pgb cannot read, and this is where that is written down", async () => {
  // A standing incompatibility between what the layout can draw and what the
  // client can read, filed as
  // [#52](https://github.com/CAST-genomics/PangenomeAPI/issues/52). It predates #22
  // — nothing in that change touched it — and it is pinned here rather than left as
  // a comment, because a latent refusal of the *whole document* is worth having a
  // failing example of.
  //
  // Three things about a reversal are off `pgb`'s grammar at once: its corners
  // carry no `trackName`, its corners are built from quadratics where the grammar
  // wants cubics, and neither its corners nor its vertical rectangles carry the
  // `fill-opacity: 1;` the grammar requires. Any one of them makes the matched
  // count disagree with the counted drawables, which `pgb` refuses outright.
  //
  // No committed fixture contains a reversal, so one is made here the way
  // band-data.test.mjs makes it: by sending a single strand backwards through
  // three segments of the smoke fixture.
  const { renderTubeMap } = await import("../../seqtubemap/render.mjs");
  const inputFile = join(mkdtempSync(join(tmpdir(), "tubemap-reversal-")), "inverted.json");
  const vg = JSON.parse(readFileSync(join(repoRoot, "tests", "fixtures", "tiny-vg.json"), "utf8"));
  const mapping = vg.path[1].mapping;
  vg.path[1].mapping = [
    ...mapping.slice(0, 2),
    ...mapping.slice(2, 5).reverse().map((step) => ({ position: { ...step.position, is_reverse: true } })),
    ...mapping.slice(5),
  ];
  writeFileSync(inputFile, JSON.stringify(vg), "utf8");

  const { document, bandData } = await renderTubeMap({
    inputFile,
    start: 0,
    end: 69,
    nodeWidthOption: "compressed",
  });

  // The layout really did draw the shapes in question.
  assert.ok(
    bandData.bands.some((band) => band.kind === "corner"),
    "the inverted input drew no corners, so this test is no longer about anything",
  );

  // And `pgb`'s grammar cannot account for every drawable in the group.
  const { counted, matched } = readBands(document);
  assert.ok(
    matched.length < counted,
    `expected pgb's grammar to miss some of the ${counted} drawables, but it matched all of them`,
  );
  assert.throws(() => assertParseableByPgb(document), /are not bands pgb recognises/);
});

test("a PCLAI scheme with fractional channels still emits colours pgb can read", async () => {
  // The live failure this test was written from: `pgb` refused a chr7 document
  // whole, over 6 of its 1,626 drawables, because their strand's colour was
  // `rgb(0, 228.5, 178.5)`. `pgb`'s grammar matches whole-number channels only,
  // and a PCLAI scheme supplies floats — the walks file carries them that way and
  // `bandage_graph.py` parses them with `float()`.
  //
  // The emulated document rounded them in jsdom's CSS serializer on the way out,
  // so this never surfaced before #22; the emitter has to round them itself, and
  // `cssColor` is where it does. No committed scheme holds a fractional channel,
  // which is exactly why nothing caught it — so one is made here, from a real
  // subgraph's own scheme, by putting every channel half a step off.
  const { pclaiPath, realCases, regionOf, inputPath } = await import("./real-cases.mjs");
  const { renderTubeMap } = await import("../../seqtubemap/render.mjs");

  const name = realCases[0];
  const scheme = JSON.parse(readFileSync(pclaiPath(name), "utf8"));
  for (const entry of Object.values(scheme)) {
    entry[0] = entry[0].map((channel) => channel + 0.5);
  }

  const { start, end } = regionOf(name);
  const { document, bandData } = await renderTubeMap({
    inputFile: inputPath(name),
    start,
    end,
    nodeWidthOption: "compressed",
    pclaiColorScheme: scheme,
  });

  // The scheme really did colour the picture, so the assertion below is about it.
  assert.ok(
    bandData.strands.some((strand) => /\.\d/.test(strand.color)),
    "no strand carries a fractional colour, so this test is no longer about anything",
  );

  assert.doesNotMatch(
    strandGroup(document),
    /fill: rgb\([^)]*\.\d/,
    "a band's colour reached the document with a fractional channel, which pgb cannot read",
  );
  assertParseableByPgb(document, bandData);
});
