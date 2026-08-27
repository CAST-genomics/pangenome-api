"""One slow request must not stop the server serving everything else.

Both endpoints do their work by blocking: `vg`, Node and the layout libraries
are all subprocess or native calls that hold the calling thread for their full
duration. Declared `async def`, FastAPI runs them *on the event loop*, and a
request that takes two minutes stops every other request for those two minutes
— including requests to the unrelated endpoint the 3D graph depends on.
Declared as ordinary `def`, FastAPI runs them in its threadpool, which is where
blocking work belongs.

The test below is what tells the two apart. It puts a slow `/seqtubemap`
request in flight and then times a `/json` request issued from another thread:
on the threadpool the second returns immediately, on the event loop it cannot
return until the first has finished. Reverting `main`'s two handlers to
`async def` fails it.

`/seqtubemap` and `/json` are the only handlers this app has (`main.py:645` and
`main.py:721`), so between them the sweep for blocking work under an async
declaration is complete.

The slowness is stood in for rather than real: each pipeline stage is replaced
by a stub that writes its output file, and the first one also sleeps. What is
under test is where the framework runs the handler, which is decided by the
handler's declaration alone and is indifferent to what the stages actually do.
"""

import os
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# How long the stalled stage holds its thread. Long enough that a fast request
# blocked behind it cannot be mistaken for a fast one, short enough to pay for
# on every run.
STALL_SECONDS = 2.0

# The fast request does no work at all, so anything approaching the stall is a
# request that waited. Loose enough to survive a loaded CI machine.
FAST_LIMIT_SECONDS = STALL_SECONDS / 2

# `/json` rejects an unknown graph type before touching any graph data
# (main.py:798), which makes it the cheapest real request to the other
# endpoint — no pangenome, no layout library, no subprocess.
FAST_REQUEST = (
    "/json",
    {
        "chrom": "chr1",
        "start": 1,
        "end": 2,
        "graphtype": "no-such-graph-type",
        "debug_small_graphs": False,
    },
)


def _stage_writing_its_output(stalls_for=None):
    """Stand in for one pipeline stage: write the output path it was handed.

    Every stage `/seqtubemap` runs takes its output as the second positional
    argument, so one stub serves for all of them. `stalls_for` makes the stage
    hold its thread, which is the whole point of the exercise.
    """

    def stage(*args, **kwargs):
        if stalls_for is not None:
            time.sleep(stalls_for)
        Path(args[1]).write_bytes(b"stand-in for a pipeline stage's output\n")

    return stage


@pytest.fixture
def stalled_seqtubemap(main_module, monkeypatch, tmp_path):
    """`/seqtubemap` with its pipeline stubbed and its first stage stalled.

    The endpoint builds every path relative to the working directory, so the
    request runs from a temporary one and everything it writes lands there.
    """
    for stage in ("GenerateWalksMC", "ConvertGfaToVg", "ConvertVgToJson", "GenerateSeqTubeMapSvg"):
        monkeypatch.setattr(main_module, stage, _stage_writing_its_output())
    monkeypatch.setattr(
        main_module, "SubgraphMC", _stage_writing_its_output(stalls_for=STALL_SECONDS)
    )

    (tmp_path / "cache" / "seqtubemap" / "mc").mkdir(parents=True)
    previous = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield {"chrom": "chr1", "start": 1, "end": 2, "version": "v2"}
    finally:
        os.chdir(previous)


def test_a_request_completes_while_a_slow_one_is_still_running(app, stalled_seqtubemap):
    """The whole issue, in one assertion: the fast request does not wait.

    `TestClient` is entered as a context manager deliberately — that is what
    makes both requests share one event loop, as they would under a real
    server. Without it each request gets a loop of its own and could not block
    the other however the handlers were declared.
    """
    slow_response = {}

    with TestClient(app) as client:

        def issue_slow_request():
            slow_response["value"] = client.get("/seqtubemap", params=stalled_seqtubemap)

        slow = threading.Thread(target=issue_slow_request)
        slow.start()
        try:
            # Give the slow request time to reach its stalled stage, so what is
            # timed below is a request issued against a genuinely busy server.
            time.sleep(STALL_SECONDS / 4)

            path, params = FAST_REQUEST
            started = time.perf_counter()
            fast_response = client.get(path, params=params)
            elapsed = time.perf_counter() - started

            # What matters is that the request was served, not what it was
            # answered with: today that rejection is a 200 with a null body,
            # and this test should survive it being corrected to a 4xx.
            assert fast_response.status_code < 500, (
                f"the fast request was not served: {fast_response.status_code}"
            )
            assert elapsed < FAST_LIMIT_SECONDS, (
                f"the fast request took {elapsed:.2f}s — it waited for the slow one"
            )
            assert slow.is_alive(), "the slow request finished first; nothing was proven"
        finally:
            slow.join(timeout=STALL_SECONDS * 5)

    assert not slow.is_alive(), "the slow request never finished"
    assert slow_response["value"].status_code == 200
