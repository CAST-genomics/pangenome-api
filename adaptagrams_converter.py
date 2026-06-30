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

    def _new_rect(self):
        #a rect_size x rect_size rect (spanning from 0 to rect_size)
        r = adap.Rectangle(0.0, self.rect_size, 0.0, self.rect_size)
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
        seg_len = self.pggraph.m_settings["NODESEGLEN"]
        for node in self.pggraph.pgnodes.values():
            if not node.isDrawn() or self._this_or_rc_in_layout(node):
                continue

            drawn_len = node.GetDrawnNodeLength()
            num_edges = node.GetNumOgdfGraphEdges(drawn_len)

            #add rect for each subnode
            chain = []
            prev_idx = None
            for i in range(num_edges + 1):
                idx = self._new_rect()
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

    def seed_linear_layout(self, assembly, y=None, branch_gap=None, iters=20):
        """Seed initial rect positions for fd, including assembly & non-assembly branches"""
        if y is None:
            y = self.rect_size / 2.0
        if branch_gap is None:
            branch_gap = self.pggraph.m_settings["EDGELEN"]

        seg_len = self.pggraph.m_settings["NODESEGLEN"]
        self._fixed = set()
        x = 0.0
        for node in self._assembly_topo_order(assembly):
            chain = self.node_to_rects[node]
            for i, idx in enumerate(chain):
                self.rs[idx].moveCentreX(x + i * seg_len)
                self.rs[idx].moveCentreY(y)
                self._fixed.add(idx)
            x += (len(chain) - 1) * seg_len

        self._seed_branches(self._fixed, y, branch_gap, iters)

    def _rect_adjacency(self):
        """Adjacency matrix over all rects in graph"""
        adj = {i: [] for i in range(len(self._rect_objs))}
        for k in range(len(self.edge_lengths)):
            e = self.es[k]
            a, b = (e.first, e.second) if hasattr(e, "first") else (e[0], e[1])
            adj[a].append(b)
            adj[b].append(a)
        return adj

    def _seed_branches(self, fixed, base_y, gap, iters):
        """Best attempt at semi-optimal seeding for fd. Each rect position becomes mean
        of its neighbors over `iters` iterations. Kind of like KNN clustering algorithm"""
        adj = self._rect_adjacency()
        x = {i: self.rs[i].getCentreX() for i in range(len(self._rect_objs))}

        #bfs from backbone and set x to backbone x - save depth
        depth = {i: 0 for i in fixed}
        frontier = list(fixed)
        while frontier:
            nxt = []
            for u in frontier:
                for v in adj[u]:
                    if v not in depth:
                        depth[v] = depth[u] + 1
                        x[v] = x[u]
                        nxt.append(v)
            frontier = nxt

        #pull free rects to mean x of neighbors
        free = [i for i in depth if i not in fixed]
        for _ in range(iters):
            for i in free:
                nb = adj[i]
                if nb:
                    x[i] = sum(x[j] for j in nb) / len(nb)

        #update positions
        for i in free:
            self.rs[i].moveCentreX(x[i])
            self.rs[i].moveCentreY(base_y + depth[i] * gap)

    def get_segment_coordinates(self, node):
        """Gets rect centers for every rect in node"""
        return [(self.rs[idx].getCentreX(), self.rs[idx].getCentreY())
                for idx in self.node_to_rects[node]]

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
        self._fd.setAvoidNodeOverlaps(True)
        self._fd.run()
        return self._fd

    def close(self):
        """
        Drop all our C++ refs so they can be garbage collected
        """
        self._fd = None
        self._pre = None
        self._locks = None
        self.rs = None
        self.es = None
        self.node_to_rects.clear()
        self._rect_objs.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
