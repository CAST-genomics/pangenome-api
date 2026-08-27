// Smoke test for the Node stage of /seqtubemap: the sequence tube map generator
// is driven over a small fixture and must produce a document.
//
// The fixture is the shape `vg view -j` emits, which is all tubemap.js reads.
// It needs no `vg` binary and no graph data, so this test runs anywhere Node does.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const generator = join(repoRoot, "seqtubemap", "generate-svg.mjs");
const fixture = join(repoRoot, "tests", "fixtures", "tiny-vg.json");

// The fixture's reference strand spans 69 bases; the generator is handed the
// region as [start, end] in the same coordinates /seqtubemap passes them.
const START = 0;
const END = 69;
const NODE_WIDTH_OPTION = "normal";

function generateSvg() {
  const outDir = mkdtempSync(join(tmpdir(), "tubemap-smoke-"));
  const outFile = join(outDir, "tubemap.svg");
  execFileSync(
    process.execPath,
    [generator, fixture, outFile, String(START), String(END), NODE_WIDTH_OPTION],
    { cwd: repoRoot, stdio: ["ignore", "pipe", "pipe"] },
  );
  assert.ok(existsSync(outFile), `generator did not write ${outFile}`);
  return readFileSync(outFile, "utf8");
}

// One document, read by every test below: the generator is a subprocess, and
// nothing here mutates what it returns.
const svg = generateSvg();

test("the generator produces an SVG document from a vg JSON fixture", () => {
  assert.match(svg, /^<svg /, "output does not start with an <svg> element");
  assert.match(svg, /xmlns="http:\/\/www\.w3\.org\/2000\/svg"/);
  assert.match(svg, /viewBox="[-\d. ]+"/);
  assert.ok(svg.trimEnd().endsWith("</svg>"), "output is not a closed document");
});

test("the document carries bands attributed to named strands", () => {
  // pgb's parser reads bands out of `g.track`, keyed by the trackID/trackName
  // pair. A document without them is a document it cannot use.
  assert.ok(svg.includes('<g class="track">'), "no g.track group in the document");

  const bands = svg.match(/<(rect|path)\b/g) ?? [];
  assert.ok(bands.length > 0, "document contains no bands");

  const strandNames = new Set(
    [...svg.matchAll(/trackName="([^"]+)"/g)].map((m) => m[1]),
  );
  // The fixture carries GRCh38 plus three assembly strands.
  assert.equal(strandNames.size, 4);
  assert.ok(strandNames.has("GRCh38#0#chr1"), "the reference strand is missing");
});
