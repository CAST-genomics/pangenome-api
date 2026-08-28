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
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { cases, goldenPath, repoRoot } from "./golden-cases.mjs";
import { assertParseableByPgb, drawables } from "./pgb-parser.mjs";

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
  // all correct, and no longer contiguous.
  const golden = readFileSync(goldenPath(cases[0]), "utf8");
  const reordered = golden.replace(/ trackID="(\d+)"/g, ' class="track$1" trackID="$1"');
  assert.throws(() => assertParseableByPgb(reordered), /pgb matches on|class attribute/);
});
