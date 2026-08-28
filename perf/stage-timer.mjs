// Runs ONE tube map render, mirroring seqtubemap/render.mjs stage for stage, but
// timing each stage and measuring the output. Emits a single JSON line on stdout.
//
// The `import:jsdom+canvas` and `jsdom:construct-dom` stages this used to report —
// 437.6 ms and 109.0 ms of the 722 ms fixed floor measured in
// docs/perf/seqtubemap-latency.md §2 — are gone, because #22 deleted what they
// were timing. `serialize:outerHTML` is now `serialize:emit-document`: the same
// bytes, written from the band data rather than walked out of a DOM.
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

const { installLayoutConfig } = await import("../seqtubemap/layout-config.mjs");
installLayoutConfig();

const { emitDocument } = await import("../seqtubemap/emit-document.mjs");
const { create, vgExtractNodes, vgExtractTracks, reorderTracksForLayout, getBandData } =
  await import("../seqtubemap/tubemap.js");
mark("import:tubemap.js");

const raw = readFileSync(inputFile, "utf8");
mark("io:read-input");

const vgJson = JSON.parse(raw);
mark("parse:JSON.parse");

// The layout's own vocabulary either side of the call: its `nodes` are this
// codebase's segments and its `tracks` are its strands (CONTEXT.md).
const segments = vgExtractNodes(vgJson);
mark("convert:vgExtractNodes");

const strands = reorderTracksForLayout(vgExtractTracks(vgJson, 0, 1));
mark("convert:vgExtractTracks");

create({
  nodes: segments, tracks: strands, reads: null,
  region: [0, Number(end) - Number(start) - 1],
  hideLegend: true,
  nodeWidthOption,
});
mark("render:create()");

const bandData = getBandData();
const { width, height } = bandData.document;
mark("render:band-data");

const svg = emitDocument(bandData);
mark("serialize:emit-document");

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
