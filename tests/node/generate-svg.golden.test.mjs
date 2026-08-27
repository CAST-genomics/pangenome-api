// Golden test for the sequence tube map generator: a committed input in, a
// committed document out, asserted byte for byte.
//
// This is the safety net the /seqtubemap rework leans on. The increments that
// follow replace how the document is produced — capturing the layout's output,
// removing the browser emulation, turning geometry from strings into numbers —
// and each one's claim is that the output is unchanged. Byte-identity is the
// right bar precisely because zero change is what is expected.
//
// When an increment legitimately changes the bytes, re-baseline deliberately:
//
//     npm run baseline:golden
//
// and review the resulting diff as part of that increment.
//
// Runs with no `vg`, no graph data and no network — the inputs are synthetic and
// committed, and the generator reads nothing else.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import {
  cases,
  goldenDir,
  goldenPath,
  inputBytes,
  inputPath,
  render,
  renderCase,
  repoRoot,
} from "./golden-cases.mjs";

for (const testCase of cases) {
  test(`the ${testCase.name} fixture renders byte-identically to its golden document`, () => {
    const actual = renderCase(testCase);
    const expected = readFileSync(goldenPath(testCase));
    // One assertion, not two: a length check first would shadow the byte offset
    // in the very case where it is most useful. `assert.ok` rather than
    // `assert.equal` because a diff of two 800 KB documents is unreadable — the
    // offset and the surrounding text are what actually locate the change.
    assert.ok(actual.equals(expected), describeDifference(actual, expected, goldenPath(testCase)));
  });

  test(`the ${testCase.name} fixture regenerates byte-identically from its seed`, () => {
    // The committed input is a convenience, not a secret: the same seed and
    // parameters must reproduce it exactly, or the goldens above pin an input
    // nobody can rebuild.
    assert.ok(
      Buffer.from(inputBytes(testCase), "utf8").equals(readFileSync(inputPath(testCase))),
      `${inputPath(testCase)} is not what its seed and parameters produce`,
    );
  });
}

test("the large fixture exercises many strands", () => {
  // A golden document only guards what it contains. The small case would pass
  // just as happily if strand layout collapsed to one strand, so one case has to
  // carry enough of them for that to show.
  const svg = readFileSync(goldenPath(cases.find((c) => c.name === "large")), "utf8");
  const strandNames = new Set([...svg.matchAll(/trackName="([^"]+)"/g)].map((m) => m[1]));
  assert.ok(strandNames.size >= 100, `only ${strandNames.size} strands in the large golden`);
});

function describeDifference(actual, expected, golden) {
  let at = 0;
  while (at < actual.length && at < expected.length && actual[at] === expected[at]) at += 1;
  const context = 60;
  return (
    `document differs from ${golden} at byte ${at} ` +
    `(${expected.length} bytes expected, ${actual.length} produced)\n` +
    `  expected: ...${expected.subarray(at, at + context).toString("utf8")}\n` +
    `  actual:   ...${actual.subarray(at, at + context).toString("utf8")}\n` +
    "If this increment is meant to change the output, re-baseline with `npm run baseline:golden` " +
    "and review the diff as part of it."
  );
}

// The synthetic cases above stand in for real inputs, which is what #18 asks for
// "until real inputs arrive". The two real subgraphs at `pgb`'s fetch ceiling —
// the regime that actually fails — are already committed next door, but the
// golden documents that match them are not: `pgb`'s five predate a change in how
// strands are named, and do not line up with these inputs today (see
// tests/fixtures/seqtubemap/README.md, "Two conventions").
//
// So the test is written against them now and skips with a stated reason, rather
// than being deferred. Drop a document at the path below and it starts running.
const FETCH_CEILING_FIXTURES = [
  "subgraph_chr1_25301271_25309238_v2_with_walk",
  "subgraph_chr1_25331646_25335796_v2_with_walk",
];

for (const name of FETCH_CEILING_FIXTURES) {
  const input = join(repoRoot, "tests", "fixtures", "seqtubemap", `${name}.json`);
  const golden = join(goldenDir, "real", `${name}.svg`);

  test(`${name} renders byte-identically to its golden document`, { skip: skipReason(golden) }, () => {
    // The region comes from the filename because that is where the endpoint gets
    // it too: it rebuilds the cache path from the query parameters, so the
    // coordinates in the name are the coordinates of the request.
    const [, start, end] = name.match(/_(\d+)_(\d+)_v2_/).map(Number);
    const actual = render(input, "compressed", { start, end });
    assert.ok(actual.equals(readFileSync(golden)), describeDifference(actual, readFileSync(golden), golden));
  });
}

function skipReason(golden) {
  if (existsSync(golden)) return false;
  return `no golden document at ${golden} — pgb's documents predate a strand-naming change and do not match these inputs (see tests/fixtures/seqtubemap/README.md)`;
}
