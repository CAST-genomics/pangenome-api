// The fixtures the two repositories exchange, checked against the code that
// produced them.
//
// #25: "a wire-format break fails loudly, on whichever side broke it." `pgb`
// holds one half of that — it parses a copy of these bytes in its own suite,
// with its own reader, which is the half that cannot be a vendored copy of this
// repository's parser. This is the other half: the bytes on disk here are what
// this repository's encoder and emitter produce *today*, from inputs committed
// beside them.
//
// Without this, the exchange rots quietly in the one direction that matters. A
// change to the encoder would leave the committed payload behind, `pgb` would go
// on parsing a fixture nothing serves any more, and both suites would be green
// about a contract neither was checking.
//
// When a change here is meant to move the wire bytes, re-generate and copy:
//
//     npm run fixtures:exchange
//     cp tests/fixtures/exchange/* ../pgb/src/tubemap/__tests__/fixtures/
//
// Runs with no `vg`, no network and no graph data — every input is committed.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  GEOMETRY_FIELDS,
  decodeBandPayload,
  encodeBandPayload,
} from "../../seqtubemap/band-payload.mjs";
import { renderReal } from "./real-cases.mjs";
import { readBands } from "./pgb-parser.mjs";
import {
  documentPath,
  exchangeCases,
  payloadPath,
  readExchangeDocument,
  readExchangePayload,
} from "./exchange-cases.mjs";

for (const name of exchangeCases) {
  // One render per fixture, scoped to the test for the same reason
  // `real-subgraph.band.test.mjs` scopes its own: the 4.2 kb subgraph costs
  // gigabytes of transient heap, and holding all five would make the suite's
  // peak their sum rather than the largest of them.
  test(`exchange fixtures for ${name}`, async (t) => {
    const { bandData, document } = await renderReal(name);

    await t.test("the committed payload is the payload this encoder writes", () => {
      const fresh = encodeBandPayload(bandData);
      const committed = readExchangePayload(name);
      // `assert.fail` rather than `assert.ok(…, describe…)`: the message is built
      // by walking two multi-megabyte buffers to the first byte that differs, and
      // an `ok`'s message argument is evaluated whether it fails or not.
      if (!sameBytes(fresh, committed)) assert.fail(describeBytes(fresh, committed, payloadPath(name)));
    });

    await t.test("the committed document is the document this emitter writes", () => {
      const committed = readExchangeDocument(name);
      // Compared decompressed, so nothing about zlib's output is pinned — a
      // different zlib writes different bytes on disk and the same green.
      if (document !== committed) assert.fail(describeText(document, committed, documentPath(name)));
    });

    await t.test("the committed pair describes one picture", () => {
      // What `pgb`'s copy of these two files is for, asserted here on the same
      // bytes: every band's six floats, read out of the payload, are the numbers
      // its parser recovers from the document, rounded once to Float32 and not
      // otherwise touched. This is the assertion that fails when a fixture is
      // altered — on this side as well as on theirs.
      const { geometry, strandIds, header } = decodeBandPayload(readExchangePayload(name));
      const { matched, counted } = readBands(readExchangeDocument(name));

      assert.equal(matched.length, counted, "pgb cannot read the whole committed document");
      assert.equal(matched.length, header.band.count, "the pair disagrees about the band count");

      matched.forEach((band, index) => {
        GEOMETRY_FIELDS.forEach((field, offset) => {
          assert.equal(
            geometry[index * 6 + offset],
            Math.fround(band[field]),
            `${field} of band ${index}`,
          );
        });
        assert.equal(header.strands[strandIds[index]].id, band.id, `strand id of band ${index}`);
        assert.equal(header.strands[strandIds[index]].name, band.name, `strand of band ${index}`);
      });
    });
  });
}

test("a payload altered to break the contract fails the pair check", () => {
  // #25 asks for the break to be *demonstrated*, and a demonstration that lives
  // in a README is a demonstration that was true once. This is it as a standing
  // test: nudge one band's far end by a part in 10,000 — a change far too small
  // to see and far too large to be rounding — and the pair check must notice.
  //
  // On the 90 bp fixture, which is the cheapest of the five and needs no render.
  const name = exchangeCases[0];
  const tampered = readExchangePayload(name);
  const bodyStart = (4 + new DataView(tampered.buffer, tampered.byteOffset, 4).getUint32(0, true) + 3) & ~3;
  const view = new DataView(tampered.buffer, tampered.byteOffset);
  const x1 = view.getFloat32(bodyStart + 8, true);
  view.setFloat32(bodyStart + 8, x1 * 1.0001, true);

  const { geometry } = decodeBandPayload(tampered);
  const { matched } = readBands(readExchangeDocument(name));

  assert.notEqual(
    geometry[2],
    Math.fround(matched[0].x1),
    "a band moved in the payload and the pair check did not notice",
  );
});

function sameBytes(a, b) {
  return a.byteLength === b.byteLength && a.every((byte, index) => byte === b[index]);
}

/** Where two byte strings first differ, which is what says what moved. */
function describeBytes(fresh, committed, path) {
  if (fresh.byteLength !== committed.byteLength) {
    return `${path} is ${committed.byteLength} bytes; this encoder writes ${fresh.byteLength}. ` +
      REGENERATE;
  }
  const at = firstDivergence(fresh, committed);
  return `${path} differs from what this encoder writes, first at byte ${at} ` +
    `(committed 0x${committed[at].toString(16)}, encoder 0x${fresh[at].toString(16)}). ` +
    REGENERATE;
}

/** The same, for the document: a diff of two megabytes of XML says nothing. */
function describeText(fresh, committed, path) {
  const at = firstDivergence(fresh, committed);
  return `${path} differs from what this emitter writes, first at character ${at}:\n` +
    `  committed: …${committed.slice(Math.max(0, at - 40), at + 40)}…\n` +
    `  emitter:   …${fresh.slice(Math.max(0, at - 40), at + 40)}…\n` +
    REGENERATE;
}

/** Where two indexable sequences first differ — bytes or characters, same walk. */
function firstDivergence(a, b) {
  const shortest = Math.min(a.length, b.length);
  for (let index = 0; index < shortest; index += 1) if (a[index] !== b[index]) return index;
  return shortest;
}

const REGENERATE =
  "If the change was intended, re-generate with `npm run fixtures:exchange` and copy the " +
  "result into pgb's src/tubemap/__tests__/fixtures/ in the same window — a payload this " +
  "repository no longer serves is a fixture pgb is green about for nothing.";
