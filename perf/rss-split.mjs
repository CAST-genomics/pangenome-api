// Answers one question the stage timer cannot: inside `render:create()`, how much of the
// memory is tubemap.js's LAYOUT, and how much is the jsdom DOM it builds?
//
// That split decides whether a wire format that skips the DOM raises the OOM ceiling
// (DOM-dominated) or only saves bytes and time (layout-dominated).
//
// Method: mark heapUsed at each boundary, forcing a full GC before each mark so the
// number is RETAINED memory rather than garbage-in-flight. Then tear the DOM down and
// GC again -- what is released is what the DOM was holding.
//
// MUST run with --expose-gc, e.g.
//   node --expose-gc --max-old-space-size=8192 perf/rss-split.mjs <input.json> <start> <end> <widthOption>
import { readFileSync } from "fs";

if (typeof globalThis.gc !== "function") {
  console.error("rss-split needs --expose-gc; retained numbers are meaningless without it.");
  process.exit(2);
}

const marks = [];
function mark(name) {
  globalThis.gc(); globalThis.gc();
  const m = process.memoryUsage();
  marks.push({
    name,
    heapMb: +(m.heapUsed / 1048576).toFixed(1),
    rssMb: +(m.rss / 1048576).toFixed(1),
    externalMb: +(m.external / 1048576).toFixed(1),
  });
  const last = marks[marks.length - 1];
  process.stderr.write(`    [rss] ${name.padEnd(24)} heap=${last.heapMb}MB rss=${last.rssMb}MB\n`);
}

const [inputFile, start, end, nodeWidthOption] = process.argv.slice(2);

const { JSDOM } = await import("jsdom");
const { createCanvas } = await import("canvas");

globalThis["__sequence_tube_map_config"] = {
  defaultHaplotypeColorPalette: { mainPalette: "reds", auxPalette: "blues" },
  defaultReadColorPalette: { mainPalette: "reds", auxPalette: "blues" },
  defaultGraphColorPalette: { mainPalette: "reds", auxPalette: "blues" },
  nodeIntervalThreshold: 150,
  coloredNodes: [], DATA_SOURCES: [], BACKEND_URL: "",
};

let dom = new JSDOM(`<!DOCTYPE html><body><svg id="mysvg"></svg></body>`, {
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

const { create, vgExtractNodes, vgExtractTracks, getImageCoordinates } =
  await import("../seqtubemap/tubemap.js");

mark("A:booted");

let raw = readFileSync(inputFile, "utf8");
let vgJson = JSON.parse(raw);
const inputBytes = Buffer.byteLength(raw);
raw = null;
mark("B:input-parsed");

let nodes = vgExtractNodes(vgJson);
let tracks = vgExtractTracks(vgJson, 0, 1);
const trackCount = tracks.length;
const nodeCount = nodes.length;
vgJson = null;
mark("C:vg-extracted");

create({
  svgID: "#mysvg",
  nodes, tracks, reads: null,
  region: [0, Number(end) - Number(start) - 1],
  hideLegend: true,
  nodeWidthOption,
});
nodes = null; tracks = null;
mark("D:after-create");

const { maxXCoordinate, maxYCoordinate, minYCoordinate } = getImageCoordinates();
const svgElement = dom.window.document.getElementById("mysvg");
svgElement.setAttribute("viewBox", `0 ${minYCoordinate - 20} ${maxXCoordinate + 50} ${maxYCoordinate - minYCoordinate + 50}`);
svgElement.setAttribute("width", maxXCoordinate + 50);
svgElement.setAttribute("height", maxYCoordinate - minYCoordinate + 50);
svgElement.setAttribute("xmlns", "http://www.w3.org/2000/svg");

let svg = svgElement.outerHTML;
const svgBytes = Buffer.byteLength(svg);
const elementCount = (svg.match(/<[a-zA-Z]/g) || []).length;
mark("E:after-serialize");

svg = null;
mark("F:svg-string-dropped");

// Tear the DOM down. What is released here is what the DOM was holding; what survives
// is tubemap.js's module-level layout state (plus jsdom's own fixed overhead).
svgElement.textContent = "";
while (dom.window.document.body.firstChild) {
  dom.window.document.body.removeChild(dom.window.document.body.firstChild);
}
mark("G:dom-emptied");

const at = (n) => marks.find((m) => m.name.startsWith(n));
const createTotal = +(at("D").heapMb - at("C").heapMb).toFixed(1);
const domShare = +(at("F").heapMb - at("G").heapMb).toFixed(1);
const layoutShare = +(createTotal - domShare).toFixed(1);

console.log(JSON.stringify({
  input: { file: inputFile, bytes: inputBytes, nodes: nodeCount, tracks: trackCount },
  output: { svgBytes, elementCount },
  marks,
  split: {
    createRetainedMb: createTotal,
    domRetainedMb: domShare,
    layoutRetainedMb: layoutShare,
    domPercentOfCreate: createTotal > 0 ? +((domShare / createTotal) * 100).toFixed(1) : null,
    svgStringMb: +(at("E").heapMb - at("D").heapMb).toFixed(1),
  },
  peakRssMb: +(Math.max(...marks.map((m) => m.rssMb))).toFixed(1),
}, null, 2));
