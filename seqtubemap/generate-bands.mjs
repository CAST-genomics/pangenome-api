// CLI over the sequence tube map renderer: vg JSON in, one band payload out.
// This is the process `/seqtubemap?format=bands` spawns, and it is
// `generate-svg.mjs` with the other sink — the same render, written to the wire
// as numbers rather than as a drawing document (see `band-payload.mjs`).
import { writeFileSync } from "fs";

import { encodeBandPayload } from "./band-payload.mjs";
import { runGenerator } from "./generator-cli.mjs";

const { outputFile, render } = await runGenerator(
  "Usage: node generate-bands.mjs <input.json> <output.bands> <startloc> <endloc> <nodeWidthOption> [pclaiColorSchemeJson]",
);

// The document is never built on this route: `renderTubeMap` writes it on first
// access and nothing here asks. It stays *derivable* — the payload carries
// everything `emit-document.mjs` reads — but a request for bands pays for
// neither the string building nor the megabytes.
writeFileSync(outputFile, encodeBandPayload(render.bandData));
console.log(`band payload written to ${outputFile}`);
