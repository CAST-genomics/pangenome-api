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


def test_a_derivative_is_opened_once_per_process(main_module, walk_stand_in, monkeypatch):
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
