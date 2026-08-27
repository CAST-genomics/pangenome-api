// Sweep orchestrator: builds fixtures, runs perf/stage-timer.mjs in its own process
// for each, and prints a table. Sweeps one axis at a time so you can see WHICH
// dimension of the graph the cost actually scales with.
//
//   node perf/bench.mjs                 # default sweep, all three axes
//   node perf/bench.mjs --axis=spine    # one axis
//   node perf/bench.mjs --input=real.json --start=0 --end=10000
import { execFileSync } from "child_process";
import { writeFileSync, mkdirSync, statSync } from "fs";
import { generate } from "./gen-vg-json.mjs";

const FIX = "perf/fixtures";
const OUT = "perf/fixtures/out";
mkdirSync(OUT, { recursive: true });

const argv = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [k, v] = a.replace(/^--/, "").split("=");
    return [k, v ?? true];
  })
);
const NODE_WIDTH = argv.nodeWidthOption ?? "compressed";

function run(jsonPath, start, end) {
  const svgPath = `${OUT}/${jsonPath.split("/").pop().replace(/\.json$/, "")}.svg`;
  const wall0 = performance.now();
  let stdout;
  try {
    stdout = execFileSync(
      "node",
      ["perf/stage-timer.mjs", jsonPath, svgPath, String(start), String(end), NODE_WIDTH],
      { encoding: "utf8", maxBuffer: 1 << 28, timeout: 600000, stdio: ["ignore", "pipe", "pipe"] }
    );
  } catch (e) {
    return { failed: true, reason: (e.stderr || e.message || "").split("\n").slice(-4).join(" ").slice(0, 160) };
  }
  const wall = performance.now() - wall0;
  const lines = stdout.trim().split("\n").filter(Boolean);
  const rec = JSON.parse(lines[lines.length - 1]);
  rec.wallMs = +wall.toFixed(2);   // includes node process startup, as production pays it
  return rec;
}

function fixture(name, params) {
  const path = `${FIX}/${name}.json`;
  const g = generate(params);
  writeFileSync(path, JSON.stringify(g));
  const bases = g.node.reduce((a, n) => a + n.sequence.length, 0);
  return { path, bases };
}

const BASE = { spineNodes: 200, haplotypes: 10, bubbleRate: 0.3, seqLen: 32, seed: 42 };

const AXES = {
  spine:   { key: "spineNodes", values: [100, 200, 400, 800, 1600, 3200, 6400] },
  haps:    { key: "haplotypes", values: [2, 5, 10, 20, 40, 80] },
  bubbles: { key: "bubbleRate", values: [0.0, 0.1, 0.25, 0.5, 0.75, 1.0] },
};

function fmt(n, w = 9) { return String(n).padStart(w); }
function mb(bytes) { return (bytes / 1048576).toFixed(2); }

function table(title, rows, axisKey) {
  console.log(`\n### ${title}`);
  console.log(
    [axisKey.padEnd(11), "nodes".padStart(7), "mappings".padStart(9), "inMB".padStart(7),
     "wall_ms".padStart(9), "create_ms".padStart(10), "fixed_ms".padStart(9),
     "svgMB".padStart(8), "elems".padStart(8), "bloat_x".padStart(8)].join(" ")
  );
  console.log("-".repeat(100));
  for (const r of rows) {
    if (r.rec.failed) {
      console.log(`${String(r.axisValue).padEnd(11)} ${"FAILED: " + r.rec.reason}`);
      continue;
    }
    const s = r.rec.stages;
    const fixed = s["import:jsdom+canvas"] + s["jsdom:construct-dom"] + s["import:tubemap.js"];
    const bloat = (r.rec.output.svgBytes / r.rec.input.bytes).toFixed(1);
    console.log([
      String(r.axisValue).padEnd(11),
      fmt(r.rec.input.nodes, 7),
      fmt(r.rec.input.mappings, 9),
      fmt(mb(r.rec.input.bytes), 7),
      fmt(r.rec.wallMs.toFixed(0), 9),
      fmt(s["render:create()"].toFixed(0), 10),
      fmt(fixed.toFixed(0), 9),
      fmt(mb(r.rec.output.svgBytes), 8),
      fmt(r.rec.output.elements, 8),
      fmt(bloat + "x", 8),
    ].join(" "));
  }
}

if (argv.input) {
  const start = Number(argv.start ?? 0);
  const end = Number(argv.end ?? 10000);
  console.log(`Real input: ${argv.input} (${mb(statSync(argv.input).size)} MB)`);
  const rec = run(argv.input, start, end);
  console.log(JSON.stringify(rec, null, 2));
} else {
  const which = argv.axis ? [argv.axis] : Object.keys(AXES);
  for (const axisName of which) {
    const axis = AXES[axisName];
    if (!axis) { console.error(`unknown axis: ${axisName}`); process.exit(1); }
    const rows = [];
    for (const v of axis.values) {
      const params = { ...BASE, [axis.key]: v };
      const { path, bases } = fixture(`${axisName}-${v}`, params);
      process.stderr.write(`  running ${axisName}=${v} ... `);
      const rec = run(path, 0, bases);
      process.stderr.write(rec.failed ? "FAILED\n" : `${rec.wallMs.toFixed(0)}ms\n`);
      rows.push({ axisValue: v, rec });
    }
    table(`axis: ${axisName} (others fixed at spine=${BASE.spineNodes}, haps=${BASE.haplotypes}, bubbleRate=${BASE.bubbleRate})`, rows, axis.key);
  }
}
