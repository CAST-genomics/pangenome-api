// Re-generate the fixtures the two repositories exchange, for the five real
// subgraphs:
//
//     npm run fixtures:exchange
//
// Both encodings of one render each — the band payload `/seqtubemap?format=bands`
// returns, and the document the same request returns without it — written under
// `tests/fixtures/exchange/` with `pgb`'s file names, so that handing them over
// is a copy:
//
//     cp tests/fixtures/exchange/* ../pgb/src/tubemap/__tests__/fixtures/
//
// Run it deliberately, as part of an increment meant to change what the endpoint
// serves, and copy in the same window. `exchange-fixtures.test.mjs` fails the
// moment the committed bytes stop being what this code writes, which is what
// keeps "deliberately" from meaning "eventually".
//
// About two seconds for all five, but a large heap while it runs: 101,742 bands
// over 1,219 segment boxes, and the documents are 29.93 MB before compression.
// The npm script raises it for the same reason `baseline:bands` does.
//
// Deterministic, down to the gzip: a re-run with nothing changed rewrites the
// same bytes and leaves no diff, so a diff here is always something moving.
import { mkdirSync, writeFileSync } from "node:fs";
import { gzipSync, constants } from "node:zlib";

import { encodeBandPayload } from "../../seqtubemap/band-payload.mjs";
import { exchangeCases, documentPath, exchangeDir, payloadPath, stemFor } from "./exchange-cases.mjs";
import { renderReal } from "./real-cases.mjs";

mkdirSync(exchangeDir, { recursive: true });

for (const name of exchangeCases) {
  const { bandData, document } = await renderReal(name);
  const payload = encodeBandPayload(bandData);
  // Maximum compression: written rarely, read on every run, and the whole reason
  // a 13.19 MB document is committable at all. The test compares the
  // decompressed text, so nothing here pins zlib's output.
  const gz = gzipSync(document, { level: constants.Z_BEST_COMPRESSION });

  writeFileSync(payloadPath(name), payload);
  writeFileSync(documentPath(name), gz);

  console.log(
    `${stemFor(name).padEnd(37)} ${String(bandData.strands.length).padStart(5)} strands ` +
      `${String(bandData.bands.length).padStart(6)} bands  ` +
      `payload ${mb(payload.byteLength).padStart(9)}  ` +
      `document ${mb(document.length).padStart(9)} -> ${mb(gz.length).padStart(9)}`,
  );
}

function mb(bytes) {
  return `${(bytes / 1e6).toFixed(2)} MB`;
}
