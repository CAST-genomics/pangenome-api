"""The walk derivatives, opened when something reads them rather than at import.

The four `.walk.gz` files are team-generated, not public downloads, so the
machine running these tests is exactly the machine that does not have them.
Every test here therefore runs against `data_dir`, which is empty: the app in
this session was booted with no walk derivative on disk at all.
"""

import pytest


def test_the_app_boots_with_no_walk_derivative_present(data_dir, client):
    """The premise of this file, asserted rather than assumed."""
    assert not list(data_dir.glob("*.walk.gz"))

    assert client.get("/openapi.json").status_code == 200


def test_a_request_reading_no_walk_derivative_succeeds(client):
    """Routing, and the handlers' own imports, do not touch a derivative."""
    assert client.get("/no-such-route").status_code == 404


def test_reading_a_missing_derivative_names_the_file_and_the_reason(main_module):
    derivative = main_module.minigraph_walks_v2_updated

    with pytest.raises(main_module.MissingWalkDerivative) as raised:
        derivative.fetch(".", 0, 1)

    message = str(raised.value)
    assert "v1_1_hprc_v2.0_minigraph.sorted.pclai.walk.gz" in message
    assert derivative.purpose in message


def test_a_missing_derivative_is_served_as_an_error_response(main_module, client):
    """The failure reaches the client as a 503, rather than only the log.

    Driven through a route added for the test, because every endpoint that
    genuinely reads a walk derivative reaches for a multi-gigabyte graph first.
    The route is removed again, so the app the other tests see is unchanged.
    """
    app = main_module.app

    @app.get("/test-only-reads-a-walk")
    def reads_a_walk():
        return list(main_module.minigraph_walks_v2_updated.fetch(".", 0, 1))

    try:
        response = client.get("/test-only-reads-a-walk")
    finally:
        app.router.routes.pop()

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "v1_1_hprc_v2.0_minigraph.sorted.pclai.walk.gz" in detail
    assert main_module.minigraph_walks_v2_updated.purpose in detail


def test_a_present_derivative_is_read(main_module, walk_stand_in):
    """Behaviour when the file is there: the rows come back."""
    derivative = main_module.WalkDerivative(walk_stand_in, "a test")

    assert [line.split("\t")[:2] for line in derivative.fetch("chr1", 0, 200)] == [
        ["chr1", "0"],
        ["chr1", "100"],
    ]


def test_a_derivative_is_opened_once_per_thread(main_module, walk_stand_in, monkeypatch):
    """Not once per request: the tabix index is paid for the first time only."""
    import pysam

    opens = []
    real = pysam.TabixFile

    def counting_tabix_file(path, *args, **kwargs):
        opens.append(path)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(pysam, "TabixFile", counting_tabix_file)
    derivative = main_module.WalkDerivative(walk_stand_in, "a test")

    list(derivative.fetch("chr1", 0, 200))
    list(derivative.fetch("chr1", 0, 200))

    assert opens == [str(walk_stand_in)]


def test_two_threads_never_share_a_handle(main_module, walk_stand_in):
    """The invariant pysam requires, and the one the live server broke.

    A `pysam.TabixFile` is one htslib handle with one seek position, and `fetch`
    hands back a lazy iterator, so the handle stays in use for as long as the
    caller takes to read it — in `GenerateWalksMC`, minutes. Endpoints run in
    FastAPI's threadpool, so two requests genuinely overlap; sharing one handle
    between them interleaved the seeks and left it broken for the life of the
    process. Every later request that read a walk derivative then failed, while
    cached requests, which read none, kept working — which is exactly how the
    `increment-b` trial wedged, and why only a restart cleared it.

    Asserted on the handles rather than on a race, because a race that has to be
    provoked makes a flaky test: what is checked is that there is nothing to
    race over.
    """
    import threading

    derivative = main_module.WalkDerivative(walk_stand_in, "a test")
    handles = {}

    def read_in_this_thread(name):
        rows = list(derivative.fetch("chr1", 0, 200))
        handles[name] = (derivative._open(), rows)

    threads = [
        threading.Thread(target=read_in_this_thread, args=(name,))
        for name in ("first", "second")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    first, second = handles["first"], handles["second"]
    assert first[0] is not second[0], "two threads were handed the same tabix handle"
    # And each thread read the file correctly through its own handle.
    assert [row.split("\t")[:2] for row in first[1]] == [["chr1", "0"], ["chr1", "100"]]
    assert first[1] == second[1]


def test_one_thread_keeps_its_own_handle(main_module, walk_stand_in):
    """The other half of it: per-thread, not per-call.

    Opening a multi-gigabyte tabix index per `fetch` would be its own defect —
    `GenerateWalksMC` calls `fetch` once per `S` line.
    """
    derivative = main_module.WalkDerivative(walk_stand_in, "a test")

    assert derivative._open() is derivative._open()
