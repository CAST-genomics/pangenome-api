from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class Bubble:
    """A bubble (branching region): source, sink, and interior node names."""
    source: str
    sink: str
    interior: frozenset


def build_adjacency(pg) -> tuple[dict, dict]:
    """
    Build out_adj and in_adj from a PGGraph object.
    Only positive nodes and positive edges are considered.
    """
    out_adj = {n: [] for n in pg.pgnodes if pg.pgnodes[n].isPositiveNode()}
    in_adj = {n: [] for n in pg.pgnodes if pg.pgnodes[n].isPositiveNode()}

    for edge in pg.pgedges.values():
        if not edge.isPositiveEdge():
            continue
        s = edge.getStartingNode().nodeName
        t = edge.getEndingNode().nodeName
        if s in out_adj and t in in_adj:
            if t not in out_adj[s]:
                out_adj[s].append(t)
            if s not in in_adj[t]:
                in_adj[t].append(s)

    return out_adj, in_adj


def _reachable_from(source: str, out_adj: dict, node_set: set) -> set:
    """BFS: all nodes reachable from *source* restricted to *node_set*."""
    visited = set()
    q = deque([source])
    while q:
        n = q.popleft()
        if n in visited or n not in node_set:
            continue
        visited.add(n)
        for nb in out_adj.get(n, []):
            if nb not in visited:
                q.append(nb)
    return visited


def _find_sink(
    source: str,
    out_adj: dict,
    in_adj: dict,
    node_set: set,
) -> Optional[tuple[str, frozenset]]:
    """
    Wavefront search from *source* within *node_set*.

    When the wavefront collapses to a single node, (sink, interior) is returned.
    Otherwise, None is returned.
    """
    if len(out_adj.get(source, [])) < 2:
        return None

    reachable = _reachable_from(source, out_adj, node_set)

    #get number of predecessors
    in_deg = {
        n: sum(1 for p in in_adj.get(n, []) if p in reachable)
        for n in reachable
    }

    visited = {source}
    interior = set()

    wavefront = set()
    visit_count = {}

    for nb in out_adj.get(source, []):
        if nb in reachable:
            wavefront.add(nb)
            visit_count[nb] = visit_count.get(nb, 0) + 1

    while True:
        if not wavefront:
            return None

        #sink case
        if len(wavefront) == 1:
            sink = next(iter(wavefront))
            if visit_count.get(sink, 0) == in_deg[sink]:
                return sink, frozenset(interior)
            return None

        node = next(
            (n for n in wavefront if visit_count.get(n, 0) == in_deg[n]),
            None,
        )
        if node is None:
            raise ValueError(
                f"Cycle detected in reachable subgraph from {source!r}; "
                "pangenome graph is expected to be acyclic."
            )

        wavefront.remove(node)
        visited.add(node)
        interior.add(node)

        for nb in out_adj.get(node, []):
            if nb in reachable and nb not in visited:
                wavefront.add(nb)
                visit_count[nb] = visit_count.get(nb, 0) + 1


def find_bubble_from_source(
    source: str,
    out_adj: dict,
    in_adj: dict,
    node_set: set = None,
) -> Optional[Bubble]:
    """Find the bubble whose source is *source*, or None."""
    if node_set is None:
        node_set = set(out_adj.keys()) | set(in_adj.keys())

    result = _find_sink(source, out_adj, in_adj, node_set)
    if result is None:
        return None

    sink, interior = result
    return Bubble(source=source, sink=sink, interior=interior)


def find_all_bubbles(
    pg=None,
    out_adj: dict = None,
    in_adj: dict = None,
) -> list[Bubble]:
    """
    Find all bubbles in the graph.

    Pass either a PGGraph object (*pg*) or pre-built adjacency dicts.
    Returns a list of Bubble objects (one per branching source).
    """
    if out_adj is None or in_adj is None:
        if pg is None:
            raise ValueError("Provide either a PGGraph (pg=) or both out_adj and in_adj.")
        out_adj, in_adj = build_adjacency(pg)

    bubbles = []
    for node in out_adj:
        if len(out_adj[node]) < 2:
            continue
        bubble = find_bubble_from_source(node, out_adj, in_adj)
        if bubble is not None:
            bubbles.append(bubble)

    return bubbles
