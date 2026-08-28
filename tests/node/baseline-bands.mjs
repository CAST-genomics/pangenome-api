// Re-baseline the band data for the five real subgraphs. Run deliberately, as
// part of an increment that is meant to change the layout's output:
//
//     npm run baseline:bands
//
// Separate from `baseline:golden` because the two cost different things. The
// synthetic goldens re-render in about a second; these render 369 to 1,201
// strands over as many as 768 segments, take longer, and want a large heap —
// which is why the npm script raises it.
//
// It leaves the diff in the working tree for review. A re-baseline that was not
// intended shows up as a baseline changing in a commit that claimed not to.
import { writeFileSync } from "node:fs";
import { gzipSync, constants } from "node:zlib";

import {
  baselinePath,
  realCases,
  renderReal,
  serializeBandData,
} from "./real-cases.mjs";

for (const name of realCases) {
  const { bandData } = await renderReal(name);
  const json = serializeBandData(bandData);
  // Maximum compression: these are written rarely and read on every run, and the
  // whole reason the baselines are committable is the ~7.5x gzip buys on them.
  // The test compares the decompressed text, so nothing here pins zlib's output.
  const gz = gzipSync(json, { level: constants.Z_BEST_COMPRESSION });
  writeFileSync(baselinePath(name), gz);
  console.log(
    `${name}: ${bandData.strands.length} strands, ${bandData.bands.length} bands, ` +
      `${mb(json.length)} of JSON -> ${mb(gz.length)} at ${baselinePath(name)}`,
  );
}

function mb(bytes) {
  return `${(bytes / 1e6).toFixed(2)} MB`;
}
