// CLI over the sequence tube map renderer: vg JSON in, one SVG document out.
// This is the process `/seqtubemap` spawns. The render itself lives in
// `render.mjs`, so that a caller inside Node can render without spawning
// anything.
import { writeFileSync } from "fs";

import { renderTubeMap } from "./render.mjs";

if (process.argv.length < 7 || process.argv.length > 8) {
  console.error(`Error: 5 or 6 arguments required, got ${process.argv.length - 2}`);
  console.error(`Usage: node generate-svg.mjs <input.json> <output.svg> <startloc> <endloc> <nodeWidthOption> [pclaiColorSchemeJson]`);
  process.exit(1);
}

const inputFile  = process.argv[2];
const outputFile = process.argv[3];
const start = parseInt(process.argv[4]);
const end = parseInt(process.argv[5]);
const nodeWidthOption = process.argv[6];
const pclaiColorSchemeArg = process.argv[7]; // optional

let pclaiColorScheme = null;
if (pclaiColorSchemeArg !== undefined) {
  pclaiColorScheme = JSON.parse(pclaiColorSchemeArg);
}

const { document } = await renderTubeMap({
  inputFile,
  start,
  end,
  nodeWidthOption,
  pclaiColorScheme,
});

writeFileSync(outputFile, document, "utf8");
console.log(`SVG written to ${outputFile}`);
