// The config `tubemap.js` reads at import time, in the one place that says it.
//
// `config-global.mjs` looks the config up in a global and throws if it is not
// there, so nothing may import `tubemap.js` before this has run. That ordering
// is the only sequencing left in standing the layout up — the jsdom window and
// the measuring canvas that used to come between them are gone (#22) — and it is
// why every caller loads `tubemap.js` dynamically.
//
// Four callers need it: `render.mjs`, the two perf harnesses, and the reorder
// test, which imports the layout without rendering. They used to carry a copy
// each, and a copy that drifted would change the picture rather than fail.
export const LAYOUT_CONFIG = {
  defaultHaplotypeColorPalette: { mainPalette: "reds", auxPalette: "blues" },
  defaultReadColorPalette:      { mainPalette: "reds", auxPalette: "blues" },
  defaultGraphColorPalette:     { mainPalette: "reds", auxPalette: "blues" },
  nodeIntervalThreshold: 150,
  coloredNodes: [],
  DATA_SOURCES: [],
  BACKEND_URL: "",
};

const GLOBAL_NAME = "__sequence_tube_map_config";

/**
 * Put the config where `config-global.mjs` will find it.
 *
 * Call this, then `await import("./tubemap.js")`. Idempotent, and it does not
 * overwrite a config somebody else has already installed.
 */
export function installLayoutConfig() {
  globalThis[GLOBAL_NAME] ??= LAYOUT_CONFIG;
  return globalThis[GLOBAL_NAME];
}
