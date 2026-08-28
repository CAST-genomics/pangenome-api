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
//
// The third case renders the *same* input as `small` through the generator's
// optional sixth argument, the PCLAI colour scheme. Production passes it whenever
// `minigraphnode` is set (main.py:767), and it takes over strand colour entirely
// (tubemap.js:2503), so without a case carrying one that branch produces bytes
// nothing pins. Sharing `small`'s input is the point: the two documents differ
// only by the scheme, which is what makes "strand colour passes through
// untouched" checkable rather than asserted.
const small = {
  name: "small",
  // 7 strands over a 12-segment spine.
  params: { spineNodes: 12, haplotypes: 6, seqLen: 8, seed: 1 },
  nodeWidthOption: "compressed",
};

export const cases = [
  small,
  {
    name: "large",
    // 121 strands — the same order of magnitude as a real subgraph's 369–464,
    // at a size that is still reasonable to commit.
    params: { spineNodes: 40, haplotypes: 120, seqLen: 12, seed: 7 },
    nodeWidthOption: "compressed",
  },
  {
    ...small,
    name: "small-pclai",
    inputName: small.name,
    // Committed next door rather than inlined, so the generator's actual input is
    // a file a reader can open. It carries all three shapes an entry can take:
    // strands with a PCLAI colour, one with the grey no-coordinate entry the
    // endpoint emits for `x_coord == "."` (main.py:684), and strands the scheme
    // does not mention, which fall back to light grey. The last two are the same
    // grey, so only the pclaiX/Y/Score attributes tell them apart — which is why
    // the golden test checks those as well as the colours.
    pclaiColorScheme: "pclai-color-scheme.json",
  },
];

/**
 * The PCLAI colour scheme a case is rendered with, or null if it has none.
 *
 * The text, because that is what the generator takes: the argument crosses a
 * process boundary as JSON, and re-serializing a parsed copy would render from
 * bytes the fixture does not contain. Callers rendering in-process parse it.
 */
export function pclaiColorSchemeText(testCase) {
  if (!testCase.pclaiColorScheme) return null;
  return readFileSync(join(goldenDir, testCase.pclaiColorScheme), "utf8");
}

// Cases may share an input — `small-pclai` renders `small`'s — so that the only
// difference between their documents is the argument under test.
export function inputPath(testCase) {
  return join(goldenDir, `${testCase.inputName ?? testCase.name}.vg.json`);
}

export function goldenPath(testCase) {
  return join(goldenDir, `${testCase.name}.svg`);
}

/** The fixture's bytes, built from the case's seed and parameters alone. */
export function inputBytes(testCase) {
  return JSON.stringify(generate(testCase.params));
}

/**
 * Write a case's input from its seed. A case that borrows another's input has
 * none of its own: writing it would let a copied case silently redefine the
 * input its original is goldened against.
 */
export function writeInput(testCase) {
  if (testCase.inputName) return;
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
export function render(input, nodeWidthOption, { colorSchemeText } = {}) {
  // A synthetic input carries no coordinates of its own, so its region is derived
  // from the reference strand's length. The real subgraphs are named for the
  // region they came from and are rendered in-process instead; see
  // real-cases.mjs.
  const { start, end } = regionFor(JSON.parse(readFileSync(input, "utf8")));
  const outDir = mkdtempSync(join(tmpdir(), "tubemap-golden-"));
  try {
    const outFile = join(outDir, "tubemap.svg");
    const args = [generator, input, outFile, String(start), String(end), nodeWidthOption];
    // Appended, not passed as an empty string: the generator distinguishes an
    // absent sixth argument from any value, and the no-scheme cases must keep
    // invoking the five-argument form production uses when `minigraphnode` is unset.
    if (colorSchemeText !== null) args.push(colorSchemeText);
    execFileSync(
      process.execPath,
      args,
      { cwd: repoRoot, stdio: ["ignore", "ignore", "pipe"] },
    );
    return readFileSync(outFile);
  } finally {
    rmSync(outDir, { recursive: true, force: true });
  }
}

/** Run the generator over a case's committed input. */
export function renderCase(testCase) {
  return render(inputPath(testCase), testCase.nodeWidthOption, {
    colorSchemeText: pclaiColorSchemeText(testCase),
  });
}

/** The case of that name, so a test can name the one it is about. */
export function caseNamed(name) {
  const testCase = cases.find((candidate) => candidate.name === name);
  if (!testCase) throw new Error(`no golden case named ${name}`);
  return testCase;
}
