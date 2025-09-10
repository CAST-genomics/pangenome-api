import cppyy

# Load OGDF headers
from ogdf_python import *
cppinclude("ogdf/energybased/FMMMLayout.h")
cppinclude("ogdf/energybased/fmmm/FMMMOptions.h")
cppinclude("ogdf/energybased/fmmm/NodeAttributes.h")
cppinclude("ogdf/basic/GraphAttributes.h")
cppinclude("ogdf/basic/Graph.h")
cppyy.cppdef("""
#include <ogdf/energybased/FMMMLayout.h>
using namespace ogdf;

// Define a subclass or a patch with a setter
class FMMMLayoutWithSetter : public FMMMLayout {
public:
    void setInitialPlacementForces(FMMMOptions::InitialPlacementForces f) {
        m_initialPlacementForces = f;
    }
};
""")

# Use namespaces
cppyy.cppdef("using namespace ogdf;")

# Construct the graph
G = cppyy.gbl.ogdf.Graph()
GA = cppyy.gbl.ogdf.GraphAttributes(G,
    cppyy.gbl.ogdf.GraphAttributes.nodeGraphics |
    cppyy.gbl.ogdf.GraphAttributes.edgeGraphics |
    cppyy.gbl.ogdf.GraphAttributes.nodeLabel |
    cppyy.gbl.ogdf.GraphAttributes.edgeStyle |
    cppyy.gbl.ogdf.GraphAttributes.nodeStyle |
    cppyy.gbl.ogdf.GraphAttributes.nodeId
)

# Add some nodes and edges
v1 = G.newNode()
v2 = G.newNode()
G.newEdge(v1, v2)

# Set initial positions
GA.x[v1] = 100.0
GA.y[v1] = 200.0
GA.x[v2] = 300.0
GA.y[v2] = 400.0

print("Before layout:")
for v in G.nodes:
    print(f"Node {v.index()} at ({GA.x(v)}, {GA.y(v)})")

# Configure FMMMLayout
fmmm = cppyy.gbl.ogdf.FMMMLayout()
fmmm.useHighLevelOptions(True)
fmmm.unitEdgeLength(15.0)
fmmm.setInitialPlacementForces(cppyy.gbl.ogdf.FMMMOptions.InitialPlacementForces.KeepPositions)

# Run layout
fmmm.call(GA)

print("\nAfter layout:")
for v in G.nodes:
    print(f"Node {v.index()} at ({GA.x(v)}, {GA.y(v)})")