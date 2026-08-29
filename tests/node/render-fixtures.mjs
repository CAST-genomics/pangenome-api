// Render the five real subgraphs to SVG documents, for looking at.
//
//     npm run render:fixtures                 # into ./rendered/
//     npm run render:fixtures -- ~/somewhere  # into a directory of your choosing
//
// This is the shortest path from this repository to a tube map you can open.
// It needs no server, no graph data, no `vg`, and no Docker: the fixtures
// include the vg JSON each region produces, which is the output of the entire
// Python half of the pipeline, so what runs here is exactly the Node stage
// `/seqtubemap` spawns — `renderTubeMap`, through the same `real-cases.mjs` the
// band test uses, so a document rendered here cannot have been produced by a
// different code path than the one under test.
//
// Why it exists: `pgb` can load a static document, so these are what you point a
// dev harness at when the live server is unavailable or its deploy is behind
// `main` — which, at the time of writing, it is (docs/releasing.md). Confirming
// a document *renders* is the one thing the byte comparisons in the test suite
// cannot do.
//
// Each region is rendered twice. Without a PCLAI colour scheme is a plain region
// request; with one is what production passes whenever `minigraphnode` is set
// (main.py:767), and it takes over strand colour entirely — so the pair is also
// how you see that path on its own.
//
// The outputs are large (57 MB for the ten) and `*.svg*` is gitignored
// repo-wide, so they stay out of commits wherever they are written.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { repoRoot } from "./golden-cases.mjs";
import { inputPath, realCases, regionOf, renderReal } from "./real-cases.mjs";
import { renderTubeMap } from "../../seqtubemap/render.mjs";

const outDir = process.argv[2] ?? join(repoRoot, "rendered");
mkdirSync(outDir, { recursive: true });

console.log(`Rendering ${realCases.length} subgraphs, with and without PCLAI, into ${outDir}\n`);

for (const name of realCases) {
  const { start, end } = regionOf(name);
  // The short name is the region, which is what identifies a document to a human
  // opening it; the fixture's own name carries the pipeline's spelling of it.
  const short = name.replace(/^subgraph_/, "").replace(/_v2_with_walk$/, "");

  for (const pclai of [false, true]) {
    const started = Date.now();
    // `renderReal` is the shared path and supplies the colour scheme; the plain
    // variant is the same call with it left out, spelled here rather than in
    // `real-cases.mjs` so the shared helper keeps meaning "as the endpoint would".
    const { document, bandData } = pclai
      ? await renderReal(name)
      : await renderTubeMap({
          inputFile: inputPath(name),
          start,
          end,
          nodeWidthOption: "compressed",
          pclaiColorScheme: null,
        });

    const file = join(outDir, `${short}${pclai ? ".pclai" : ""}.svg`);
    writeFileSync(file, document, "utf8");
    console.log(
      `${mb(document.length).padStart(8)}  ${String(Date.now() - started).padStart(5)} ms  ` +
        `${String(bandData.strands.length).padStart(5)} strands  ` +
        `${String(bandData.bands.length).padStart(6)} bands  ${file}`,
    );
  }
}

function mb(bytes) {
  return `${(bytes / 1048576).toFixed(2)} MB`;
}
