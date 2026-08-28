// The five real subgraphs, and the three inputs each one takes to a render.
//
// Shared by the test that checks their band data and the script that
// re-baselines it, for the same reason `golden-cases.mjs` is shared: a baseline
// is only meaningful if both sides invoke the layout identically.
//
// A case is a region, and the fixture directory holds every input it needs:
//
//   <name>.gfa           the subgraph as the server wrote it — the source of truth
//   <name>.json          the same subgraph in the shape the layout eats
//   <name>.pclai.json    the PCLAI colour scheme the region was rendered with
//
// and the baseline this repository pins against:
//
//   <name>.band.json.gz  the band data that render produces
//
// See ../fixtures/seqtubemap/README.md for where each of those came from.
import { gunzipSync } from "node:zlib";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderTubeMap } from "../../seqtubemap/render.mjs";
import { repoRoot } from "./golden-cases.mjs";

export const fixtureDir = join(repoRoot, "tests", "fixtures", "seqtubemap");

// Every committed real subgraph, smallest first, so a run that is going to fail
// tends to fail on the cheap one. `pgb`'s fetch ceiling is the last two: they are
// the regime that actually fails (#13), and the reason this list is not just the
// 90 bp fixture the other tests already use.
export const realCases = [
  "subgraph_chr8_78771162_78771252_v2_with_walk",
  "subgraph_chr1_25331046_25331646_v2_with_walk",
  "subgraph_chr8_10079054_10080461_v2_with_walk",
  "subgraph_chr1_25301271_25309238_v2_with_walk",
  "subgraph_chr1_25331646_25335796_v2_with_walk",
];

/**
 * The region a fixture covers, read from its filename.
 *
 * The filename is where the endpoint gets it too: it rebuilds the cache path
 * from the query parameters, so the coordinates in the name are the coordinates
 * of the request (main.py:665-676).
 */
export function regionOf(name) {
  const [, start, end] = name.match(/_(\d+)_(\d+)_v2_/).map(Number);
  return { start, end };
}

export function inputPath(name) {
  return join(fixtureDir, `${name}.json`);
}

export function pclaiPath(name) {
  return join(fixtureDir, `${name}.pclai.json`);
}

export function baselinePath(name) {
  return join(fixtureDir, `${name}.band.json.gz`);
}

/** Render one real subgraph exactly as the endpoint would, all three inputs in. */
export async function renderReal(name) {
  const { start, end } = regionOf(name);
  return renderTubeMap({
    inputFile: inputPath(name),
    start,
    end,
    // The endpoint's own default (main.py:720), and the only width mode whose
    // geometry is portable — "normal" measures labels with the platform's fonts.
    nodeWidthOption: "compressed",
    pclaiColorScheme: JSON.parse(readFileSync(pclaiPath(name), "utf8")),
  });
}

/**
 * The band data as it is baselined: compact JSON.
 *
 * Thin, but it is the one place the writer and the reader agree on the format, so
 * a change to it cannot make the two disagree. Text rather than a value, because
 * text is what is compared: two structurally equal objects can serialize
 * differently — a reordered key is a real change to what a consumer parses — and
 * the point of a baseline is to notice that.
 */
export function serializeBandData(bandData) {
  return JSON.stringify(bandData);
}

/**
 * The committed baseline, as the same text.
 *
 * Stored gzipped and compared decompressed: gzip is what makes 18.02 MB of
 * baselines committable at 2.33 MB, and comparing the compressed bytes would pin
 * zlib's output as well as the layout's.
 */
export function readBaseline(name) {
  return gunzipSync(readFileSync(baselinePath(name))).toString("utf8");
}
