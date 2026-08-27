// Finds the scale at which create() blows the heap.
import { execFileSync } from "child_process";
import { writeFileSync, statSync, mkdirSync } from "fs";
import { generate } from "./gen-vg-json.mjs";
mkdirSync("perf/fixtures/out", { recursive: true });

const COMBOS = [[2000,10],[2000,45],[2000,90],[5000,10],[5000,45],[5000,90],[10000,10],[10000,45]];
console.log(["spine","haps","inMB","result","createMs","svgMB","elems","rssMB"].map(s=>s.padStart(9)).join(" "));
console.log("-".repeat(80));
for (const [spineNodes, haplotypes] of COMBOS) {
  const p = "perf/fixtures/cliff.json";
  writeFileSync(p, JSON.stringify(generate({ spineNodes, haplotypes, bubbleRate: 0.4, seqLen: 48, seed: 7 })));
  const inMB = (statSync(p).size / 1048576).toFixed(1);
  let row;
  try {
    const out = execFileSync("node", ["perf/stage-timer.mjs", p, "perf/fixtures/out/cliff.svg", "0", "300000", "compressed"],
      { encoding: "utf8", maxBuffer: 1 << 28, stdio: ["ignore", "pipe", "pipe"] });
    const lines = out.trim().split("\n").filter(Boolean);
    const r = JSON.parse(lines[lines.length - 1]);
    row = ["ok", r.stages["render:create()"].toFixed(0), (r.output.svgBytes/1048576).toFixed(2), r.output.elements, r.peakRssMb];
  } catch (e) {
    const isOom = /heap out of memory|Ineffective mark-compacts/.test((e.stderr||"") + (e.message||""));
    row = [isOom ? "OOM" : "FAIL", "-", "-", "-", "-"];
  }
  console.log([spineNodes, haplotypes, inMB, ...row].map(s=>String(s).padStart(9)).join(" "));
}
