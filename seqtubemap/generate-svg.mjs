import { readFileSync, writeFileSync } from "fs";
import { JSDOM } from "jsdom";
import { createCanvas } from "canvas";

if (process.argv.length < 7 || process.argv.length > 8) {
  console.error(`Error: 5 or 6 arguments required, got ${process.argv.length - 2}`);
  console.error(`Usage: node generate-svg.mjs <input.json> <output.svg> <startloc> <endloc> <nodeWidthOption> [pclaiColorSchemeJson]`);
  process.exit(1);
}

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
const { create, vgExtractNodes, vgExtractTracks, getImageCoordinates } = await import("./tubemap.js");

// 4. Load vg JSON
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

const vgJson = JSON.parse(readFileSync(inputFile, "utf8"));

// 5. Convert to TubeMap format
const nodes  = vgExtractNodes(vgJson);
const tracks = vgExtractTracks(vgJson, 0, 1);

// 6. Render
create({
  svgID: "#mysvg",
  nodes: nodes,
  tracks: tracks,
  reads: null,
  region: [0, end-start-1],
  hideLegend: true,
  nodeWidthOption: nodeWidthOption,
  pclaiColorScheme: pclaiColorScheme
});

// 7. Fix SVG dimensions to fit full graph
const { maxXCoordinate, maxYCoordinate, minYCoordinate } = getImageCoordinates();

const svgElement = dom.window.document.getElementById("mysvg");
const width = maxXCoordinate + 50;
const height = maxYCoordinate - minYCoordinate + 50;

svgElement.setAttribute("viewBox", `0 ${minYCoordinate - 20} ${width} ${height}`);
svgElement.setAttribute("width", width);
svgElement.setAttribute("height", height);
svgElement.setAttribute("xmlns", "http://www.w3.org/2000/svg");

writeFileSync(outputFile, svgElement.outerHTML, "utf8");
console.log(`SVG written to ${outputFile}`);