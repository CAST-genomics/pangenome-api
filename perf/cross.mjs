// The real case: MANY tracks AND a growing spine at the same time.
// Earlier sweeps varied one axis with the other held low and looked linear;
// this tests the cross term.
import { execFileSync } from "child_process";
import { writeFileSync, statSync, mkdirSync } from "fs";
import { generate } from "./gen-vg-json.mjs";
mkdirSync("perf/fixtures/out", { recursive: true });

const HAPS = Number(process.env.HAPS ?? 464);
const ALT = Number(process.env.ALT ?? 0.08);   // realistic allele sharing -> heavy merging
const SPINES = (process.env.SPINES ?? "40,100,200,400,800,1600").split(",").map(Number);

console.log(`haps=${HAPS} altFreq=${ALT}`);
console.log(["spine","inMB","create_ms","total_ms","svgMB","elems","rssMB","ms/spine"].map(s=>s.padStart(10)).join(""));
console.log("-".repeat(80));
let prev = null;
for (const spineNodes of SPINES) {
  const p = "perf/fixtures/cross.json";
  writeFileSync(p, JSON.stringify(generate({ spineNodes, haplotypes: HAPS, bubbleRate: 0.4, altFreq: ALT, seqLen: 8, seed: 11 })));
  const inMB = (statSync(p).size / 1048576).toFixed(2);
  try {
    const out = execFileSync("node", ["--max-old-space-size=6144", "perf/stage-timer.mjs", p,
      "perf/fixtures/out/cross.svg", "0", String(spineNodes * 8), "compressed"],
      { encoding: "utf8", maxBuffer: 1 << 28, stdio: ["ignore", "pipe", "pipe"], timeout: 900000 });
    const lines = out.trim().split("\n").filter(Boolean);
    const r = JSON.parse(lines[lines.length - 1]);
    const c = r.stages["render:create()"];
    const growth = prev ? ` (${(c / prev).toFixed(1)}x for 2x input)` : "";
    console.log([spineNodes, inMB, c.toFixed(0), r.totalMs.toFixed(0),
      (r.output.svgBytes/1048576).toFixed(2), r.output.elements, r.peakRssMb,
      (c/spineNodes).toFixed(2)].map(s=>String(s).padStart(10)).join("") + growth);
    prev = c;
  } catch (e) {
    const oom = /heap out of memory|Ineffective mark-compacts/.test((e.stderr||"")+(e.message||""));
    console.log(String(spineNodes).padStart(10) + String(inMB).padStart(10) + (oom ? "   *** OOM (6GB heap) ***" : "   *** FAILED ***"));
    break;
  }
}
