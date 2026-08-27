// Render a sequence tube map in this process, and hand back both of its
// products: the document, and the band data the layout produced on the way to
// it.
//
// The document is byte-for-byte what `generate-svg.mjs` has always written —
// that CLI is now a thin wrapper around this function. The band data is the
// same numbers, before they were turned into attribute strings; see
// `band-data.mjs` for its shape.
//
// The browser emulation lives here because the layout still needs it: config
// first, then a jsdom window, and only then may `tubemap.js` be imported at
// all. That ordering is the reason this module loads it dynamically.
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { createCanvas } from "canvas";

let loaded = null;

// One jsdom window and one measuring canvas per process, not per render: both
// are expensive to build, and `create()` clears the SVG element before it draws.
async function environment() {
  if (loaded) return loaded;

  // 1. Config must be set first
  globalThis["__sequence_tube_map_config"] = {
    defaultHaplotypeColorPalette: { mainPalette: "reds", auxPalette: "blues" },
    defaultReadColorPalette:      { mainPalette: "reds", auxPalette: "blues" },
    defaultGraphColorPalette:     { mainPalette: "reds", auxPalette: "blues" },
    nodeIntervalThreshold: 150,
    coloredNodes: [],
    DATA_SOURCES: [],
    BACKEND_URL: "",
  };

  // 2. Fake browser environment
  const dom = new JSDOM(`<!DOCTYPE html><body><svg id="mysvg"></svg></body>`, {
    resources: "usable",
    pretendToBeVisual: true,
  });
  globalThis.window   = dom.window;
  globalThis.document = dom.window.document;

  // Patch getComputedTextLength
  const canvas = createCanvas(200, 200);
  const ctx = canvas.getContext("2d");
  ctx.font = '14px "Courier New"';
  dom.window.SVGElement.prototype.getComputedTextLength = function() {
    return ctx.measureText(this.textContent).width;
  };

  // 3. Import TubeMap
  const module = await import("./tubemap.js");
  loaded = { dom, module };
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
  const { dom, module } = await environment();
  const {
    create,
    vgExtractNodes,
    vgExtractTracks,
    reorderTracksForLayout,
    getBandData,
  } = module;

  const vgJson = JSON.parse(readFileSync(inputFile, "utf8"));

  const segments = vgExtractNodes(vgJson);
  const strands = reorderTracksForLayout(vgExtractTracks(vgJson, 0, 1));
  // DEBUGGING — the fork logs its own progress to stderr; this is the line the
  // CLI has always printed alongside it.
  console.error("tracks[0].name:", strands[0].name, "length:", strands[0].sequence.length);

  create({
    svgID: "#mysvg",
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

  // Fix SVG dimensions to fit full graph. The numbers come from the band data
  // rather than being recomputed here: the document and the band data have to
  // agree about how big the picture is, and the only way to guarantee that is
  // for there to be one of them.
  const { width, height, viewBox } = bandData.document;
  const svgElement = dom.window.document.getElementById("mysvg");
  svgElement.setAttribute("viewBox", viewBox);
  svgElement.setAttribute("width", width);
  svgElement.setAttribute("height", height);
  svgElement.setAttribute("xmlns", "http://www.w3.org/2000/svg");

  return { document: svgElement.outerHTML, bandData };
}
