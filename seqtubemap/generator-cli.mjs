// The command line both generators take.
//
// `/seqtubemap` spawns one of two processes — `generate-svg.mjs` for the
// document, `generate-bands.mjs` for the band payload — and they differ only in
// which sink they write. The arguments are the same six, in the same order,
// because they are the same render: the endpoint builds one command line for
// both (`_render_seq_tube_map`, main.py), so the two have to agree on it, and
// agreeing by construction beats agreeing by inspection.
import { renderTubeMap } from "./render.mjs";

/**
 * Run one generator: parse `process.argv`, render, and hand the caller the
 * result to write.
 *
 * @param {string} usage  the generator's own usage line, for a bad invocation
 * @returns {{outputFile: string, render: {bandData: object, document: string}}}
 *   The render is handed over whole rather than spread, because its `document`
 *   is built on first access — spreading it would build one for the generator
 *   that does not want it.
 */
export async function runGenerator(usage) {
  if (process.argv.length < 7 || process.argv.length > 8) {
    console.error(`Error: 5 or 6 arguments required, got ${process.argv.length - 2}`);
    console.error(usage);
    process.exit(1);
  }

  const inputFile = process.argv[2];
  const outputFile = process.argv[3];
  const start = parseInt(process.argv[4]);
  const end = parseInt(process.argv[5]);
  const nodeWidthOption = process.argv[6];
  const pclaiColorSchemeArg = process.argv[7]; // optional

  let pclaiColorScheme = null;
  if (pclaiColorSchemeArg !== undefined) {
    pclaiColorScheme = JSON.parse(pclaiColorSchemeArg);
  }

  const render = await renderTubeMap({
    inputFile,
    start,
    end,
    nodeWidthOption,
    pclaiColorScheme,
  });

  return { outputFile, render };
}
