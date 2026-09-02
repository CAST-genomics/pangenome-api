import math
from collections import deque

import adaptagrams as adap

from bubble_finding import build_adjacency, find_all_bubbles

NODE_SPACING = 30.0   #horizontal gap between consecutive nodes

#spine width is a power law in total bp using the below constants
SPINE_REF_WIDTH = 2000.0
SPINE_REF_BP = 100_000
#0 would make all spines regardless of length be 2000 units
#1 would make all spines scale to exact bp length
SPINE_WIDTH_EXPONENT = 0.5

#min width of nodes off spine as a fraction of the total spine width
#(keeps small nodes visible with really big spines)
OFF_SPINE_MIN_WIDTH_FRACTION = 1.0 / 500.0


def spine_width(total_bp):
    """Note for future: a constant pad could be added to total_bp if small loci look really bad.
    Since this uses a power law, really small loci will have tiny spines. +5000 to total_bp in the return
    func would probably fix this but may not be necessary."""
    return SPINE_REF_WIDTH * (max(1, total_bp) / SPINE_REF_BP) ** SPINE_WIDTH_EXPONENT


class AdaptagramsGraph:
    """
    Builds adaptagrams layout inputs from a PGGraph for linear
    alignment.

    Attributes
    ==========
    rs : adaptagrams.RectanglePtrs
        All subnode rectangles
    es : adaptagrams.ColaEdges
        FD spring edges: non-asm internal chains + external edges (excl. asm<->asm)
    edge_lengths : list[float]
        Per-edge ideal-length weight, same order/len as es
    node_to_rects : dict[PGNode, list[int]]
        Mapping of node to its ordered rect indices
    """

    def __init__(self, pggraph, rect_size=1.0):
        self.pggraph = pggraph
        self.rect_size = rect_size
        self._base_ideal = pggraph.m_settings.get("NODESEGLEN", 20.0)
        self._weight = NODE_SPACING / self._base_ideal

        self.rs = adap.RectanglePtrs()
        self.es = adap.ColaEdges()
        self.edge_lengths = []

        self.node_to_rects = {}
        self._fixed = set()

        #set at first point where total bp on spine is known
        self._bp_scale = None
        self._spine_total_width = None
        self._spine_bp_total = 0
        self._asm_order = []

        #need to store rect pointers so they don't get garbage collected mid-layout
        self._rect_objs = []

        self._mark_drawn()
        self._add_nodes()

    def _mark_drawn(self):
        for node in self.pggraph.pgnodes.values():
            #all positive nodes are drawn
            if node.isPositiveNode():
                node.setAsDrawn()

    def _node_in_layout(self, node):
        return node in self.node_to_rects

    def _this_or_rc_in_layout(self, node):
        rc = node.getReverseComplement()
        return self._node_in_layout(node) or (rc is not None and self._node_in_layout(rc))

    def _new_rect(self, width):
        r = adap.Rectangle(0.0, width, 0.0, self.rect_size)
        idx = len(self._rect_objs)
        self._rect_objs.append(r)
        self.rs.push_back(r)
        return idx

    def _add_edge(self, i, j):
        self.es.push_back(adap.ColaEdge(i, j))
        self.edge_lengths.append(self._weight)

    def _add_nodes(self):
        """One rect per subnode for every drawn node"""
        for node in self.pggraph.pgnodes.values():
            if not node.isDrawn() or self._this_or_rc_in_layout(node):
                continue
            drawn_len = node.GetDrawnNodeLength()
            num_edges = node.GetNumOgdfGraphEdges(drawn_len)
            self.node_to_rects[node] = [
                self._new_rect(2.0) for _ in range(num_edges + 1)
            ]

    #simple accessors just to help readability a bit
    def _chain_last(self, node):
        return self.node_to_rects[node][-1]

    def _chain_first(self, node):
        return self.node_to_rects[node][0]

    def resolve(self, node):
        """Get whichever node is in layout (node or its reverse compliment)"""
        if self._node_in_layout(node):
            return node
        rc = node.getReverseComplement()
        if rc is not None and self._node_in_layout(rc):
            return rc
        return None

    def _matches(self, node):
        """True if node has an entry for the selected assembly + haplotype"""
        for entry in node.m_nd_assembly + node.m_dup_assembly:
            if entry["assembly_name"] == self._assembly and \
                    (self._haplotype is None or entry["haplotype"] == self._haplotype):
                return True
        return False

    def _is_asm(self, node):
        """True if node (or its rc) belongs to the selected assembly+haplotype"""
        r = self.resolve(node)
        return r is not None and self._matches(r)

    def _is_asm_name(self, name):
        node = self.pggraph.pgnodes.get(name)
        return node is not None and self._matches(node)

    def _node_width(self, name):
        """
        Get the width of a node off the assembly spine.
        """
        node = self.pggraph.pgnodes[name]
        if self._bp_scale is None:
            return node.GetDrawnNodeLength()
        floor = self._spine_total_width * OFF_SPINE_MIN_WIDTH_FRACTION
        return max(node.GetLength() * self._bp_scale, floor)

    def _spine_width(self, name):
        """
        Get the width of a node on the assembly spine.
        Will be proportional to the number of basepairs in the node, scaled to fit desired total length.
        """
        node = self.pggraph.pgnodes[name]
        if self._bp_scale is None:
            #legacy approach
            chain = self.node_to_rects[node]
            return max(1, len(chain) - 1) * NODE_SPACING
        return max(node.GetLength(), 1) * self._bp_scale

    def _spine_segment(self, name):
        """Gets center-to-center pitch between consecutive rects of a spine node."""
        chain = self.node_to_rects[self.pggraph.pgnodes[name]]
        n = len(chain)
        return self._spine_width(name) / (n - 1) if n > 1 else 0.0

    def _place_chain(self, name, x, y):
        """Place a node's subnode rects starting at (x, y), spanning its width"""
        node = self.pggraph.pgnodes[name]
        chain = self.node_to_rects[node]
        n = len(chain)
        if n == 1:
            self.rs[chain[0]].moveCentreX(x)
            self.rs[chain[0]].moveCentreY(y)
            return
        seg = (self._spine_segment(name) if self._is_asm_name(name)
               else self._node_width(name) / (n - 1))
        for i, idx in enumerate(chain):
            self.rs[idx].moveCentreX(x + i * seg)
            self.rs[idx].moveCentreY(y)

    def _place_bubble_interior(self, bubble, out_adj, in_adj, placed,
                               bubble_by_source, junction_x, start_parity=0):
        """
        Seed non-asm interior nodes of a bubble.
        """
        interior_set = set(bubble.interior)

        in_cnt = {
            n: sum(1 for p in in_adj.get(n, []) if p in interior_set)
            for n in interior_set
        }
        q = deque(n for n in interior_set if in_cnt[n] == 0)
        topo = []
        seen = set()
        while q:
            n = q.popleft()
            if n in seen:
                continue
            seen.add(n)
            topo.append(n)
            for nb in out_adj.get(n, []):
                if nb in interior_set and nb not in seen:
                    in_cnt[nb] -= 1
                    if in_cnt[nb] == 0:
                        q.append(nb)
        for n in interior_set:
            if n not in seen:
                topo.append(n)

        direct_nonasm = [n for n in topo if not self._is_asm_name(n) and n not in placed]
        n = len(direct_nonasm)
        R = NODE_SPACING * max(1.0, n / (2 * math.pi))
        above = (start_parity % 2 == 0)

        arc_idx = 0
        sub_count = 0
        for iname in topo:
            if iname in placed:
                continue
            sub = bubble_by_source.get(iname)
            has_sub = sub is not None and sub is not bubble

            if self._is_asm_name(iname):
                if has_sub:
                    self._place_bubble_interior(
                        sub, out_adj, in_adj, placed, bubble_by_source,
                        junction_x=junction_x,
                        start_parity=(start_parity + sub_count + 1) % 2)
                    sub_count += 1
                continue

            theta = 2 * math.pi * (arc_idx + 1) / (n + 1)
            x0 = junction_x + R * math.sin(theta)
            y0 = R * (1 - math.cos(theta)) * (1 if above else -1)

            self._place_chain(iname, x0, y0)
            placed.add(iname)

            if has_sub:
                self._place_bubble_interior(
                    sub, out_adj, in_adj, placed, bubble_by_source,
                    junction_x=x0 + self._node_width(iname),
                    start_parity=(start_parity + sub_count + 1) % 2)
                sub_count += 1

            arc_idx += 1

    def seed_linear_layout(self, assembly, haplotype=None, bp_scaled=True):
        """
        Initial placement of spine and bubbles.
        haplotype filters to one haplotype of assembly; `None` = all.

        bp_scaled=True makes spine width exactly proportional to node bp, which
        is what the frontend's annotation track requires to map reference
        coordinates onto the graph at a constant rate. False restores the legacy
        fixed-pitch grid for comparison.
        """
        self._assembly = assembly
        self._haplotype = haplotype
        self._spine_y = 0.0

        out_adj, in_adj = build_adjacency(self.pggraph)

        #topo ordering
        asm_set = {n for n in out_adj if self._is_asm_name(n)}
        in_count = {
            n: sum(1 for p in in_adj.get(n, []) if p in asm_set)
            for n in asm_set
        }
        queue = deque(n for n in asm_set if in_count[n] == 0)
        asm_order = []
        while queue:
            n = queue.popleft()
            asm_order.append(n)
            for nb in out_adj.get(n, []):
                if nb in asm_set:
                    in_count[nb] -= 1
                    if in_count[nb] == 0:
                        queue.append(nb)
        self._asm_order = asm_order

        #normalize against the spine's total number of bp
        self._spine_bp_total = sum(
            self.pggraph.pgnodes[n].GetLength() for n in asm_order)
        self._spine_total_width = (
            spine_width(self._spine_bp_total) if bp_scaled else None)
        self._bp_scale = (
            self._spine_total_width / max(1, self._spine_bp_total)
            if bp_scaled else None)

        bubbles = find_all_bubbles(self.pggraph, out_adj, in_adj)
        bubble_by_source = {b.source: b for b in bubbles}

        placed = set()
        spine_x = 0.0
        for name in asm_order:
            if name in placed:
                continue
            self._place_chain(name, spine_x, 0.0)
            spine_x += self._spine_width(name)
            placed.add(name)

            bubble = bubble_by_source.get(name)
            if bubble is None:
                continue
            self._place_bubble_interior(
                bubble, out_adj, in_adj, placed, bubble_by_source,
                junction_x=spine_x)

        # asm rect indices, for the spine y-alignment constraint
        self._fixed = set()
        for name in asm_set:
            node = self.pggraph.pgnodes.get(name)
            if node in self.node_to_rects:
                self._fixed.update(self.node_to_rects[node])

        self._build_springs()

    def _assembly_metadata(self, name):
        """First metadata entry on `name` for the selected assembly+haplotype."""
        node = self.pggraph.pgnodes.get(name)
        if node is None:
            return None
        for entry in node.m_nd_assembly + node.m_dup_assembly:
            if entry["assembly_name"] != self._assembly:
                continue
            if self._haplotype is not None and entry["haplotype"] != self._haplotype:
                continue
            for meta in entry.get("metadata", []):
                return meta
        return None

    def spine_report(self):
        """Facts about layout which frontend can use to identify linear files which were dropped in"""
        return {
            "assembly": self._assembly,
            "haplotype": self._haplotype,
            "bp_scaled": self._bp_scale is not None,
            "bp_scale": self._bp_scale,
            "total_bp": self._spine_bp_total,
            "total_width": self._spine_total_width,
            "node_count": len(self._asm_order)
        }

    def _edge_rects(self, edge):
        start, end = edge.startingNode, edge.endingNode
        if self._node_in_layout(start):
            i = self._chain_last(start)
        elif start.getReverseComplement() is not None and \
                self._node_in_layout(start.getReverseComplement()):
            i = self._chain_first(start.getReverseComplement())
        else:
            return None
        if self._node_in_layout(end):
            j = self._chain_first(end)
        elif end.getReverseComplement() is not None and \
                self._node_in_layout(end.getReverseComplement()):
            j = self._chain_last(end.getReverseComplement())
        else:
            return None
        return i, j

    def _build_springs(self):
        #internal chains: non-asm nodes only
        for node, chain in self.node_to_rects.items():
            if self._is_asm(node):
                continue
            for a, b in zip(chain, chain[1:]):
                self._add_edge(a, b)

        #external edges between nodes
        for edge in self.pggraph.pgedges.values():
            edge.DetermineIfDrawn()
            if not edge.isDrawn():
                continue
            rects = self._edge_rects(edge)
            if rects is None:
                continue
            i, j = rects

            #skip single-segment self connecting nodes (avoids a self-edge)
            start = edge.startingNode
            drawn_len = start.GetDrawnNodeLength()
            if start == edge.endingNode and start.GetNumOgdfGraphEdges(drawn_len) == 1:
                continue

            if self._is_asm(start) and self._is_asm(edge.endingNode):
                continue

            self._add_edge(i, j)

    def get_segment_coordinates(self, node):
        """Gets rect centers for every rect in node"""
        return [(self.rs[idx].getCentreX(), self.rs[idx].getCentreY())
                for idx in self.node_to_rects[node]]

    def _spine_alignment(self):
        """Pin every assembly rect onto one horizontal line"""
        ac = adap.AlignmentConstraint(adap.YDIM, self._spine_y)
        for idx in self._fixed:
            ac.addShape(idx, 0.0)
        ac.fixPos(self._spine_y)
        return ac

    def _spine_x_chain(self):
        """
        Rigid front-to-back x ordering of assembly rects.

        The final True is `equality`, so these are exact placements, not minimum
        gaps - the FD relax projects onto them rather than around them. That makes
        this method, and not the layout solver, the thing that decides spine
        geometry.

        Two gaps are in play:
          - within a node: _spine_segment(name), so the node's first and last rect
            centres are exactly `bp * bp_scale` apart;
          - between nodes: 0.0, so the last centre of one node coincides with the
            first centre of the next. Nodes are contiguous, with no seam for the
            annotation track's bp mapping to fall through.

        Total spine width is therefore sum(bp) * bp_scale == spine_width(sum(bp)).

        (Docstring generated by Claude Opus 5.0)
        """
        cs = []
        prev = None
        for name in self._asm_order:
            chain = self.node_to_rects[self.pggraph.pgnodes[name]]
            seg = self._spine_segment(name)
            for k, idx in enumerate(chain):
                if prev is not None:
                    gap = seg if k > 0 else 0.0
                    cs.append(adap.SeparationConstraint(adap.XDIM, prev, idx, gap, True))
                prev = idx
        return cs

    def _branch_y_separations(self):
        """
        Pin each non-asm subnode exactly NODE_SPACING off the spine along every
        asm<->non-asm edge.
        """
        cs = []
        for edge in self.pggraph.pgedges.values():
            edge.DetermineIfDrawn()
            if not edge.isDrawn():
                continue
            rects = self._edge_rects(edge)
            if rects is None:
                continue
            i, j = rects
            u_asm = self._is_asm(edge.startingNode)
            v_asm = self._is_asm(edge.endingNode)
            if u_asm == v_asm:
                continue
            asm_idx, nonasm_idx = (i, j) if u_asm else (j, i)
            if self.rs[nonasm_idx].getCentreY() >= self._spine_y:
                cs.append(adap.SeparationConstraint(adap.YDIM, asm_idx, nonasm_idx, NODE_SPACING, True))
            else:
                cs.append(adap.SeparationConstraint(adap.YDIM, nonasm_idx, asm_idx, NODE_SPACING, True))
        return cs

    def build_fd_layout(self, ideal_length=None):
        """Builds fd layout with the linear-alignment constraints"""
        if ideal_length is None:
            ideal_length = self._base_ideal / 1.5

        self._constraints = adap.CompoundConstraintPtrs()
        self._constraints.push_back(self._spine_alignment())
        for c in self._spine_x_chain():
            self._constraints.push_back(c)
        for c in self._branch_y_separations():
            self._constraints.push_back(c)

        self._fd = adap.ConstrainedFDLayout(self.rs, self.es, ideal_length,
                                            adap.Doubles(self.edge_lengths))
        self._fd.setConstraints(self._constraints)
        return self._fd

    def close(self):
        """
        Drop all our C++ refs so they can be garbage collected
        """
        self._fd = None
        self._constraints = None
        self.rs = None
        self.es = None
        self.node_to_rects.clear()
        self._rect_objs.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
