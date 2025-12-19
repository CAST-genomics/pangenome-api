import bandage_graph
import json

settings_dict = {
    'chr_input': 'chr12', 
    'start_loc_input': 21023100, 
    'end_loc_input': 21023150, 
    'graph_type': 'minigraph', 
    'EXACT_OVERLAP': True, 
    'DEBUG_SMALL_GRAPHS': False, 
    'MINNODELENGTH': 5.0, 
    'NODESEGLEN': 20.0, 
    'EDGELEN': 5.0, 
    'NODELENPERMB': 1000.0, 
    'NAMELABEL': False
}
gfa_output = "cache/minigraph/subgraph_chr12_21023100_21023150.gfa"
pggraph = bandage_graph.PGGraph(str(gfa_output), settings_dict)
pggraph.BuildOGDFGraph()
pggraph.LayoutGraph()

data = {
    "locus": "chr12:21023100-21023150",
    "node": {},
    "edge": [],
    "sequence": {}
}

sequence = {}
node = {}
edges = []

for pgnodes in pggraph.pgnodes.values():
    if pgnodes.isDrawn():
        node_info = {}
        node_info["name"] = pgnodes.nodeName
        node_info["length"] = pgnodes.nodeLength
        node_info["color"] = pgnodes.m_color
        sequence[pgnodes.nodeName] = pgnodes.nodeSequence
        odgf_coordinates = []
        for ogdf_node in pgnodes.GetOgdfNode().m_ogdfNodes:
            coordinates = {"x": pggraph.m_graphAttributes.x(ogdf_node), "y": pggraph.m_graphAttributes.y(ogdf_node)}
            odgf_coordinates.append(coordinates)
        node_info["odgf_coordinates"] = odgf_coordinates
        node[pgnodes.nodeName] = node_info

for node_pairs in pggraph.pgedges.keys():
    if pggraph.pgedges[node_pairs].isDrawn():
        edge = {}
        edge["starting_node"] = node_pairs[0].nodeName
        edge["ending_node"] = node_pairs[1].nodeName
        edge["color"] = pggraph.pgedges[node_pairs].m_color
        edges.append(edge)
    

data["sequence"] = sequence
data["node"] = node
data["edge"] = edges
    
with open("small_chr12_21023100_21023150.JSON", "w") as output:
    json.dump(data, output, indent=4)