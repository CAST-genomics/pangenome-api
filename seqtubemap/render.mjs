// Render a sequence tube map in this process, and hand back both of its
// products: the band data the layout produced, and the document written from it.
//
// There is no browser here any more. The layout used to bind its numbers to
// elements in a jsdom document and the document's `outerHTML` was the answer;
// that document was 93.7% of the render's retained memory and cost ~722 ms to
// stand up on every request, including the smallest. Now the layout collects
// the same numbers as band data (`band-data.mjs`) and `emit-document.mjs`
// writes the bytes from them. `jsdom` and `canvas` are gone from the dependency
// tree with it.
//
// The document remains compatible with `pgb`'s existing parser as a deliberate
// constraint — see `emit-document.mjs` for what that constraint is and
// `tests/node/document-conformance.test.mjs` for what holds it.
//
// The layout still wants its config in a global before it is imported at all,
// which is the one thing left that this module has to sequence, and the reason
// it loads `tubemap.js` dynamically.
import { readFileSync } from "node:fs";

import { emitDocument } from "./emit-document.mjs";
import { installLayoutConfig } from "./layout-config.mjs";

let loaded = null;

// One import per process, not per render: the module carries the layout's state
// and `create()` resets it before it draws.
async function layout() {
  if (loaded) return loaded;

  // Config must be set before tubemap.js is imported: config-global.mjs reads it
  // at module scope and throws if it is not there.
  installLayoutConfig();

  loaded = await import("./tubemap.js");
  return loaded;
}

/**
 * Render one vg JSON input.
 *
 * @param {object} options
 * @param {string} options.inputFile   path to the `vg view -j` JSON
 * @param {number} options.start       the requested region's first base
 * @param {number} options.end         the requested region's last base
 * @param {string} options.nodeWidthOption  "compressed", "normal" or "small"
 * @param {object|null} [options.pclaiColorScheme]
 * @returns {{document: string, bandData: object}}
 */
export async function renderTubeMap({
  inputFile,
  start,
  end,
  nodeWidthOption,
  pclaiColorScheme = null,
}) {
  const {
    create,
    vgExtractNodes,
    vgExtractTracks,
    reorderTracksForLayout,
    getBandData,
  } = await layout();

  const vgJson = JSON.parse(readFileSync(inputFile, "utf8"));

  const segments = vgExtractNodes(vgJson);
  const strands = reorderTracksForLayout(vgExtractTracks(vgJson, 0, 1));
  // DEBUGGING — the fork logs its own progress to stderr; this is the line the
  // CLI has always printed alongside it.
  console.error("tracks[0].name:", strands[0].name, "length:", strands[0].sequence.length);

  create({
    // The layout's own vocabulary: its `nodes` are this codebase's segments,
    // and its `tracks` are its strands (CONTEXT.md).
    nodes: segments,
    tracks: strands,
    reads: null,
    region: [0, end - start - 1],
    hideLegend: true,
    nodeWidthOption: nodeWidthOption,
    pclaiColorScheme: pclaiColorScheme,
  });

  const bandData = getBandData();

  // The document and the band data cannot disagree about the picture, because
  // there is only one of them: the document *is* the band data, written out.
  return { document: emitDocument(bandData), bandData };
}
