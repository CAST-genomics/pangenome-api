# pangenome-api

This is the backend API of the Pangenome Browser.

## How to Install
 
 If you are using the AWS instance, you can skip this part and directly navigate to the [How to Use](#how-to-use) section. If you are using the pangenome-api on your own computer instead, please follow the steps below to install. (Note that the gfabase associated to minigraph subgraph extraction are not compatible with the MacOS system)

#### Step 1: Clone the repository

#### Step 2: Install gbz-base and gfabase 
- gbz-base: https://github.com/jltsiren/gbz-base
- gfabase: https://github.com/mlin/gfabase/tree/main 
    - Follow the installation process, and adjust these lines before running `./cargo build --release`
        - **Cargo.toml.in**: change `clap = "3.0.0-beta.2"` to `clap = { version = "3.0.0-beta.2", features = ["derive"] }`
        - **add_mappings.rs, load.rs, main.rs, sub.rs, view.rs**: change `use clap::Clap;` to `use clap::Parser;`, change `#[derive(Clap)]` to `#[derive(Parser)]`
- panct: https://github.com/CAST-genomics/panCT.git

#### Step 3: Install python packages
```
pip install pathlib fastapi 
```

#### Step 4: Download the graph files and store them in a data folder

- [Minigraph-Cactus GRCh38](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.gbz)
- [Minigraph GRCh38](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph/hprc-v1.0-minigraph-grch38.gfa.gz)

We use the database from HPRC which you can find more through [this link](https://github.com/human-pangenomics/hpp_pangenome_resources?tab=readme-ov-file#minigraph-cactus).

#### Step 5: Add the source directories to git config
```
git config --local tools.path [PATH_TO_TOOL_DIR_WITH_PANCT]
git config --local data.path [PATH_TO_DATA_DIR_WITH_MINIGRAPH_AND_MINIGRAPH-CACTUS_GFA]
```

## How to Test

Two suites, one command each. Both are safe to run on a machine without graph
data; anything that genuinely needs a missing dependency skips and says so.

```
pip install -r requirements-test.txt
npm ci                 # the Python endpoint test renders through the Node stage
pytest                 # Python: boots the app and exercises the endpoint seam
npm test               # Node: drives the sequence tube map generator
```

Neither suite needs graph data: the Python tests run against an empty data
directory — the `.walk.gz` derivatives are opened only when a request reads one
— and stub the two natively-compiled layout libraries, while the Node tests
read a committed vg JSON fixture. panCT is used for real if you
have it — from the `tools.path` Step 5 sets, or from `PANCT_PATH` — and stubbed
if you do not. Tests that shell out to `vg` skip when it is not installed, and
so does the `/seqtubemap` endpoint test when `node_modules` is not installed —
it renders a real tube map, which reaches Node through `d3`.

Both suites run in CI on every pull request (`.github/workflows/ci.yml`), where
`vg` and panCT are installed and a skip is turned into a failure.

### Golden tube map documents

`npm test` includes a golden test: committed subgraphs are rendered through the
sequence tube map generator and the output is compared **byte for byte** against
committed documents. It is the safety net for the `/seqtubemap` rework, whose
increments each claim the output is unchanged. One case renders with a PCLAI
colour scheme, the optional argument production passes whenever `minigraphnode`
is set, so strand colour is pinned on that path too.

When a change is *meant* to alter the output, re-baseline deliberately with
`npm run baseline:golden` and review the resulting diff as part of that change.
Details, including why the fixtures are synthetic, are in
[`tests/fixtures/tubemap-golden/README.md`](tests/fixtures/tubemap-golden/README.md).

## The vendored tube map layout

`seqtubemap/` holds a **vendored fork** of the sequence tube map layout, not a
dependency. It was copied from [`vgteam/sequenceTubeMap`](https://github.com/vgteam/sequenceTubeMap)
at commit
[`33b7a7e`](https://github.com/vgteam/sequenceTubeMap/commit/33b7a7e5df9f8052974ef8e6c689a031dac6e2c9)
(2025-08-21 — still the tip of upstream's `master`, and so also the tip when the
copy was taken on 2026-06-10), and is MIT licensed — Copyright (c) 2017
Wolfgang Beyer.

| file | upstream origin | state |
| --- | --- | --- |
| `seqtubemap/tubemap.js` | `src/util/tubemap.js` | forked — trimmed and edited |
| `seqtubemap/common.mjs` | `src/common.mjs` | unmodified |
| `seqtubemap/config-global.mjs` | `src/config-global.mjs` | unmodified |
| `seqtubemap/config-client.js` | `src/config-client.js` | emptied |
| `seqtubemap/generate-svg.mjs` | — | ours |
| `seqtubemap/render.mjs` | — | ours |
| `seqtubemap/band-data.mjs` | — | ours |

**`tubemap.js` is a fork and does not track upstream.** It arrived already
trimmed of upstream's interactive browser half (mouse handlers, zoom, legend
drawing, visibility toggles, the `vg` read extraction entry point — read layout
itself was kept) and adapted to run headless, and
it has been edited since. Increment B of the `/seqtubemap` rework will remove
its DOM sink outright — not yet landed — which puts the divergence beyond
anything a merge could reconcile. Edit it freely; do not attempt to re-sync it
with upstream, and do not read a difference from upstream as a bug.

The decision is
[`docs/adr/0001-additive-band-format.md`](docs/adr/0001-additive-band-format.md)
(its closing "Consequences" bullet is the one about this file), and the
increment that acts on it is
[`docs/perf/seqtubemap-plan.md`](docs/perf/seqtubemap-plan.md). The same
provenance is repeated in the header comment of `seqtubemap/tubemap.js` for
anyone who opens the file directly.

## How to Use:
In the pangenome-api folder, run:
```
fastapi dev main.py
```
You can then open the interactive API doc at http://127.0.0.1:8000/docs.

![fastapi_doc](/image/fastapi_doc.png)

Click "try it out" and input the genome region of interest. Then click "execute" to generate the url.

Alternatively, you can run the API directly from the url ` http://127.0.0.1:8000/json?chrom=chr1&start=25280000&end=25290000&graphtype=minigraph&version=v1&debug_small_graphs=false&minnodelen=5&nodeseglen=20&edgelen=5&nodelenpermb=1000 ` by manually changing the chromosome(eg. chr1, chrX), start location, end location, and graphtype("mc" for minigraph-cactus, or "minigraph").

(Note: the api will likely take a couple of minutes to load when you run the function for the first time. The code will need to indexing the gbz file and gfa file first. This may take around 5 minutes.)

## Example:

```
http://127.0.0.1:8000/json?chrom=chr1&start=25240000&end=25460000&graphtype=minigraph&version=v1&debug_small_graphs=false&minnodelen=5&nodeseglen=20&edgelen=5&nodelenpermb=1000
```
This will return a JSON file with the nodeID, coordinates, assembly list, assembly metadata, etc. of each node, along with the corresponding edges and sequence information. 

![example](/image/example.png)