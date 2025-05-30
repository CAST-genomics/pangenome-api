"""
Classes for drawing the GFA as a graph
"""

# Standard imports
import math

# OGDF
from ogdf_python import *
cppinclude("ogdf/energybased/FMMMLayout.h")

# # Package imports
# from graph_plotter import *

selectionThickness = 1.0
# averageNodeWidth = FloatSetting(5.0, 0.5, 1000.0);
averageNodeWidth = 5.0
# edgeWidth = FloatSetting(1.5, 0.1, 100);
edgeWidth = 1.5

def getLengthFromCigar(cigar):
    return 0 # TODO. not sure we need CIGAR?

def getOppositeNodeName(nodeName):
    lastChar = nodeName[-1]
    if lastChar == "-":
        return nodeName[:-1] + "+"
    else: return nodeName[:-1] + "-"

def reverseComplement(sequence):
    if sequence == "*": return sequence
    sequence = sequence.upper()
    rev = sequence[::-1]
    newseq = ""
    for i in range(len(rev)):
        if rev[i] == "A":
            newseq += "T"
        elif rev[i] == "T":
            newseq += "A"
        elif rev[i] == "C":
            newseq += "C"
        elif rev[i] == "G":
            newseq += "G"
        else: newseq += "N"
    return newseq

class OgdfNode:
    def __init__(self):
        self.m_ogdfNodes = []

    def addOgdfNode(self, ogdf_node):
        self.m_ogdfNodes.append(ogdf_node)

    def GetLast(self):
        if len(self.m_ogdfNodes) == 0:
            return 0
        else:
            return self.m_ogdfNodes[-1]

    def GetFirst(self):
        if len(self.m_ogdfNodes) == 0:
            return 0
        else:
            return self.m_ogdfNodes[0]

class PGEdge:
    def __init__(self, node1, node2):
        self.startingNode = node1
        self.endingNode = node2
        self.reverse_complement = None
        self.overlap = None
        self.m_drawn = False
        self.m_graphics_item_edge = 0

    def isDrawn(self):
        return self.m_drawn

    def DetermineIfDrawn(self):
        self.m_drawn = self.EdgeIsVisible()

    def EdgeIsVisible(self):
        drawEdge = (self.startingNode.isDrawn() or \
                self.startingNode.getReverseComplement().isDrawn()) and \
            (self.endingNode.isDrawn() or self.endingNode.getReverseComplement().isDrawn())
        if not drawEdge:
            return False
        return self.isPositiveEdge()

    def isPositiveEdge(self):
        if self.startingNode.isPositiveNode() and \
            self.endingNode.isPositiveNode():
            return True
        if (not self.startingNode.isPositiveNode()) and \
            (not self.endingNode.isPositiveNode()):
            return False
        if self == self.getReverseComplement():
            return True
        # otherwise choose one arbitrarily
        return self.startingNode.nodeName > \
            self.getReverseComplement().startingNode.nodeName

    def getStartingNode(self):
        return self.startingNode

    def getEndingNode(self):
        return self.endingNode

    def setReverseComplement(self, rcnode):
        self.reverse_complement = rcnode

    def getReverseComplement(self):
        return self.reverse_complement

    def setOverlap(self, overlap):
        self.overlap = overlap

    def SetGraphicsItemEdge(self, graphics_item_edge):
        self.m_graphics_item_edge = graphics_item_edge
        
    def GetGraphicsItemEdge(self):
        return self.m_graphics_item_edge

