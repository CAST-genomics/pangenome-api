// The order the layout arranges strands in, and the invariant that order carries.
//
// `reorderTracksForLayout` decides which strand becomes the **pivot strand**
// (CONTEXT.md) — `createTubeMap` straightens `tracks[0]` and orients everything
// else against it — so this function decides the arrangement of every picture
// /seqtubemap returns. Before this file existed it was a one-line sort by
// sequence length whose comment claimed three properties it did not implement:
// GRCh38 landed first only when it happened to tie for longest and a stable sort
// happened to keep it there, and CHM13 landed at index 455 of 464.
//
// It also renumbers the strands, and that renumbering is a cross-repo contract:
// the ids reach `pgb` as the document's `trackID`, and `pgb` rejects a document
// whose ids are not dense. The last test here is the one that fails on this side
// rather than in the other repository.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { assertDenseStrandIds } from "../../seqtubemap/band-data.mjs";
import { installLayoutConfig } from "../../seqtubemap/layout-config.mjs";
import { inputPath, realCases } from "./real-cases.mjs";

/**
 * The layout, loaded the way `render.mjs` loads it: config first, then the
 * module. There is no window any more — #22 took the browser emulation out — but
 * `tubemap.js` still reads its config at import time, so the order stands.
 */
async function layout() {
  installLayoutConfig();
  return import("../../seqtubemap/tubemap.js");
}

/** Every committed real subgraph, as the strands the layout would be handed. */
async function realSubgraphs() {
  const { vgExtractTracks } = await layout();
  // `realCases` rather than everything in the directory: a fixture now carries
  // several `.json` files — the subgraph and its PCLAI colour scheme — and a glob
  // that catches the scheme feeds the layout something that is not a subgraph.
  // That list is where a sixth subgraph gets added, and every test over the real
  // fixtures picks it up from there.
  return realCases.map((name) => ({
    name: name.replace(/^subgraph_|_v2_with_walk$/g, ""),
    strands: vgExtractTracks(JSON.parse(readFileSync(inputPath(name), "utf8")), 0, 1),
  }));
}

/** The `sample#haplotype#contig` triple, which is the whole of a strand's identity. */
function identity(name) {
  return name.split("#").slice(0, 3).join("#").split("[")[0];
}

/** One strand per walk, in the shape the reorder reads. */
function strandsNamed(...names) {
  return names.map((name, index) => ({ id: index, name, sequence: new Array(name.length).fill("1") }));
}

test("GRCh38 is the pivot strand, whatever order vg emitted", async () => {
  const { reorderTracksForLayout } = await layout();
  for (const { name, strands } of await realSubgraphs()) {
    const ordered = reorderTracksForLayout(strands);
    assert.ok(ordered[0].name.startsWith("GRCh38#"), `${name} pivots on ${ordered[0].name}`);
  }
});

test("GRCh38 pivots even when it is not the longest strand", async () => {
  // The regression the old sort could not survive: length alone made the pivot a
  // matter of which strand vg wrote first among the equal-longest, and a shorter
  // GRCh38 lost outright.
  const { reorderTracksForLayout } = await layout();
  const ordered = reorderTracksForLayout(
    strandsNamed("HG00097#1#CM094064.1#0", "NA21309#2#CM092102.1#0", "GRCh38#0#chr8"),
  );
  assert.equal(ordered[0].name, "GRCh38#0#chr8");
  assert.deepEqual(
    ordered.slice(1).map((strand) => strand.name),
    ["HG00097#1#CM094064.1#0", "NA21309#2#CM092102.1#0"],
  );
});

test("CHM13's walks follow GRCh38's, both grouped rather than interleaved", async () => {
  const { reorderTracksForLayout } = await layout();
  for (const { name, strands } of await realSubgraphs()) {
    const ordered = reorderTracksForLayout(strands).map((strand) => identity(strand.name));
    const reference = ordered.filter((id) => id.startsWith("GRCh38#") || id.startsWith("CHM13#"));
    // The references occupy the front of the list, GRCh38's walks then CHM13's.
    assert.deepEqual(ordered.slice(0, reference.length), reference, `${name} interleaves the references`);
    const firstChm13 = reference.findIndex((id) => id.startsWith("CHM13#"));
    assert.ok(firstChm13 > 0, `${name} has no CHM13 after GRCh38`);
    assert.ok(
      reference.slice(0, firstChm13).every((id) => id.startsWith("GRCh38#")),
      `${name} puts CHM13 before a GRCh38 walk`,
    );
  }
});

test("every walk of one strand sits with the rest of that strand", async () => {
  // A haplotype fragmented across the region arrives as several W lines — 1,201
  // walks for 464 strands in the 4.2 kb fixture. They lay out against each other
  // only if they are adjacent.
  const { reorderTracksForLayout } = await layout();
  for (const { name, strands } of await realSubgraphs()) {
    const ordered = reorderTracksForLayout(strands).map((strand) => identity(strand.name));
    const started = new Set();
    let current = null;
    for (const id of ordered) {
      if (id === current) continue;
      assert.ok(!started.has(id), `${name} resumes ${id} after leaving it`);
      started.add(id);
      current = id;
    }
  }
});

test("the order does not depend on the order vg emitted", async () => {
  // The property the old sort claimed and did not have. Reversing the input is
  // enough to show it: under a stable sort by length alone, every tie flips.
  const { reorderTracksForLayout } = await layout();
  for (const { name, strands } of await realSubgraphs()) {
    const forwards = reorderTracksForLayout([...strands]).map((strand) => strand.name);
    const backwards = reorderTracksForLayout([...strands].reverse()).map((strand) => strand.name);
    assert.deepEqual(backwards, forwards, `${name} lays out differently when vg emits in another order`);
  }
});

test("strand ids are renumbered dense from zero", async () => {
  // `pgb` indexes its tables by trackID and rejects a document whose ids have a
  // gap, so this is the wire contract, not an implementation detail.
  const { reorderTracksForLayout } = await layout();
  for (const { name, strands } of await realSubgraphs()) {
    const ordered = reorderTracksForLayout(strands);
    assert.deepEqual(
      ordered.map((strand) => strand.id),
      ordered.map((_, index) => index),
      `${name} numbers its strands with a gap`,
    );
  }
});

test("band data refuses to report a strand table with a hole in it", () => {
  // `createTubeMap` splices hidden strands out *after* the reorder numbered
  // them. Nothing sets `hidden` in this pipeline today, so the guard is what
  // makes a future one fail here rather than in `pgb`.
  assert.doesNotThrow(() => assertDenseStrandIds([{ id: 0 }, { id: 1 }, { id: 2 }]));
  // A recoloured strand contributes a second row, so it is the set of ids that
  // must be dense and not the row count.
  assert.doesNotThrow(() => assertDenseStrandIds([{ id: 0 }, { id: 0 }, { id: 1 }]));
  assert.throws(
    () => assertDenseStrandIds([{ id: 0 }, { id: 2 }]),
    /must run from 0 upward with no gaps: 2 strands, numbered up to 2, with 1 missing/,
  );
});
