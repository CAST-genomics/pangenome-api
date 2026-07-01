import adaptagrams as adap

class AdaptagramsGraph:
    """
    Builds adaptagrams (libcola) layout inputs from a PGGraph for linear alignment.

    Attributes
    ==========
    rs : adaptagrams.RectanglePtrs
        All segment rectangles
    es : adaptagrams.ColaEdges
        All edges, including internal & external
    edge_lengths : list[float]
        Ideal length per edge in es, same order/len as es
    node_to_rects : dict[PGNode, list[int]]
        Mapping of node to its ordered rect indices
    """

    def __init__(self, pggraph, rect_size=1.0):
        self.pggraph = pggraph
        self.rect_size = rect_size

        self.rs = adap.RectanglePtrs()
        self.es = adap.ColaEdges()
        self.edge_lengths = []

        self.node_to_rects = {}
        self._fixed = set()

        #need to store rect pointers so they don't get garbage collected mid-layout
        self._rect_objs = []

        self._mark_drawn()
        self._add_nodes()
        self._add_edges()

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

    def _add_edge(self, i, j, ideal_length):
        self.es.push_back(adap.ColaEdge(i, j))
        self.edge_lengths.append(float(ideal_length))

    def _add_nodes(self):
        """
        Adds every drawn node to the graph, including bandage subnodes
        """
        for node in self.pggraph.pgnodes.values():
            if not node.isDrawn() or self._this_or_rc_in_layout(node):
                continue

            drawn_len = node.GetDrawnNodeLength()
            num_edges = node.GetNumOgdfGraphEdges(drawn_len)
            seg_len = drawn_len / num_edges

            #add rect for each subnode
            chain = []
            prev_idx = None
            for i in range(num_edges + 1):
                idx = self._new_rect(seg_len)
                chain.append(idx)
                if i > 0:
                    self._add_edge(prev_idx, idx, seg_len)
                prev_idx = idx

            self.node_to_rects[node] = chain

    #simple accessors just to help readability a bit
    def _chain_last(self, node):
        return self.node_to_rects[node][-1]

    def _chain_first(self, node):
        return self.node_to_rects[node][0]

    def _add_edges(self):
        edge_len = self.pggraph.m_settings["EDGELEN"]
        for edge in self.pggraph.pgedges.values():
            edge.DetermineIfDrawn()
            if not edge.isDrawn():
                continue

            start = edge.startingNode
            end = edge.endingNode

            #pretty much the same logic as AddEdgeToOGDFGraph in bandage_graph.py
            if self._node_in_layout(start):
                first_idx = self._chain_last(start)
            elif start.getReverseComplement() is not None and \
                    self._node_in_layout(start.getReverseComplement()):
                first_idx = self._chain_first(start.getReverseComplement())
            else:
                continue

            if self._node_in_layout(end):
                second_idx = self._chain_first(end)
            elif end.getReverseComplement() is not None and \
                    self._node_in_layout(end.getReverseComplement()):
                second_idx = self._chain_last(end.getReverseComplement())
            else:
                continue

            #skip single-segment self connecting nodes
            drawn_len = start.GetDrawnNodeLength()
            if start == end and start.GetNumOgdfGraphEdges(drawn_len) == 1:
                continue

            self._add_edge(first_idx, second_idx, edge_len)

    def resolve(self, node):
        """Get whichever node is in layout (node or its reverse compliment)"""
        if self._node_in_layout(node):
            return node
        rc = node.getReverseComplement()
        if rc is not None and self._node_in_layout(rc):
            return rc
        return None

    def _assembly_topo_order(self, assembly):
        """Topological sort of selected assembly using Kahn's"""
        nodes = {n for n in self.node_to_rects if assembly in n.m_assembly}
        children = {n: set() for n in nodes}
        indeg = {n: 0 for n in nodes}
        for edge in self.pggraph.pgedges.values():
            edge.DetermineIfDrawn()
            if not edge.isDrawn():
                continue
            u = self.resolve(edge.startingNode)
            v = self.resolve(edge.endingNode)
            if u in nodes and v in nodes and u is not v and v not in children[u]:
                children[u].add(v)
                indeg[v] += 1

        frontier = [n for n in nodes if indeg[n] == 0]
        order = []
        while frontier:
            u = frontier.pop()
            order.append(u)
            for v in children[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    frontier.append(v)
        return order

    def seed_linear_layout(self, assembly, y=None, branch_gap=None):
        """Seed initial rect positions for fd, including assembly & non-assembly branches"""
        if y is None:
            y = self.rect_size / 2.0
        if branch_gap is None:
            branch_gap = self.pggraph.m_settings["EDGELEN"]

        self._fixed = set()
        x = 0.0
        for node in self._assembly_topo_order(assembly):
            chain = self.node_to_rects[node]
            drawn_len = node.GetDrawnNodeLength()
            #same per-edge length as _add_nodes so node spans its true drawn length
            seg_len = drawn_len / node.GetNumOgdfGraphEdges(drawn_len)
            for i, idx in enumerate(chain):
                self.rs[idx].moveCentreX(x + i * seg_len)
                self.rs[idx].moveCentreY(y)
                self._fixed.add(idx)
            x += (len(chain) - 1) * seg_len

        self._seed_branches(self._fixed, y, branch_gap)

    def _rect_adjacency(self):
        """Adjacency matrix over all rects in graph"""
        adj = {i: [] for i in range(len(self._rect_objs))}
        for k in range(len(self.edge_lengths)):
            e = self.es[k]
            a, b = (e.first, e.second) if hasattr(e, "first") else (e[0], e[1])
            adj[a].append(b)
            adj[b].append(a)
        return adj

    def _seed_branches(self, fixed, base_y, gap):
        adj = self._rect_adjacency()
        seen = set(fixed)
        x = {i: self.rs[i].getCentreX() for i in fixed}

        def walk(cur, prev, level):
            y = base_y + level * gap
            while cur is not None and cur not in seen:
                seen.add(cur)
                x[cur] = x[prev] + gap
                self.rs[cur].moveCentreX(x[cur])
                self.rs[cur].moveCentreY(y)
                nbrs = [w for w in adj[cur] if w not in seen]
                prev, cur = cur, (nbrs[0] if nbrs else None)
                #rest are subbubbles
                for w in nbrs[1:]:
                    walk(w, prev, level + 1)

        #first layer neighbors are starts of bubbles
        for f in list(fixed):
            for w in adj[f]:
                walk(w, f, 1)

    def get_segment_coordinates(self, node):
        """Gets rect centers for every rect in node"""
        return [(self.rs[idx].getCentreX(), self.rs[idx].getCentreY())
                for idx in self.node_to_rects[node]]

    def _forward_x_constraints(self):
        """Makes non asm edges point forward"""
        cs = adap.CompoundConstraintPtrs()
        for k in range(len(self.edge_lengths)):
            e = self.es[k]
            i, j = (e.first, e.second) if hasattr(e, "first") else (e[0], e[1])
            if i in self._fixed or j in self._fixed:
                continue
            cs.push_back(adap.SeparationConstraint(adap.XDIM, i, j, 0.0))
        return cs

    def build_fd_layout(self, ideal_length=1.0):
        """Builds and runs fd layout"""
        #lock each assembly rect at its seeded (linear) position
        self._locks = adap.ColaLocks()
        for idx in self._fixed:
            r = self.rs[idx]
            self._locks.push_back(adap.Lock(idx, r.getCentreX(), r.getCentreY()))
        self._pre = adap.PreIteration(self._locks)

        self._fd = adap.ConstrainedFDLayout(self.rs, self.es, ideal_length,
                                            adap.Doubles(self.edge_lengths),
                                            None, self._pre)
        self._constraints = self._forward_x_constraints()
        self._fd.setConstraints(self._constraints)
        self._fd.setAvoidNodeOverlaps(True)
        return self._fd

    def close(self):
        """
        Drop all our C++ refs so they can be garbage collected
        """
        self._fd = None
        self._pre = None
        self._locks = None
        self._constraints = None
        self.rs = None
        self.es = None
        self.node_to_rects.clear()
        self._rect_objs.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
