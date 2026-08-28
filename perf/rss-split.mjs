// Answers one question the stage timer cannot: inside `render:create()`, how much of the
// memory is tubemap.js's LAYOUT, and how much is the document it builds?
//
// That split decided whether a wire format that skips the DOM raises the OOM ceiling
// (DOM-dominated) or only saves bytes and time (layout-dominated). It reported
// **94.3% DOM** on `split-400.json` — 1,759.2 MB of jsdom against 106.4 MB of layout,
// at a peak RSS of 2,442.5 MB — and that number is why #22 exists.
//
// Since #22 there is no DOM to weigh, so this no longer reports a share. A share of
// zero would be arithmetic on an absence, not a measurement, and printing it as one
// would be the kind of number this file exists to avoid. What it reports instead is
// what it can observe: how much `create()` retains, what the emitted document costs,
// peak RSS — read against the before-side figures above — and a checked fact, that
// no window and no document global exists on the far side of a render. The
// structural form of that claim, that nothing *can* build one, is
// `tests/node/document-conformance.test.mjs`; the before-and-after table is
// `docs/perf/increment-b.md`.
//
// Method: mark heapUsed at each boundary, forcing a full GC before each mark so the
// number is RETAINED memory rather than garbage-in-flight.
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

const { installLayoutConfig } = await import("../seqtubemap/layout-config.mjs");
installLayoutConfig();

const { emitDocument } = await import("../seqtubemap/emit-document.mjs");
const { create, vgExtractNodes, vgExtractTracks, reorderTracksForLayout, getBandData } =
  await import("../seqtubemap/tubemap.js");

mark("A:booted");

let raw = readFileSync(inputFile, "utf8");
let vgJson = JSON.parse(raw);
const inputBytes = Buffer.byteLength(raw);
raw = null;
mark("B:input-parsed");

// The layout's own vocabulary either side of the call: its `nodes` are this
// codebase's segments and its `tracks` are its strands (CONTEXT.md). The JSON
// below keeps the layout's spelling, because that shape is a recorded format.
let segments = vgExtractNodes(vgJson);
let strands = reorderTracksForLayout(vgExtractTracks(vgJson, 0, 1));
const strandCount = strands.length;
const segmentCount = segments.length;
vgJson = null;
mark("C:vg-extracted");

create({
  nodes: segments, tracks: strands, reads: null,
  region: [0, Number(end) - Number(start) - 1],
  hideLegend: true,
  nodeWidthOption,
});
segments = null; strands = null;
mark("D:after-create");

// The band data is what `create()` retained that the caller wants: the numbers, and
// nothing that only means something inside this process.
const bandData = getBandData();
const bandCount = bandData.bands.length;
mark("E:band-data");

let svg = emitDocument(bandData);
const svgBytes = Buffer.byteLength(svg);
const elementCount = (svg.match(/<[a-zA-Z]/g) || []).length;
mark("F:after-emit");

svg = null;
mark("G:svg-string-dropped");

const at = (n) => marks.find((m) => m.name.startsWith(n));

console.log(JSON.stringify({
  input: { file: inputFile, bytes: inputBytes, nodes: segmentCount, tracks: strandCount },
  output: { svgBytes, elementCount, bands: bandCount },
  marks,
  retained: {
    // All of `create()`, and all of it layout: there is nothing else left in it.
    createMb: +(at("D").heapMb - at("C").heapMb).toFixed(1),
    // From RSS, not heapUsed: the emitted document is one large string, and a
    // full GC either side of it moves more heap than the string occupies.
    documentRssMb: +(at("F").rssMb - at("E").rssMb).toFixed(1),
  },
  // Observed, not assumed. A render that had stood a browser up would have left
  // these behind, as the pre-#22 pipeline did for the life of the process.
  emulatedDocument: {
    windowGlobal: typeof globalThis.window,
    documentGlobal: typeof globalThis.document,
  },
  peakRssMb: +(Math.max(...marks.map((m) => m.rssMb))).toFixed(1),
}, null, 2));
