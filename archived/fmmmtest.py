import bandage_graph
from ogdf_python import *
cppinclude("ogdf/energybased/FMMMLayout.h")
cppinclude("ogdf/energybased/fmmm/FMMMOptions.h")
cppinclude("ogdf/energybased/fmmm/NodeAttributes.h")
cppinclude("ogdf/basic/GraphAttributes.h")
cppinclude("ogdf/basic/Graph.h")

def LayoutGraph1(pggraph):
    # print(dir(pggraph.m_graphAttributes))
    fmmm1 = ogdf.FMMMLayout()
    fmmm1.newInitialPlacement(False)
    fmmm1.call(pggraph.m_graphAttributes, pggraph.m_edgeArray)
    print("Before Adjustment")
    for pgnodes in pggraph.pgnodes.values():
        if pgnodes.isDrawn():
            for ogdf_node in pgnodes.GetOgdfNode().m_ogdfNodes:
                coordinates = {"x":pggraph.m_graphAttributes.x(ogdf_node), "y": pggraph.m_graphAttributes.y(ogdf_node)}
                print(coordinates)
    print("\nAdjusted")
    for pgnodes in pggraph.pgnodes.values():
        if pgnodes.isDrawn() and pgnodes.m_assembly == "GRCh38":
            for ogdf_node in pgnodes.GetOgdfNode().m_ogdfNodes:
                pggraph.m_graphAttributes.y[ogdf_node] = 100.0
                coordinates = {"x":pggraph.m_graphAttributes.x(ogdf_node), "y": pggraph.m_graphAttributes.y(ogdf_node)}
    
    for pgnodes in pggraph.pgnodes.values():
        if pgnodes.isDrawn():
            for ogdf_node in pgnodes.GetOgdfNode().m_ogdfNodes:
                coordinates = {"x":pggraph.m_graphAttributes.x(ogdf_node), "y": pggraph.m_graphAttributes.y(ogdf_node)}
                print(coordinates)
    
    fmmm2 = ogdf.FMMMLayout()
    # print(dir(fmmm2))
    fmmm2.useHighLevelOptions(True)
    # print(dir(ogdf.FMMMOptions))
    # print(dir(fmmm2))
    fmmm2.initialPlacementMult(ogdf.FMMMOptions.InitialPlacementMult.Advanced)
    fmmm2.initialPlacementForces(False)
    fmmm2.newInitialPlacement(False)
    # fmmm2.initialPlacementForces(ogdf.FMMMOptions.initialPlacementForces.KeepPositions)
    fmmm2.call(pggraph.m_graphAttributes, pggraph.m_edgeArray)
    print("\nAfter Adjustment")
    for pgnodes in pggraph.pgnodes.values():
        if pgnodes.isDrawn():
            for ogdf_node in pgnodes.GetOgdfNode().m_ogdfNodes:
                coordinates = {"x":pggraph.m_graphAttributes.x(ogdf_node), "y": pggraph.m_graphAttributes.y(ogdf_node)}
                print(coordinates)

settings_dict = {
    'chr_input': 'chr1', 
    'start_loc_input': 200000, 
    'end_loc_input': 201000, 
    'graph_type': 'minigraph', 
    'EXACT_OVERLAP': True, 
    'DEBUG_SMALL_GRAPHS': False, 
    'MINNODELENGTH': 5.0, 
    'NODESEGLEN': 20.0, 
    'EDGELEN': 5.0, 
    'NODELENPERMB': 1000.0, 
    'NAMELABEL': False
}

gfa_output = "cache/minigraph/subgraph_chr1_200000_201000.gfa"
pggraph = bandage_graph.PGGraph(str(gfa_output), settings_dict)
pggraph.BuildOGDFGraph()
LayoutGraph1(pggraph)