class PGNode:
    def __init__(self, nodeName, sequence, seqlen, assembly, range, settings):
        self.nodeName = nodeName
        self.nodeSequence = sequence
        self.nodeLength = seqlen
        self.m_settings = settings
        self.reverse_complement_node = None
        self.edges = []
        self.m_ogdfNode = 0
        self.m_drawn = False
        self.m_graphics_item_node = 0
        self.m_textx = 0
        self.m_texty = 0
        self.m_assembly = assembly
        self.m_range = range

    def GetOgdfNode(self):
        return self.m_ogdfNode

    def GetLength(self):
        return self.nodeLength
    
    def inOgdf(self):
        return self.m_ogdfNode != 0

    def thisOrReverseComplementInOgdf(self):
        return self.inOgdf() or self.getReverseComplement().inOgdf()
    
    def setReverseComplement(self, node):
        self.reverse_complement_node = node

    def getReverseComplement(self):
        return self.reverse_complement_node

    def getEdges(self):
        return self.edges

    def addEdge(self, edge):
        self.edges.append(edge)

    def GetDrawnNodeLength(self):
        if self.m_settings["DEBUG_SMALL_GRAPHS"]:
            drawnNodeLength = self.GetLength() # use raw length
        else:
            drawnNodeLength = self.m_settings["NODELENPERMB"] * \
                self.GetLength()/1000000
        if drawnNodeLength < self.m_settings["MINNODELENGTH"]:
            return self.m_settings["MINNODELENGTH"]
        else:
            return drawnNodeLength

    def GetNumOgdfGraphEdges(self, drawnNodeLength):
        numGraphEdges = math.ceil(drawnNodeLength/self.m_settings["NODESEGLEN"])
        if numGraphEdges <= 0:
            return 1
        else: return numGraphEdges

    def isPositiveNode(self):
        return self.nodeName.endswith("+")

    def setAsDrawn(self):
        self.m_drawn = True

    def isDrawn(self):
        return self.m_drawn

    def SetOgdfNode(self, ogdf_node):
        self.m_ogdfNode = ogdf_node

    def SetGraphicsItemNode(self, graphics_item_node):
        self.m_graphics_item_node = graphics_item_node

    def GetGraphicsItemNode(self):
        return self.m_graphics_item_node

    def hasGraphicsItem(self):
        return self.m_graphics_item_node != 0

