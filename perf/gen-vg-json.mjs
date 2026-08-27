// Deterministic synthetic vg-JSON generator for tube map perf work.
// Emits the same shape `vg view -j` produces, which is all tubemap.js reads:
//   { node: [{id, sequence}], path: [{name, freq, mapping:[{position:{node_id,is_reverse}}]}] }
//
// Graph shape mimics a pangenome subgraph: a reference spine with bubbles
// hanging off it, and haplotype paths choosing an allele at each bubble.
import { writeFileSync } from "fs";

// mulberry32 — seeded so every run produces byte-identical fixtures.
function rng(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const BASES = "ACGT";
function seq(rand, len) {
  let s = "";
  for (let i = 0; i < len; i += 1) s += BASES[(rand() * 4) | 0];
  return s;
}

export function generate({
  spineNodes = 200,   // nodes along the reference backbone
  haplotypes = 10,    // number of haplotype paths
  bubbleRate = 0.3,   // fraction of spine positions carrying an alternate allele
  altFreq = 0.5,      // P(haplotype takes the alt allele). Real haplotypes mostly
                      // share alleles, so low values reproduce the heavy node
                      // merging seen in real subgraphs; 0.5 is worst-case divergence.
  seqLen = 32,        // mean node sequence length
  seed = 42,
} = {}) {
  const rand = rng(seed);
  const node = [];
  const spine = [];   // [{ref, alt|null}] by position
  let nextId = 1;

  for (let i = 0; i < spineNodes; i += 1) {
    const len = Math.max(1, Math.round(seqLen * (0.5 + rand())));
    const ref = nextId++;
    node.push({ id: ref, sequence: seq(rand, len) });
    let alt = null;
    if (rand() < bubbleRate) {
      alt = nextId++;
      const altLen = Math.max(1, Math.round(seqLen * (0.5 + rand())));
      node.push({ id: alt, sequence: seq(rand, altLen) });
    }
    spine.push({ ref, alt });
  }

  const path = [];
  // Reference path first — always the pure spine, like GRCh38 in a real subgraph.
  path.push({
    name: "GRCh38#0#chr1",
    freq: 1,
    indexOfFirstBase: 0,
    mapping: spine.map((s) => ({ position: { node_id: s.ref, is_reverse: false } })),
  });
  for (let h = 0; h < haplotypes; h += 1) {
    const mapping = [];
    for (const s of spine) {
      const useAlt = s.alt !== null && rand() < altFreq;
      mapping.push({ position: { node_id: useAlt ? s.alt : s.ref, is_reverse: false } });
    }
    path.push({
      name: `HG${String(10000 + h).padStart(5, "0")}#${(h % 2) + 1}#chr1`,
      freq: 1,
      indexOfFirstBase: 0,
      mapping,
    });
  }
  return { node, path };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = Object.fromEntries(
    process.argv.slice(3).map((a) => {
      const [k, v] = a.replace(/^--/, "").split("=");
      return [k, Number(v)];
    })
  );
  const out = process.argv[2];
  writeFileSync(out, JSON.stringify(generate(args)));
  console.log(`wrote ${out}`);
}
