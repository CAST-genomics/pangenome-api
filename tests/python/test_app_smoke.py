"""Smoke test: the application boots and serves.

Nothing here asserts anything about the pangenome — it asserts that `main`
imports, that the app object is a live FastAPI application, and that a request
reaches it and comes back. Everything downstream of this file assumes that
much works.
"""


def test_the_app_serves_its_schema(client):
    """`/openapi.json` is FastAPI's own route — the most trivial one there is."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["openapi"].startswith("3.")


def test_the_endpoints_are_registered(client):
    """The two endpoints the browser calls are present on the booted app."""
    paths = client.get("/openapi.json").json()["paths"]

    assert "/seqtubemap" in paths
    assert "/json" in paths


def test_an_unknown_route_is_a_404(client):
    """The app routes rather than falling over."""
    assert client.get("/no-such-route").status_code == 404
