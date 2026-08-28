// Recover the PCLAI colour scheme a tube map document was rendered with.
//
// The scheme is the third input to a render — the subgraph and the region being
// the other two — and unlike them it is not a file anyone here can produce: the
// endpoint builds it from a minigraph walks file on the server
// (`GetPclaiColorScheme`, main.py:673). What it can be read back out of is a
// document that was rendered with it, because the generator writes every entry
// onto the elements it draws: the colour as `color`, and the placement as
// `pclaiX`, `pclaiY` and `pclaiScore`.
//
//     node perf/pclai-from-document.mjs <document.svg> <out.pclai.json>
//
// The output is keyed by the `sample#haplotype#contig` triple, which is what the
// layout looks a strand up by (`getPclaiEntry`, tubemap.js:2563), and is shaped
// exactly as `main.py` builds it: `[[r, g, b], [x, y], score]`, with the score a
// string because that is what the endpoint puts there.
//
// **A strand with no placement is omitted, not written as grey.** The endpoint
// distinguishes two cases that the document cannot: an entry whose `x_coord` is
// "." gets an explicit grey no-coordinate row (main.py:684), and a strand the
// walks file never mentions gets no row at all and falls back to the same light
// grey (tubemap.js:2509). Both draw identically, so a document is no evidence
// about which one produced it. Omitting is the reading that claims less; it
// renders the same picture either way, which is the property the baselines rely
// on.
import { readFileSync, writeFileSync } from "node:fs";

import { strandIdentity } from "../seqtubemap/strand.mjs";

// `color` rather than the `style` fill: both carry the strand's colour, and this
// one is a bare `rgb(...)` with nothing else in the attribute.
const ELEMENT =
  /trackName="([^"]*)"[^>]*?color="rgb\((\d+), (\d+), (\d+)\)" pclaiX="([^"]*)" pclaiY="([^"]*)" pclaiScore="([^"]*)"/g;

/**
 * The scheme a document was rendered with, as a value.
 *
 * Every element of a strand carries the same entry, so the same key is reached
 * many times; disagreement between two of them would mean the document was not
 * rendered from one scheme, and is worth failing on rather than picking a winner.
 */
export function pclaiSchemeFromDocument(svg) {
  const scheme = {};
  for (const [, name, r, g, b, x, y, score] of svg.matchAll(ELEMENT)) {
    if (x === "None") continue; // no placement — see the note above
    const key = strandIdentity(name);
    const entry = [[Number(r), Number(g), Number(b)], [Number(x), Number(y)], score];
    const seen = scheme[key];
    if (seen && JSON.stringify(seen) !== JSON.stringify(entry)) {
      throw new Error(`${key} carries two different PCLAI entries in this document`);
    }
    scheme[key] = entry;
  }
  return scheme;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [document, out] = process.argv.slice(2);
  if (!document || !out) {
    console.error("usage: node perf/pclai-from-document.mjs <document.svg> <out.pclai.json>");
    process.exit(2);
  }
  const scheme = pclaiSchemeFromDocument(readFileSync(document, "utf8"));
  const keys = Object.keys(scheme).sort();
  // Sorted and one entry per line: the file is committed, so it has to diff.
  const body = keys.map((key) => `  ${JSON.stringify(key)}: ${JSON.stringify(scheme[key])}`);
  writeFileSync(out, `{\n${body.join(",\n")}\n}\n`, "utf8");
  console.log(`${out}: ${keys.length} placed strands`);
}
