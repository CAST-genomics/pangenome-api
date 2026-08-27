// GFA (with W lines) -> vg JSON, without the `vg` binary.
//
// The pipeline reaches the Node stage as `vg convert -g` piped through
// `vg view -j` (main.py:396-421). Both binaries are Linux-only in practice, so
// on a developer machine without them the committed `.gfa` fixtures in
// tests/fixtures/seqtubemap/ cannot be driven at all. This produces the same
// JSON from the GFA directly.
//
//   node perf/gfa-to-vg-json.mjs <in.gfa> <out.json> [--names=fragment|bare]
//
// Only the fields tubemap.js actually reads are emitted — `vgExtractNodes`
// (tubemap.js:3760) reads node.id and node.sequence; `vgExtractTracks`
// (tubemap.js:3842) reads path.name, path.freq and
// path.mapping[].position.{node_id,is_reverse}. Nothing else in `vg view -j`'s
// output reaches the layout.
//
// Path naming is read off the golden documents in `pgb`, and they do not agree
// with each other — see "Two conventions" in tests/fixtures/seqtubemap/README.md.
// Two forms are therefore supported:
//
//   --names=fragment  (default)  `sample#hap#contig#N`, N counting fragments of
//                                that triple in file order, except the header's
//                                reference sample (RS:Z), which stays bare.
//                                Matches the most recent golden.
//   --names=bare                 `sample#hap#contig` throughout. Matches the
//                                other four.
import { readFileSync, writeFileSync } from "fs";

export function gfaToVgJson(gfaText, { names = "fragment" } = {}) {
  const node = [];
  const path = [];
  const fragmentCount = new Map();
  let referenceSample = null;

  for (const line of gfaText.split("\n")) {
    if (line === "") continue;
    const f = line.split("\t");

    if (f[0] === "H") {
      for (const tag of f.slice(1)) {
        if (tag.startsWith("RS:Z:")) referenceSample = tag.slice(5).trim();
      }
    } else if (f[0] === "S") {
      node.push({ id: Number(f[1]), sequence: f[2] });
    } else if (f[0] === "W") {
      const [sample, haplotype, contig] = [f[1], f[2], f[3]];
      const triple = `${sample}#${haplotype}#${contig}`;
      const fragment = fragmentCount.get(triple) ?? 0;
      fragmentCount.set(triple, fragment + 1);

      const mapping = [];
      // The walk is a run of >id / <id; '<' is a reverse visit.
      for (const [, orient, id] of f[6].matchAll(/([<>])(\d+)/g)) {
        mapping.push({
          position: { node_id: Number(id), is_reverse: orient === "<" },
        });
      }

      const suffixed = names === "fragment" && sample !== referenceSample;
      path.push({
        name: suffixed ? `${triple}#${fragment}` : triple,
        mapping,
      });
    }
    // L lines carry no information the layout reads: the tracks describe the
    // edges they use. `vg view -j` emits them; tubemap.js never looks.
  }

  return { node, path };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const [inFile, outFile] = args.filter((a) => !a.startsWith("--"));
  const namesArg = args.find((a) => a.startsWith("--names="));
  const names = namesArg ? namesArg.split("=")[1] : "fragment";
  if (!inFile || !outFile || !["fragment", "bare"].includes(names)) {
    console.error(
      "Usage: node perf/gfa-to-vg-json.mjs <in.gfa> <out.json> [--names=fragment|bare]"
    );
    process.exit(1);
  }
  const vg = gfaToVgJson(readFileSync(inFile, "utf8"), { names });
  writeFileSync(outFile, JSON.stringify(vg));
  console.log(`${outFile}: ${vg.node.length} nodes, ${vg.path.length} paths`);
}
