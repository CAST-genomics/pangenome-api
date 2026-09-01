# Driving `/seqtubemap` locally — the harness behind #22's before-and-after

On 2026-08-28, immediately after [#22](https://github.com/CAST-genomics/PangenomeAPI/issues/22)
merged, the endpoint was exercised for real on a developer machine: two isolated API
instances, one running the code from before the change and one from after, serving the same
five regions over HTTP so the difference could be measured on the wire rather than inferred
from a unit test.

This document records exactly how that was done, because the setup is not obvious, it is
reproducible, and one part of it is a stand-in that materially limits what the results prove.

> **Still reproducible, with one change.** The §5 recipe was re-read against `main` on
> 2026-09-01 and still works. What moved since is the cache check in §3 — see the note there.
> `main.py` line numbers have shifted throughout, so this document names functions rather than
> lines wherever it can.

**Nothing here touched production.** `release` — the branch the server follows
([`releasing.md`](../releasing.md)) — was not read, written, or deployed to. Both instances
bound to `127.0.0.1` on ports **8100** and **8101**; production is `:8000` on
`pangenome-api.ucsd.edu`. Everything the harness created lives in a session scratchpad
outside the repository, except one gitignored `cache/` directory that was deleted afterwards.

The results are in [`increment-b.md`](./increment-b.md); this is the method.

- Designed version: [`local-endpoint-harness.html`](./local-endpoint-harness.html)

---

## 1. Why this needs a harness at all

`/seqtubemap` is not a pure function. Serving one request touches four things a developer
machine does not have:

| what the endpoint wants | why it is missing here |
| --- | --- |
| the multi-gigabyte HPRC v2 `.gbz` graph | not distributable; lives on the server |
| the `vg` binary, twice (`ConvertGfaToVg`, `ConvertVgToJson`) | vgteam ship a **Linux** static build; this is darwin/arm64 |
| `panCT`, and `tools.path` / `data.path` in git config | developer setup step, unset in this checkout |
| `adaptagrams` and `ogdf-python` | compiled inside the Docker image (see the `Dockerfile`), not on the host |

Docker would supply all four at once, and `docker-compose.yml` exists for exactly that. This
machine has no Docker daemon, so each one was supplied separately.

The Python test suite already solves three of these — `tests/python/conftest.py` stubs the
native libraries, stubs or finds panCT, and supplies the git config through git's environment
variables. What it *cannot* solve is `vg`, which is why
`tests/python/test_seqtubemap_endpoint.py` skips four tests on a machine without it. Those are
the very tests that render a real tube map. So on this machine, before this harness, **no part
of `/seqtubemap` had ever run end to end** — the coverage came from CI, where `vg` is
installed, and from the Node-level tests below HTTP.

---

## 2. What "isolated instance" means, precisely

Two `uvicorn` processes, each serving `main:app` out of a different checkout:

| | after | before |
| --- | --- | --- |
| port | `127.0.0.1:8100` | `127.0.0.1:8101` |
| working directory | the repository | a `git worktree` at `399db1e` |
| code | post-#22 (`e8e5bfe`) | pre-#22, with `jsdom` and `canvas` reinstalled |
| `node_modules` | 2 packages | 5 packages |
| `./cache/seqtubemap/mc/` | its own, seeded | its own, seeded |

They shared the harness pieces — one virtualenv, one panCT checkout, one stub directory, one
empty data directory, one `vg` stand-in — deliberately: anything shared is a constant across
the comparison and therefore cannot contribute to the difference.

A `git worktree` is what makes the "before" side honest. It is a second working directory
attached to the same repository, checked out at an arbitrary commit, with its own untracked
files — so `399db1e` gets its own `node_modules` containing the browser emulation, without
disturbing the main checkout or requiring a stash-and-reinstall dance between measurements.
Both servers were up at the same time.

---

## 3. The trick that removes the need for graph data

This is the part worth understanding, because it is not a test hook — it is a **production
code path**, used as intended.

The endpoint's cache check reads:

```python
subgraph_cached = subgraph_has_walks(preprocess_gfa_subgraph_w_walk)

with stage_timing(stages, "subgraph_extract"):
    if not subgraph_cached:
        ...SubgraphMC(...); GenerateWalksMC(...)
```

If the extracted subgraph is already on disk, the endpoint skips extraction entirely — no
`.gbz`, no `gfabase`, no `gbz-base`, no tabix walk lookups. That branch exists so a repeated
region is fast. It also means that **pre-placing a subgraph file is enough to make the rest of
the pipeline run**.

> **Updated 2026-09-01.** At the time of this harness the check was
> `preprocess_gfa_subgraph_w_walk.exists()`. PR
> [#60](https://github.com/CAST-genomics/PangenomeAPI/pull/60) tightened it to
> `subgraph_has_walks()` — a cache hit now means a subgraph with at least one `W` line, so a
> half-written extraction can never be served as finished. **The trick still works**, because
> the five committed fixtures are complete subgraphs with their walks in them; but a
> hand-made or truncated `.gfa` dropped into `cache/` will now be re-extracted rather than
> served, which on a machine with no graph data means the request fails.

The path it looks for is built from the query parameters:

```
./cache/seqtubemap/mc/subgraph_{chrom}_{start}_{end}_{version}_with_walk.gfa
```

And the five fixtures in [`tests/fixtures/seqtubemap/`](../../tests/fixtures/seqtubemap/) were
copied out of the production server's own cache directory, under the server's own filenames —
`subgraph_chr8_78771162_78771252_v2_with_walk.gfa` and four others. They drop into that path
without being renamed, and the region in the filename *is* the region to request.

So:

```sh
mkdir -p cache/seqtubemap/mc
cp tests/fixtures/seqtubemap/*.gfa cache/seqtubemap/mc/
```

turns five committed fixtures into five servable regions. The `cache/` directory is gitignored
(`.gitignore:26`).

The second half of the same trick is [#19](https://github.com/CAST-genomics/PangenomeAPI/issues/19):
the `.walk.gz` derivatives are opened by `WalkDerivative` the first time something reads one
(`main.py:85`), rather than at import. (Since PR
[#60](https://github.com/CAST-genomics/PangenomeAPI/pull/60) that open is per thread rather
than per process, which changes nothing for this harness.) A request with no `minigraphnode` reads none, so
`data.path` can point at an **empty directory** and the app still boots and serves.

---

## 4. The five stand-ins

### 4.1 `tools.path` and `data.path`, without touching your git config

`main.py` shells out to `git config --get` for both, at import. Rather than writing them into
`.git/config` — a mutation of the developer's checkout that would outlive the experiment —
they were supplied through git's environment configuration, the same mechanism `conftest.py`
uses:

```sh
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=tools.path  GIT_CONFIG_VALUE_0="$S/tools"
export GIT_CONFIG_KEY_1=data.path   GIT_CONFIG_VALUE_1="$S/data"
```

Any `git config --get` in a child process sees these; nothing on disk changes.

### 4.2 panCT — real, not stubbed

```sh
git clone https://github.com/CAST-genomics/panCT.git "$S/tools/panCT"
git -C "$S/tools/panCT" checkout 03c406b
```

`03c406b` is the commit CI pins (`.github/workflows/ci.yml`, `PANCT_COMMIT`). `main.py` does
`sys.path.append(tool_path)` and imports `Region` and `getLogger` from it. Using the real thing
rather than `conftest`'s placeholder means the logging in the `[stage-timing]` line below is
panCT's own.

### 4.3 `adaptagrams` and `ogdf_python` — stubbed, and this has a cost

Two files on `PYTHONPATH`:

```python
# ogdf_python.py
import types
ogdf = types.SimpleNamespace()
def cppinclude(*a, **k):
    return None
```

```python
# adaptagrams.py — stand-in: the real one is compiled in the Docker image
```

`main.py` imports `bandage_graph` and `adaptagrams_converter` at module scope, which import
these. They are the **3D graph layout** libraries, used by `/json`, and nothing in the
`/seqtubemap` path calls them.

**The cost:** in these instances `/json` was non-functional. That endpoint was not exercised
and no claim here covers it.

### 4.4 The `vg` stand-in — the one that limits the conclusions

`ConvertGfaToVg` and `ConvertVgToJson` each run `subprocess.run` against
`vg`, unconditionally — there is no "skip if the output exists" branch to exploit, the way
there is for extraction. Without a `vg` on `PATH` the request cannot proceed past `gfa_to_vg`.

So a shell script named `vg` was put first on `PATH`, implementing exactly the two invocations
`main.py` makes and nothing else:

```bash
#!/bin/bash
set -euo pipefail
REPO="${VG_SHIM_REPO:?VG_SHIM_REPO must point at the checkout to use}"
case "${1:-}" in
  convert)   # vg convert -g <in.gfa>  -> stdout   (ConvertGfaToVg)
    printf 'GFA_SHIM\t%s\n' "$(cd "$(dirname "$3")" && pwd)/$(basename "$3")"
    ;;
  view)      # vg view -j <in.vg>      -> stdout   (ConvertVgToJson)
    gfa=$(awk -F'\t' '/^GFA_SHIM/{print $2; exit}' "$3")
    out=$(mktemp -t vgshim); trap 'rm -f "$out"' EXIT
    node "$REPO/perf/gfa-to-vg-json.mjs" "$gfa" "$out" >/dev/null 2>&1
    cat "$out"
    ;;
  *) echo "vg shim: unsupported invocation: $*" >&2; exit 64 ;;
esac
```

The `.vg` protobuf is a private intermediate — nothing but `vg view` ever reads it, and the
endpoint deletes it afterwards — so `convert` does not need to produce one. It writes a marker
line naming the GFA it was given, and `view` reads that marker and converts the GFA directly,
using [`perf/gfa-to-vg-json.mjs`](../../perf/gfa-to-vg-json.mjs), this repository's own
GFA → vg-JSON derivation.

**It was verified before being trusted.** Run over the 90 bp fixture, the shim's output is
`JSON.stringify`-identical to the committed `subgraph_chr8_78771162_78771252_v2_with_walk.json`
— which is the file the Node-level tests and the band-data baselines are built from. The Node
stage therefore received, over HTTP, exactly the input it receives in `npm test`.

**What it is not.** It is not `vg`. `tests/fixtures/seqtubemap/README.md` is explicit that the
committed `.json` files "were not produced by `vg`", and the roadmap records a known
divergence: real `vg view -j` appends a subrange to a path covering part of a contig
(`CHM13#0#chr8#0[9659985-9661740]`) and this shim never does. See §7 for what that costs.

The stand-in deliberately lives **outside the repository**, in a scratchpad. A file named `vg`
that silently is not `vg` is a hazard, and it should not be findable by anyone who has not read
this section.

### 4.5 The virtualenv

`python3 -m venv`, then `pip install -r requirements-test.txt` plus `uvicorn`. Resolved to
fastapi 0.141.1, starlette 1.6.0, uvicorn 0.52.4, pysam 0.24.0, numpy 2.5.2, on Python 3.13.5.
Node was the system v26.7.0. Host: macOS 26.5.2, arm64.

The repo's own `docker-compose.yml` runs `fastapi dev`; `uvicorn main:app` was used instead
because it is one dependency rather than the `fastapi[standard]` bundle, and the app object is
the same either way.

---

## 5. Reproducing it

Set `S` to a scratch directory outside the repo, and `REPO` to the checkout.

```sh
S=/tmp/seqtubemap-harness; REPO=$PWD; mkdir -p "$S"/{tools,data,stubs,bin}

# 1. environment
python3 -m venv "$S/venv"
"$S/venv/bin/pip" install -r requirements-test.txt uvicorn
git clone --quiet https://github.com/CAST-genomics/panCT.git "$S/tools/panCT"
git -C "$S/tools/panCT" checkout --quiet 03c406b
printf 'import types\nogdf = types.SimpleNamespace()\ndef cppinclude(*a, **k):\n    return None\n' > "$S/stubs/ogdf_python.py"
printf '# stand-in for the compiled library\n' > "$S/stubs/adaptagrams.py"

# 2. the vg stand-in from §4.4, saved as "$S/bin/vg", then: chmod +x "$S/bin/vg"

# 3. seed the cache from the committed fixtures
mkdir -p "$REPO/cache/seqtubemap/mc"
cp "$REPO"/tests/fixtures/seqtubemap/*.gfa "$REPO/cache/seqtubemap/mc/"

# 4. run it
cd "$REPO"
GIT_CONFIG_COUNT=2 \
GIT_CONFIG_KEY_0=tools.path GIT_CONFIG_VALUE_0="$S/tools" \
GIT_CONFIG_KEY_1=data.path  GIT_CONFIG_VALUE_1="$S/data" \
PYTHONPATH="$S/stubs" VG_SHIM_REPO="$REPO" PATH="$S/bin:$PATH" \
  "$S/venv/bin/uvicorn" main:app --host 127.0.0.1 --port 8100 --log-level info
```

Then, from another shell:

```sh
curl -s -o /tmp/out.svg -w '%{http_code} %{time_starttransfer}s %{size_download}\n' \
  'http://127.0.0.1:8100/seqtubemap?chrom=chr8&start=78771162&end=78771252&version=v2'
```

The five servable regions are the five fixture filenames:

| region | query |
| --- | --- |
| 90 bp | `chrom=chr8&start=78771162&end=78771252` |
| 600 bp | `chrom=chr1&start=25331046&end=25331646` |
| 1.4 kb | `chrom=chr8&start=10079054&end=10080461` |
| 8.0 kb | `chrom=chr1&start=25301271&end=25309238` |
| 4.2 kb | `chrom=chr1&start=25331646&end=25335796` |

For the "before" side, add a worktree and give it the browser emulation back:

```sh
git worktree add "$S/before" 399db1e
cd "$S/before" && npm install          # restores jsdom + canvas from that commit's manifest
mkdir -p "$S/before/cache/seqtubemap/mc"
cp "$REPO"/tests/fixtures/seqtubemap/*.gfa "$S/before/cache/seqtubemap/mc/"
# same uvicorn line, but --port 8101, VG_SHIM_REPO="$S/before", run from "$S/before"
```

**Requesting anything else** — a region with no seeded `.gfa` — sends the endpoint down the
real extraction branch, which fails for want of the graph. That is correct behaviour, not a
harness fault.

---

## 6. What was measured

Each region: one warm-up request, then three timed, best taken. `curl`'s
`%{time_starttransfer}` is TTFB; `%{size_download}` is the payload.

| region | TTFB before | TTFB after | speedup | bytes before | bytes after | change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 90 bp | 0.646 s | **0.213 s** | 3.0× | 166,675 | 138,340 | −17.0% |
| 600 bp | 0.982 s | **0.278 s** | 3.5× | 2,738,884 | 2,352,410 | −14.1% |
| 1.4 kb | 1.226 s | **0.331 s** | 3.7× | 4,391,887 | 3,757,885 | −14.4% |
| 8.0 kb | 2.376 s | **0.735 s** | 3.2× | 12,090,267 | 10,408,507 | −13.9% |
| 4.2 kb | 2.561 s | **0.589 s** | 4.3× | 15,285,418 | 13,122,049 | −14.2% |

The endpoint's own `[stage-timing]` line attributes the saving. On the 90 bp region:

```
before: total=0.796s subgraph_extract=0.0s gfa_to_vg=0.011s vg_to_json=0.062s generate_svg=0.723s
after:  total=0.323s subgraph_extract=0.0s gfa_to_vg=0.010s vg_to_json=0.059s generate_svg=0.254s
```

Every stage but `generate_svg` is unchanged, which is the expected shape: #22 touched the Node
stage and nothing else.

**Conformance, checked on the response bodies.** For all five regions, the "after" body is
byte-identical to the "before" body once `color=`, `class="track{id}"` and `<title></title>`
are textually deleted from it. Drawable counts in `g.track` are unchanged — 592, 8,089, 13,246,
35,020, 44,795 — and `tests/node/pgb-parser.mjs`, which states `pgb`'s parsing contract, passes
on every one. `nodewidthoption=normal`, the one path whose geometry could have shifted, is
identical too, with the same nine `<text>` elements.

Neither server log contains an error, a traceback, or a non-200 response.

**Byte reductions are ~14% here against ~16.6% measured on the fixtures**, and the reason is
the absence of `minigraphnode`: with no PCLAI scheme every `pclaiX`/`pclaiY`/`pclaiScore` is
the short literal `None`, so the removed attributes are a smaller share of a smaller document.

---

## 7. What this proves, and what it does not

**Proves.** That the post-#22 code serves `/seqtubemap` over real HTTP, through the real
FastAPI handler, the real caching branch and the real Node subprocess; that the documents it
returns satisfy `pgb`'s parsing contract; that they differ from the pre-#22 documents by
exactly the three removals and nothing else; and that the saving is where the change was made.
It is a genuine A/B: the two instances differ only in the checkout they serve, because every
stand-in is shared between them.

> **`curl` stood in for `pgb`'s fetch, not for `pgb`.** It retrieves the bytes; it does not
> parse them. The parsing side was checked separately, and afterwards properly: `pgb`'s own
> `parseBands.ts` was run over the same documents and recovers bit-identical arrays from the
> pre- and post-#22 sides. See [`increment-b.md`](./increment-b.md), "Checked against `pgb`'s
> own parser".

**Does not prove.** Anything about the bytes real `vg` produces. The GFA → vg-JSON step ran
through this repository's own derivation, which is known to differ from `vg view -j` in at
least the subrange-naming respect. That step sits entirely **upstream** of #22 — it feeds the
Node stage, and #22 changed only what happens after — so it cannot mask a regression introduced
by this change. But an absolute claim of the form "production will return exactly these bytes"
is not supported by this harness. The evidence for that is CI, which installs `vg` v1.75.0 and
runs `tests/python/test_seqtubemap_endpoint.py` for real; those tests passed on
[PR #51](https://github.com/CAST-genomics/PangenomeAPI/pull/51).

**Does not cover.** `/json` and the 3D graph path, whose layout libraries were stubbed. Real
subgraph extraction, which was skipped by design. The PCLAI colouring path, which needs the
minigraph walks file — a request with `minigraphnode` set would have gone looking for a walk
derivative that this data directory does not contain.

**Absolute timings are a developer laptop, not the server.** The ratios are the transferable
part. Production's own baseline is [`seqtubemap-latency.md`](./seqtubemap-latency.md) §1, and
it will not move until something is promoted to `release`.

---

## 8. What was left behind

Nothing in the repository. The seeded `cache/` directory was deleted, the `git worktree` was
removed, both `uvicorn` processes were stopped and both ports confirmed closed. `git status`
is clean and `origin/release` is untouched at `33105e3`.

The harness itself — virtualenv, panCT clone, stubs, `vg` stand-in, captured documents and
server logs — lives in a session scratchpad, which is temporary. §5 is what makes it
reproducible; that is deliberately the only durable form it takes, so that a script named `vg`
which is not `vg` never sits in a checkout waiting to be found.
