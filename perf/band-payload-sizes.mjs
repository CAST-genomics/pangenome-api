// What the band payload costs against the document, over the five real
// subgraphs. Reproduces the table in `docs/band-format.md`:
//
//     node --max-old-space-size=8192 perf/band-payload-sizes.mjs
//
// Both encodings come out of one render, so the two figures on a row describe
// the same picture rather than two renders that might have differed.
import { encodeBandPayload } from "../seqtubemap/band-payload.mjs";
import { realCases, renderReal, regionOf } from "../tests/node/real-cases.mjs";

const mb = (bytes) => `${(bytes / 1048576).toFixed(2)} MB`;
const rows = [];

for (const name of realCases) {
  const { bandData, document } = await renderReal(name);
  const payload = encodeBandPayload(bandData);
  const headerLength = new DataView(payload.buffer, payload.byteOffset, 4).getUint32(0, true);
  const { start, end } = regionOf(name);
  const sequences = bandData.segments.reduce(
    (total, segment) => total + (segment.sequence?.length ?? 0),
    0,
  );

  rows.push({
    region: name.replace(/^subgraph_/, "").replace(/_v2_with_walk$/, ""),
    span: end - start,
    strands: bandData.strands.length,
    bands: bandData.bands.length,
    segments: bandData.segments.length,
    boxes: Buffer.byteLength(
      JSON.stringify(bandData.segments.map((segment) => segment.box)),
    ),
    // The two things the header spends its bytes on, measured as the JSON they
    // become, so the breakdown in `docs/band-format.md` is reproducible rather
    // than asserted.
    segmentJson: Buffer.byteLength(JSON.stringify(bandData.segments)),
    strandJson: Buffer.byteLength(JSON.stringify(bandData.strands)),
    svg: Buffer.byteLength(document),
    payload: payload.byteLength,
    header: headerLength,
    body: payload.byteLength - 4 - headerLength,
    sequences,
  });
}

for (const row of rows) {
  console.log(
    `${row.region.padEnd(28)} ${String(row.span).padStart(6)} bp  ` +
      `${String(row.strands).padStart(5)} strands ${String(row.bands).padStart(6)} bands  ` +
      `svg ${mb(row.svg).padStart(9)}  payload ${mb(row.payload).padStart(9)}  ` +
      `${(row.svg / row.payload).toFixed(1)}x  ` +
      `[header ${mb(row.header)}: ${row.segments} segment boxes at ${mb(row.segmentJson)} ` +
      `(${mb(row.boxes)} box, ${mb(row.sequences)} sequence), ` +
      `${row.strands}-row strand table at ${mb(row.strandJson)}; body ${mb(row.body)}]`,
  );
}
