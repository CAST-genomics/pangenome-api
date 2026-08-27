// Re-baseline the golden tube map documents. Run deliberately, as part of an
// increment that is meant to change the generator's output:
//
//     npm run baseline:golden
//
// It rewrites both the inputs (from their seeds) and the documents, then leaves
// the diff in the working tree for review. A re-baseline that was not intended
// shows up as a golden document changing in a commit that claimed not to.
import { writeFileSync } from "node:fs";

import { cases, goldenPath, renderCase, writeInput } from "./golden-cases.mjs";

for (const testCase of cases) {
  writeInput(testCase);
  const svg = renderCase(testCase);
  writeFileSync(goldenPath(testCase), svg);
  console.log(`${testCase.name}: ${svg.length} bytes -> ${goldenPath(testCase)}`);
}
