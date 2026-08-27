// The golden tube map cases, shared by the test that checks them and the script
// that re-baselines them. Both must agree on every input to the generator —
// the fixture's contents, the region, the node width option — because a golden
// document is only meaningful if the two sides invoke the generator identically.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { generate } from "../../perf/gen-vg-json.mjs";

export const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
export const goldenDir = join(repoRoot, "tests", "fixtures", "tubemap-golden");
const generator = join(repoRoot, "seqtubemap", "generate-svg.mjs");

// Synthetic, because the real inputs behind `pgb`'s golden documents live on the
// live server (see tests/fixtures/seqtubemap/README.md). `generate` is seeded, so
// these are byte-reproducible from the parameters alone — the fixtures are
// committed for speed and for review, not because they cannot be rebuilt.
//
// Two sizes on purpose: the small one is legible in a diff, the large one carries
// enough strands that a change to how strands are laid out or ordered shows up.
// `nodeWidthOption` is "compressed" throughout — the endpoint's own default
// (main.py:720), and the only width mode whose geometry is portable. "normal"
// measures the segment's label with the platform's fonts, so its bytes differ between
// a developer's machine and CI and cannot be goldened; the smoke test covers that
// mode without asserting on bytes.
export const cases = [
  {
    name: "small",
    // 7 strands over a 12-segment spine.
    params: { spineNodes: 12, haplotypes: 6, seqLen: 8, seed: 1 },
    nodeWidthOption: "compressed",
  },
  {
    name: "large",
    // 121 strands — the same order of magnitude as a real subgraph's 369–464,
    // at a size that is still reasonable to commit.
    params: { spineNodes: 40, haplotypes: 120, seqLen: 12, seed: 7 },
    nodeWidthOption: "compressed",
  },
];

export function inputPath(testCase) {
  return join(goldenDir, `${testCase.name}.vg.json`);
}

export function goldenPath(testCase) {
  return join(goldenDir, `${testCase.name}.svg`);
}

/** The fixture's bytes, built from the case's seed and parameters alone. */
export function inputBytes(testCase) {
  return JSON.stringify(generate(testCase.params));
}

export function writeInput(testCase) {
  writeFileSync(inputPath(testCase), inputBytes(testCase), "utf8");
}

// `/seqtubemap` passes the requested region's coordinates through to the
// generator, which uses only their difference. The reference strand is the whole
// spine, so its length is the synthetic region's span.
export function regionFor(vgJson) {
  const lengthById = new Map(vgJson.node.map((n) => [n.id, n.sequence.length]));
  const reference = vgJson.path[0];
  const span = reference.mapping.reduce(
    (total, m) => total + lengthById.get(m.position.node_id),
    0,
  );
  return { start: 0, end: span };
}

/**
 * Run the generator over an input and return the document as raw bytes.
 *
 * Bytes, not a string: "byte-identical" is the bar this whole test exists to
 * hold, and comparing decoded strings would compare UTF-16 code units instead.
 */
export function render(input, nodeWidthOption, region) {
  // A synthetic input carries no coordinates, so its region is derived from the
  // reference strand's length. A real one is named for the region it came from,
  // and the caller passes those coordinates through as the endpoint does.
  const { start, end } = region ?? regionFor(JSON.parse(readFileSync(input, "utf8")));
  const outDir = mkdtempSync(join(tmpdir(), "tubemap-golden-"));
  try {
    const outFile = join(outDir, "tubemap.svg");
    execFileSync(
      process.execPath,
      [generator, input, outFile, String(start), String(end), nodeWidthOption],
      { cwd: repoRoot, stdio: ["ignore", "ignore", "pipe"] },
    );
    return readFileSync(outFile);
  } finally {
    rmSync(outDir, { recursive: true, force: true });
  }
}

/** Run the generator over a case's committed input. */
export function renderCase(testCase) {
  return render(inputPath(testCase), testCase.nodeWidthOption);
}
