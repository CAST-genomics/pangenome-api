// CLI over the sequence tube map renderer: vg JSON in, one SVG document out.
// This is the process `/seqtubemap` spawns. The render itself lives in
// `render.mjs`, so that a caller inside Node can render without spawning
// anything, and the command line lives in `generator-cli.mjs`, which this
// shares with the band generator.
import { writeFileSync } from "fs";

import { runGenerator } from "./generator-cli.mjs";

const { outputFile, render } = await runGenerator(
  "Usage: node generate-svg.mjs <input.json> <output.svg> <startloc> <endloc> <nodeWidthOption> [pclaiColorSchemeJson]",
);

writeFileSync(outputFile, render.document, "utf8");
console.log(`SVG written to ${outputFile}`);