class PGGraph:
    def __init__(self, gfadata, settings):
        self.gfadata = gfadata
        self.m_settings = settings
        self.pgnodes = {} # nodename->node
        self.pgedges = {} # (node1, node2)->edge
        self.load_success, self.load_msg = self.LoadGraphFromGFA()
        self.m_ogdfGraph = ogdf.Graph()
        self.m_edgeArray = ogdf.EdgeArray["double"](self.m_ogdfGraph)
        self.m_graphAttributes = ogdf.GraphAttributes(self.m_ogdfGraph, \
            ogdf.GraphAttributes.all)
        
    def createEdge(self, node1name, node2name, overlap):
        node1Opposite = getOppositeNodeName(node1name)
        node2Opposite = getOppositeNodeName(node2name)

        # Quit if any of these nodes don't exist
        for name in [node1name, node2name, node1Opposite, node2Opposite]:
            if name not in self.pgnodes:
                return

        # Quit if the edge already exists
        node1 = self.pgnodes[node1name]
        node2 = self.pgnodes[node2name]
        negNode1 = self.pgnodes[node1Opposite]
        negNode2 = self.pgnodes[node2Opposite]
        edges = node1.getEdges()
        for i in range(len(edges)):
            if edges[i].getStartingNode() == node1 and \
               edges[i].getEndingNode() == node2:
                return

        isOwnPair = (node1 == negNode2 and node2 == negNode1)

        forwardEdge = PGEdge(node1, node2)
        if isOwnPair:
            backwardEdge = forwardEdge
        else:
            backwardEdge = PGEdge(negNode2, negNode1)
        forwardEdge.setReverseComplement(backwardEdge)
        backwardEdge.setReverseComplement(forwardEdge)
        forwardEdge.setOverlap(overlap)
        backwardEdge.setOverlap(overlap)
        self.pgedges[(forwardEdge.getStartingNode(), forwardEdge.getEndingNode())] = forwardEdge
        if not isOwnPair:
            self.pgedges[(backwardEdge.getStartingNode(), backwardEdge.getEndingNode())] = backwardEdge
        node1.addEdge(forwardEdge)
        node2.addEdge(forwardEdge)
        negNode1.addEdge(backwardEdge)
        negNode2.addEdge(backwardEdge)

    def makeReverseComplementNodeIfNecessary(self, node):
        reverseComplementName = getOppositeNodeName(node.nodeName)
        if reverseComplementName in self.pgnodes:
            return # no need to add
        reverseComplementNode = PGNode(reverseComplementName, reverseComplement(node.nodeSequence), \
                           node.nodeLength, node.m_assembly, node.m_range, self.m_settings)
        self.pgnodes[reverseComplementName] = reverseComplementNode

    def pointEachNodeToItsReverseComplement(self):
        for node in self.pgnodes:
            if node[-1] == "+":
                positiveNode = self.pgnodes[node]
                negativeNode = self.pgnodes[getOppositeNodeName(node)]
                positiveNode.setReverseComplement(negativeNode)
                negativeNode.setReverseComplement(positiveNode)

    def LoadGraphFromGFA(self):
        """
        Based on https://github.com/rrwick/Bandage/blob/main/graph/assemblygraph.cpp#L564
        """
        # Initialize start/end nodes of edges
        edgeStartingNodeNames = []
        edgeEndingNodeNames = []
        edgeOverlaps = []
        gfafile = open(self.gfadata, "r")
        for line in gfafile:
            if type(line)==str:
                lineParts = line.strip().split("\t")
            else:
                lineParts = line.decode('utf8').strip().split("\t")
            # Lines that begin with "H" are header
            # We skip them for now. In future could parse
            # options from the header
            if lineParts[0] == "H":
                pass

            # Lines beginning with "S" are sequence (node) lines.
            if lineParts[0] == "S":
                if len(lineParts) < 3:
                    return False, "ERROR: malformatted 'S' line: %s"%line
                nodeName = lineParts[1]
                sequence = lineParts[2]
                # Parse tags
                seqlen = len(sequence)
                node_assembly = ""
                node_range = ""
                for i in range(3, len(lineParts)):
                    tag = lineParts[i].split(":")[0]
                    valString = lineParts[i].split(":")[2]
                    if tag == "LN":
                        ln = int(valString)
                        if sequence in ["*", ""]:
                            seqlen = ln
                    if tag == "SN":
                        if valString[0:3] == "chr":
                            node_assembly = "GRCh38"
                        else:
                            node_assembly = valString
                    if node_assembly == "GRCh38" and tag == "gr":
                        node_range = valString[1:]+":"+lineParts[i].split(":")[3]
                # Check node orientation
                # If not given, assume "+"
                lastChar = nodeName[-1]
                if lastChar not in ["+", "-"]:
                    nodeName += "+"
                    
                # Add to list of nodes
                self.pgnodes[nodeName] = PGNode(nodeName, sequence, seqlen, node_assembly, node_range, self.m_settings)

            # Lines beginning with "L" are link (edge) lines
            """
            Edges aren't made now, in case their sequence hasn't yet been specified.
            Instead, we save the starting and ending nodes and make the edges after
            we're done looking at the file.
            """
            if lineParts[0] == "L":
                if len(lineParts) < 6:
                    return False, "ERROR: malformated 'L' line: %s"%line
                # Parts 1 and 3 hold the node names and parts 2 and 4 hold the corresponding +/-
                startingNode = lineParts[1] + lineParts[2]
                endingNode = lineParts[3] + lineParts[4]
                edgeStartingNodeNames.append(startingNode)
                edgeEndingNodeNames.append(endingNode)

                # Part 5 has CIGAR for overlap
                cigar = lineParts[5]
                if cigar == "*":
                    edgeOverlaps.append(0)
                else:
                    edgeOverlaps.append(getLengthFromCigar(cigar))

        # Pair up reverse complements, creating them if necessary
        existing_nodes = list(self.pgnodes.keys())
        for key in existing_nodes:
            self.makeReverseComplementNodeIfNecessary(self.pgnodes[key])
        self.pointEachNodeToItsReverseComplement()

        # Create all of the edges
        for i in range(len(edgeStartingNodeNames)):
            self.createEdge(edgeStartingNodeNames[i], \
                    edgeEndingNodeNames[i], \
                    edgeOverlaps[i])

        if len(self.pgnodes.keys()) == 0:
            return False, "ERROR: No nodes in graph"

        return True, "Success"

    def BuildOGDFGraph(self):
        # Determine which nodes to draw and add them to the graph
        for nodename in self.pgnodes.keys():
            if self.pgnodes[nodename].isPositiveNode():
                self.pgnodes[nodename].setAsDrawn()
        # Add nodes to the graph
        for nodename in self.pgnodes.keys():
            if self.pgnodes[nodename].isDrawn() and \
               not self.pgnodes[nodename].thisOrReverseComplementInOgdf():
                self.AddNodeToOGDFGraph(nodename)
        # Add edges to the graph
        for edge in self.pgedges.values():
            edge.DetermineIfDrawn()
            if edge.isDrawn():
                self.AddEdgeToOGDFGraph(edge)

    def AddEdgeToOGDFGraph(self, edge):
        # Get first Ogdf node
        firstEdgeOgdfNode = 0
        if edge.startingNode.inOgdf():
            firstEdgeOgdfNode = edge.startingNode.GetOgdfNode().GetLast()
        elif edge.startingNode.getReverseComplement().inOgdf():
            firstEdgeOgdfNode = edge.startingNode.getReverseComplement().GetOgdfNode().GetFirst()
        else:
            return # Starting node or its reverse complement isn't in OGDF
        # print(f"firstEdgeOgdfNode is {firstEdgeOgdfNode}")

        # Get second Ogdf node
        secondEdgeOgdfNode = 0
        if edge.endingNode.inOgdf():
            secondEdgeOgdfNode = edge.endingNode.GetOgdfNode().GetFirst()
        elif edge.endingNode.getReverseComplement().inOgdf():
            secondEdgeOgdfNode = edge.endingNode.getReverseComplement().GetOgdfNode().GetLast()
        else:
            return # Ending node or its reverse complement isn't in OGDF
        # print(f"secondEdgeOgdfNode is {secondEdgeOgdfNode}")

        # Skip if edge connects a single-segment node to itself
        drawnLength = edge.startingNode.GetDrawnNodeLength()
        if (edge.startingNode == edge.endingNode) and \
            (edge.startingNode.GetNumOgdfGraphEdges(drawnLength)==1):
            return

        # If we made it here, add the edge
        newEdge = self.m_ogdfGraph.newEdge(firstEdgeOgdfNode, secondEdgeOgdfNode)
        self.m_edgeArray[newEdge] = self.m_settings["EDGELEN"]

    def AddNodeToOGDFGraph(self, nodename):
        node = self.pgnodes[nodename]

        # Check if we need to draw
        if node.thisOrReverseComplementInOgdf(): return
        
        # Create a new OgdfNode node
        m_ogdfNode = OgdfNode()

        # Each GFA node will correspond to multiple OGDF nodes
        # This allows drawing nodes as lines whose lengths
        # correspond to sequence length
        drawnNodeLength = node.GetDrawnNodeLength()
        numberOfGraphEdges = node.GetNumOgdfGraphEdges(drawnNodeLength)
        numberOfGraphNodes = numberOfGraphEdges + 1
        drawnLengthPerEdge = drawnNodeLength / numberOfGraphEdges

        newNode = 0
        previousNode = 0
        for i in range(numberOfGraphNodes):
            newNode = self.m_ogdfGraph.newNode()
            m_ogdfNode.addOgdfNode(newNode)
            if i > 0:
                newEdge = self.m_ogdfGraph.newEdge(previousNode, newNode)
                self.m_edgeArray[newEdge] = drawnLengthPerEdge
            previousNode = newNode

        # Set OgdfNode for the node object
        node.SetOgdfNode(m_ogdfNode)

    def LayoutGraph(self):
        # TODO may set additional options see
        # https://github.com/rrwick/Bandage/blob/main/program/graphlayoutworker.cpp#L34
        fmmm = ogdf.FMMMLayout()
        fmmm.call(self.m_graphAttributes, self.m_edgeArray)

        #### For debugging - show how to access the node coordinates ####
        
        # for node in self.pgnodes.values():
        #     # if node.isDrawn():
        #     print(node.nodeName)
        #     print(node.GetOgdfNode())
        #     # if node.inOgdf():
        #     for ogdf_node in node.GetOgdfNode().m_ogdfNodes:
        #         print("%s, %s"%(self.m_graphAttributes.x(ogdf_node), \
        #             self.m_graphAttributes.y(ogdf_node)))
        #         print("hi")