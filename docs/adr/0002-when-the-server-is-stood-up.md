---
status: proposed
date: 2026-08-27
---

# The server is stood up only for claims the fixtures cannot carry

Both test suites run from a bare checkout: no `.gbz`, no `.walk.gz` derivatives, no
network. That is deliberate, and it is not a limitation to be fixed by pointing the tests
at a running server. **Fixtures are the default oracle. A server — local or live — is
stood up only when the claim being made is one the fixtures cannot carry, and a live
deploy only when the claim is end-to-end.**

This is written down because the suites look, from the outside, like they are missing
something. They are not.

## What each rung can prove

**Fixtures — the default.** `tests/python/conftest.py` stubs the two natively-compiled
layout libraries, stubs panCT where the machine lacks it, and points `data.path` at an
empty directory, because the walk derivatives are opened when something reads them.
`tests/python/test_seqtubemap_endpoint.py` then drives `/seqtubemap` end to end with no
graph data at all, by planting a committed subgraph at the pipeline's own cache path — the
`subgraph_cached` branch in `main.py`, an existing production shortcut rather than a test
hook. The Node suite renders committed inputs and asserts byte-identity against committed
documents.

This covers more than it looks like it does: the endpoint's request path, the generator's
output byte for byte, and — in CI, where `PANGENOME_TESTS_REQUIRE_ALL=1` turns every skip
and every stand-in into a failure — `vg` and panCT for real.

What it cannot cover: whether the real client accepts the output, and what anything costs
at production size.

**A local server — rare.** `fastapi dev main.py`, or `docker-compose` with `DATA_DIR`
mounted at `/data`. It needs the multi-gigabyte graph data on the machine and spends
around five minutes indexing on first run. Worth it to look at a real picture in a browser
or to reproduce a report against real data; not worth it as a routine step, and never as a
substitute for a test.

**A live deploy — the exception.** The server follows `release`, not `main`
([`docs/releasing.md`](../releasing.md)), so merging is not shipping: a deploy is a
promotion somebody performs on purpose (`git merge --ff-only main`) and then a colleague
with server access pulls and restarts. It costs someone else's afternoon-fragment, and it
is the only rung that can answer the two questions the fixtures cannot.

That the two are separate is what makes the rest of this decision safe to hold. Work can
land on `main` — including a rewrite as large as increment B — without anybody deciding to
put it in front of a researcher.

## When a live deploy is required

The test is not "is this change risky" — it is **"is the claim end-to-end?"** Three cases
qualify, and nothing else does:

1. **The claim is that `pgb` accepts the output.** [ADR 0001](./0001-additive-band-format.md)
   holds increment B byte-compatible with `pgb`'s existing parser as a deliberate
   constraint, precisely so that "`pgb` becomes its conformance test: a bad B shows up as
   an error card rather than as a diff nobody ran". That property is worth nothing unless
   the deploy actually happens, while the client is still unchanged.
2. **The claim is about time or memory at production size.** The committed fixtures top out
   well below the regime that fails. `subgraph_extract` is 77% of a 10 kb request and no
   fixture exercises it at all.
3. **The claim is about production data the fixtures do not carry** — a region, a strand
   naming convention, or a graph build that nothing in `tests/fixtures/` represents.

A change that makes none of these claims ships on the strength of the suites.

## Before any deploy, capture the before-state

The server that is about to be replaced is the only place the current bytes exist. Once it
restarts, a byte-comparison against it is impossible forever, and "it looked right in the
browser" is what remains.

So a deploy request is paired with a capture of the same URLs against the running server
beforehand, saved to disk. Afterwards the same URLs are fetched again and compared. That
is the difference between a conformance test and a glance.

This is not hypothetical: `tests/fixtures/seqtubemap/` holds five real *inputs* taken from
the live server, and no matching documents — `pgb`'s five golden documents predate a change
in how strands are named and no longer line up with them. The pairs were separable at the
time and were not taken.

## Considered and rejected

**A staging environment.** The honest answer to the deploy cost, and out of reach: the
data is multi-gigabyte and the machine is not ours to duplicate. Reconsider if either
changes.

**Live smoke tests in CI.** A scheduled job hitting the deployed server would catch drift,
but it tests whatever happens to be deployed rather than the commit under review, turns an
unrelated outage into a red build on someone's PR, and cannot run before a deploy — which
is exactly when the question matters.

**Deploying every merge to `main`.** Would make the deploy boundary meaningless and spend a
colleague's time per PR. The batching is a cost, not a feature, but it is the right cost.

**Standing up `pgb` against a local server in CI.** Two repositories in lockstep in a build,
to test a compatibility that ADR 0001 already holds by construction and that the golden
documents already pin byte for byte. The end-to-end check is worth running once per
increment, not once per commit.

## Consequences

- **A deploy validates a batch, not an increment.** `git log release..main` is the batch,
  and the deploy after increment B will also be the first to carry A's event-loop fix and
  #21's capture. The promotion message should name what is in it, so a surprise has a list
  of suspects rather than one assumed cause.
- **The fixtures have to be kept honest, because they are load-bearing.** Where a fixture is
  missing its oracle, that is a gap in the default rung and should be closed there rather
  than deferred to a deploy. The two skipped real-input golden cases in
  `tests/node/generate-svg.golden.test.mjs` are the current instance.
- **Watch for an oracle that degenerates.** `tests/node/band-data.test.mjs` proves the band
  data can rebuild the document by comparing the reconstruction against the render. After
  increment B the document *is* emitted from the band data, so that comparison becomes a
  tautology that still passes. The golden documents are what survive it.
- **`vg` remains a real dependency of the default rung** until increment D removes the round
  trip. Locally its absence skips; in CI it does not.
