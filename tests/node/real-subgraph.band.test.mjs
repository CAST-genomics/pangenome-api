// The band data the five real subgraphs produce, pinned against a baseline
// committed here.
//
// This is the coverage #13 asks for and the synthetic goldens next door cannot
// give: "the two documents at the fetch ceiling … so that the regime that
// actually fails is the regime under test". The synthetic cases cover the
// mechanism — 121 strands over a 40-segment spine — at a size that is pleasant to
// commit. These are 369 to 1,201 strands over as many as 768 segments, which is
// where the layout's cost, and its failures, actually live.
//
// **Why band data and not a document.** These tests were written earlier against
// a recaptured SVG from the server and skipped waiting for one to appear. That
// was the wrong artifact to wait for: `docs/adr/0001-additive-band-format.md`
// makes the band data canonical and the document derived from it, so pinning the
// document buys a weaker guarantee at ten times the size — 13.19 MB of XML against
// 1.04 MB of gzipped numbers for the largest fixture. Since #22 that is literally
// true of the running code: the document is written from this data, so the
// baseline pins the bytes the endpoint serves as surely as a golden document
// would, and the document is checked here as what the baseline writes out.
//
// When an increment is meant to change the layout's output, re-baseline
// deliberately and review the diff as part of it:
//
//     npm run baseline:bands
//
// Runs with no `vg`, no network and no graph data — every input is committed.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { strandIdentity } from "../../seqtubemap/strand.mjs";
import { assertParseableByPgb } from "./pgb-parser.mjs";
import { emitDocument } from "../../seqtubemap/emit-document.mjs";
import {
  baselinePath,
  pclaiPath,
  readBaseline,
  realCases,
  renderReal,
  serializeBandData,
} from "./real-cases.mjs";

for (const name of realCases) {
  // One render per fixture, and it is scoped to this test rather than hoisted to
  // the file: rendering the 4.2 kb subgraph costs gigabytes of transient heap, and
  // holding all five at once would make the suite's peak the sum of them rather
  // than the largest of them.
  test(name, async (t) => {
    const { document, bandData } = await renderReal(name);
    const baseline = readBaseline(name);

    await t.test("produces its baselined band data", () => {
      // One assertion over the whole serialization, with the divergence located by
      // hand: `assert.equal` on two multi-megabyte strings prints a diff nobody can
      // read, and the byte offset plus its surroundings is what actually says what
      // moved.
      const actual = serializeBandData(bandData);
      assert.ok(actual === baseline, describeDifference(actual, baseline, baselinePath(name)));
    });

    await t.test("has the document the committed baseline writes out", () => {
      // Written from the *committed baseline*, not from the render above, so the
      // claim is about the bytes on disk: this is the document the endpoint
      // serves for this region, accounted for in full rather than in prefix.
      const rebuilt = emitDocument(JSON.parse(baseline));
      assert.ok(document === rebuilt, describeReconstruction(document, rebuilt));
    });

    await t.test("has a document `pgb`'s parser can read", () => {
      // The constraint #22 ships under: the browser emulation went, and the
      // client did not change. `document-conformance.test.mjs` is where that
      // contract is written down; this is it applied to a real 464-strand
      // document, which is the regime that actually reaches the client.
      assertParseableByPgb(document, bandData);
    });

    await t.test("is coloured by its PCLAI scheme", () => {
      // Byte-identity cannot say which branch produced the bytes, and a scheme that
      // quietly stopped being applied would just re-baseline. The scheme is the
      // third input to the render (see real-cases.mjs); this is what holds it there.
      const scheme = JSON.parse(readFileSync(pclaiPath(name), "utf8"));

      // A strand reaches the document under `vg`'s longer spelling and is looked up
      // by the `sample#haplotype#contig` triple, so one key may name several rows —
      // a haplotype fragmented across the region contributes a walk each — and a
      // row's key may be absent from the scheme entirely.
      const used = new Set();
      const unlisted = [];
      for (const strand of bandData.strands) {
        const key = strandIdentity(strand.name);
        const entry = scheme[key];
        if (!entry) {
          unlisted.push(strand);
          continue;
        }
        used.add(key);
        const [[r, g, b], [x, y], score] = entry;
        assert.equal(strand.color, `rgb(${r}, ${g}, ${b})`, `${strand.name} is not its scheme colour`);
        assert.equal(strand.pclaiX, x, `${strand.name} pclaiX`);
        assert.equal(strand.pclaiY, y, `${strand.name} pclaiY`);
        assert.equal(strand.pclaiScore, score, `${strand.name} pclaiScore`);
      }

      // Every entry found its strand — the exact set, not a threshold. The scheme
      // was recovered from a document of this very region, so a key that matches
      // nothing means the two have drifted apart, which is the thing most worth
      // hearing about.
      assert.deepEqual([...used].sort(), Object.keys(scheme).sort());

      // And the strands the scheme does not mention fall back to light grey with no
      // placement, rather than to the default palette. Both shapes have to be
      // present, or the fixture is only covering one branch.
      assert.ok(unlisted.length > 0, "every strand is in the scheme, so the fallback is untested");
      for (const strand of unlisted) {
        assert.equal(strand.color, "rgb(211, 211, 211)", `${strand.name} kept a palette colour`);
        assert.equal(strand.pclaiX, null, `${strand.name} pclaiX`);
        assert.equal(strand.pclaiY, null, `${strand.name} pclaiY`);
        assert.equal(strand.pclaiScore, null, `${strand.name} pclaiScore`);
      }
    });
  });
}

function describeDifference(actual, expected, baseline) {
  return (
    `band data differs from ${baseline} ${locate(actual, expected)}` +
    "If this increment is meant to change the layout's output, re-baseline with " +
    "`npm run baseline:bands` and review the diff as part of it."
  );
}

function describeReconstruction(document, rebuilt) {
  return (
    `the baseline writes a different document ${locate(rebuilt, document)}` +
    "The render and the committed band data disagree about the picture."
  );
}

/** Where two long strings first disagree, and what each says there. */
function locate(actual, expected) {
  let at = 0;
  while (at < actual.length && at < expected.length && actual[at] === expected[at]) at += 1;
  const context = 120;
  return (
    `at byte ${at} (${expected.length} bytes expected, ${actual.length} produced)\n` +
    `  expected: ...${expected.slice(at, at + context)}\n` +
    `  actual:   ...${actual.slice(at, at + context)}\n`
  );
}
