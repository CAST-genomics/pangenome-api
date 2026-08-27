// Runs ONE tube map render, mirroring seqtubemap/generate-svg.mjs stage for stage,
// but timing each stage and measuring the output. Emits a single JSON line on stdout.
//
// Runs as its own process on purpose: tubemap.js keeps module-level layout state,
// so a fresh process per render is both the only way to get clean numbers and
// exactly what production does (one `node` subprocess per API request).
//
// Usage: node perf/stage-timer.mjs <input.json> <output.svg> <start> <end> <nodeWidthOption>
import { readFileSync, writeFileSync } from "fs";

const t = [];
let last = performance.now();
function mark(name) {
  const now = performance.now();
  t.push([name, +(now - last).toFixed(2)]);
  // Progress to stderr as we go, so a crash still tells us which stage died.
  process.stderr.write(
    `    [stage] ${name} ${(now - last).toFixed(1)}ms rss=${(process.memoryUsage().rss / 1048576).toFixed(0)}MB\n`
  );
  last = now;
}

const processStart = performance.now();
const [inputFile, outputFile, start, end, nodeWidthOption] = process.argv.slice(2);

const { JSDOM } = await import("jsdom");
const { createCanvas } = await import("canvas");
mark("import:jsdom+canvas");

globalThis["__sequence_tube_map_config"] = {
  defaultHaplotypeColorPalette: { mainPalette: "reds", auxPalette: "blues" },
  defaultReadColorPalette: { mainPalette: "reds", auxPalette: "blues" },
  defaultGraphColorPalette: { mainPalette: "reds", auxPalette: "blues" },
  nodeIntervalThreshold: 150,
  coloredNodes: [], DATA_SOURCES: [], BACKEND_URL: "",
};

const dom = new JSDOM(`<!DOCTYPE html><body><svg id="mysvg"></svg></body>`, {
  resources: "usable",
  pretendToBeVisual: true,
});
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const canvas = createCanvas(200, 200);
const ctx = canvas.getContext("2d");
ctx.font = '14px "Courier New"';
dom.window.SVGElement.prototype.getComputedTextLength = function () {
  return ctx.measureText(this.textContent).width;
};
mark("jsdom:construct-dom");

const { create, vgExtractNodes, vgExtractTracks, getImageCoordinates } =
  await import("../seqtubemap/tubemap.js");
mark("import:tubemap.js");

const raw = readFileSync(inputFile, "utf8");
mark("io:read-input");

const vgJson = JSON.parse(raw);
mark("parse:JSON.parse");

const nodes = vgExtractNodes(vgJson);
mark("convert:vgExtractNodes");

const tracks = vgExtractTracks(vgJson, 0, 1);
mark("convert:vgExtractTracks");

create({
  svgID: "#mysvg",
  nodes, tracks, reads: null,
  region: [0, Number(end) - Number(start) - 1],
  hideLegend: true,
  nodeWidthOption,
});
mark("render:create()");

const { maxXCoordinate, maxYCoordinate, minYCoordinate } = getImageCoordinates();
const svgElement = dom.window.document.getElementById("mysvg");
const width = maxXCoordinate + 50;
const height = maxYCoordinate - minYCoordinate + 50;
svgElement.setAttribute("viewBox", `0 ${minYCoordinate - 20} ${width} ${height}`);
svgElement.setAttribute("width", width);
svgElement.setAttribute("height", height);
svgElement.setAttribute("xmlns", "http://www.w3.org/2000/svg");
mark("render:fix-dimensions");

const svg = svgElement.outerHTML;
mark("serialize:outerHTML");

writeFileSync(outputFile, svg, "utf8");
mark("io:write-svg");

// --- output shape: the "bloated data" half of the symptom ---
const tagCounts = {};
for (const m of svg.matchAll(/<([a-zA-Z][a-zA-Z0-9]*)/g)) {
  tagCounts[m[1]] = (tagCounts[m[1]] || 0) + 1;
}
let dAttrChars = 0;
for (const m of svg.matchAll(/\sd="([^"]*)"/g)) dAttrChars += m[1].length;
let transformChars = 0;
for (const m of svg.matchAll(/\stransform="([^"]*)"/g)) transformChars += m[1].length;

const totalRefBases = vgJson.node.reduce((a, n) => a + n.sequence.length, 0);

console.log(JSON.stringify({
  input: {
    bytes: Buffer.byteLength(raw),
    nodes: vgJson.node.length,
    paths: vgJson.path.length,
    mappings: vgJson.path.reduce((a, p) => a + p.mapping.length, 0),
    bases: totalRefBases,
  },
  output: {
    svgBytes: Buffer.byteLength(svg),
    elements: Object.values(tagCounts).reduce((a, b) => a + b, 0),
    tagCounts,
    dAttrChars,
    transformChars,
    widthPx: width,
    heightPx: height,
  },
  stages: Object.fromEntries(t),
  totalMs: +(performance.now() - processStart).toFixed(2),
  peakRssMb: +(process.memoryUsage().rss / 1048576).toFixed(1),
}));
