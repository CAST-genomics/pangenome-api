"""
Classes for plotting the graph with plotly
"""
import bandage_graph
import json
import math
import tempfile

class GraphicsItemEdge:
    def __init__(self, edge, settings):
        self.m_edge = edge
        self.m_startingLocation = None
        self.m_beforeStartingLocation = None
        self.m_endingLocation = None
        self.m_afterEndingLocation = None
        self.m_controlPoint1 = None
        self.m_controlPoint2 = None 
        self.m_settings = settings
        self.shape = self.GetShape()
    
    def setControlPointLocations(self):
        starting_node = self.m_edge.startingNode
        ending_node = self.m_edge.endingNode

        if starting_node.hasGraphicsItem():
            self.m_startingLocation = starting_node.GetGraphicsItemNode().getLast()
            self.m_beforeStartingLocation = starting_node.GetGraphicsItemNode().getSecondLast()
        elif starting_node.getReverseComplement().hasGraphicsItem():
            self.m_startingLocation = starting_node.getReverseComplement().GetGraphicsItemNode().getFirst()
            self.m_beforeStartingLocation = starting_node.getReverseComplement().GetGraphicsItemNode().getSecond()
        else: pass

        if ending_node.hasGraphicsItem():
            self.m_endingLocation = ending_node.GetGraphicsItemNode().getFirst()
            self.m_afterEndingLocation = ending_node.GetGraphicsItemNode().getSecond()
        elif ending_node.getReverseComplement().hasGraphicsItem():
            self.m_endingLocation = ending_node.getReverseComplement().GetGraphicsItemNode().getLast()
            self.m_afterEndingLocation = ending_node.getReverseComplement().GetGraphicsItemNode().getSecondLast()
        else: pass

    def GetEdgeDistance(self):
        return math.sqrt((self.m_startingLocation[0]-self.m_endingLocation[0]) **2 + \
            (self.m_startingLocation[1]-self.m_endingLocation[1])**2)

    def extendLine(self, start, end, extensionLength):
        extensionRatio = extensionLength/self.GetEdgeDistance()
        difference = [(end[0]-start[0])*extensionRatio, (end[1]-start[1])*extensionRatio]
        return [end[0]+difference[0], end[1]+difference[1]]

    def GetShape(self):
        self.setControlPointLocations()

        starting_node = self.m_edge.startingNode
        ending_node = self.m_edge.endingNode

        edge_distance = self.GetEdgeDistance()
        extensionLength = self.m_settings["EDGELEN"]
        if extensionLength > edge_distance/2:
            extensionLength = edge_distance/2
        self.m_controlPoint1 = self.extendLine(self.m_beforeStartingLocation, self.m_startingLocation, extensionLength)
        self.m_controlPoint2 = self.extendLine(self.m_afterEndingLocation, self.m_endingLocation, extensionLength)

        # If edge connects a node to itself, need special edge
        if starting_node == ending_node:
            # TODO
            return None

        # If single mode and edge connects node to its reverse
        # complement, also need special edge
        if starting_node == ending_node.getReverseComplement():
            # TODO
            return None

        # Else just a single cubic Bezier curve
        path = "M %s %s"%(self.m_startingLocation[0], self.m_startingLocation[1])
        path += " C %s %s %s %s %s %s"%(self.m_controlPoint1[0], self.m_controlPoint2[1],
            self.m_controlPoint2[0], self.m_controlPoint2[1],
            self.m_endingLocation[0], self.m_endingLocation[1])
        
        color = "red"
        if starting_node.m_color != "" and ending_node.m_color != "":
            color = "black"
         # Return the path shape
        shape = dict(
            type="path",
            path=path,
            line_color=color,
            line_width=2
        )
        return shape       

class GraphicsItemNode:
    def __init__(self, node, GA, settings):
        self.m_node = node
        self.m_graphAttributes = GA
        self.m_settings = settings
        self.points = []
        self.shape = self.GetShape() 
        self.max_x = max([item[0] for item in self.points])
        self.max_y = max([item[1] for item in self.points])

    def GetShape(self):
        self.points = []
        # First get all points in the pagh
        for ogdf_node in self.m_node.GetOgdfNode().m_ogdfNodes:
            self.points.append((self.m_graphAttributes.x(ogdf_node), self.m_graphAttributes.y(ogdf_node)))
        if len(self.points) < 2: return None
        # Now turn into an SVG path
        path = "M %s %s"%(self.points[0][0], self.points[0][1])
        for i in range(1, len(self.points)):
            path = path + " L %s %s"%(self.points[i][0], self.points[i][1])
        self.m_node.m_textx = (self.points[0][0] + self.points[-1][0])/2
        self.m_node.m_texty = (self.points[0][1] + self.points[-1][1])/2
        # Return the path shape
        shape = dict(
            type="path",
            path=path,
            line_color="MediumPurple",
            line_width=10,
            id=self.m_node.nodeName
            # label=dict(text=self.m_node.nodeName)
        )
        return shape

    def getFirst(self):
        return self.points[0]

    def getSecond(self):
        return self.points[1]

    def getLast(self):
        return self.points[-1]

    def getSecondLast(self):
        return self.points[-2]

class GraphPlotter:
    def __init__(self, pggraph, settings):
        self.m_pggraph = pggraph
        self.max_x = 0 
        self.max_y = 0 
        self.m_settings = settings

    def BuildGraphicsItems(self):
        for node in self.m_pggraph.pgnodes.values():
            if node.isDrawn():
                graphics_item_node = GraphicsItemNode(node, self.m_pggraph.m_graphAttributes, self.m_settings)
                if graphics_item_node.max_x > self.max_x:
                    self.max_x = graphics_item_node.max_x 
                if graphics_item_node.max_y > self.max_y:
                    self.max_y = graphics_item_node.max_y
                node.SetGraphicsItemNode(graphics_item_node)
        # Then get edges
        for edge in self.m_pggraph.pgedges.values():
            if edge.isDrawn():
                graphics_item_edge = GraphicsItemEdge(edge, self.m_settings)
                edge.SetGraphicsItemEdge(graphics_item_edge)
    
    def BuildSvg(self):
        self.BuildGraphicsItems()
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as svgFile:
            svgFile.write("<svg width=\"100%%\" height=\"100%%\" viewBox=\"0 0 %s %s\" xmlns=\"http://www.w3.org/2000/svg\" preserveAspectRatio=\"xMidYMid meet\">\n"%(self.max_x*1.1, self.max_y*1.1))
            for node in self.m_pggraph.pgnodes.values():
                if node.isDrawn():
                    shape = node.GetGraphicsItemNode().GetShape()
                    if node.m_color != "":
                        color = node.m_color
                    else: 
                        color = "MediumPurple"
                    if shape is not None:
                        svgFile.write(f"\t<path class=\"{shape['id']}\" id=\"{shape['id']}\" d=\"{shape['path']}\" fill=\"none\" stroke=\"{color}\" stroke-width=\"{shape['line_width']}\"/>\n")
                        if self.m_settings["NAMELABEL"]:
                            svgFile.write(f"\t<text class=\"{shape['id']}\" font-size=\"16\" fill=\"black\">\n")
                            svgFile.write(f"\t\t<textPath class=\"{shape['id']}\" href=\"#{shape['id']}\" startOffset=\"50%\" text-anchor=\"middle\">{shape['id'][0:-1]}</textPath>")
                            svgFile.write("\t</text>")
                        svgFile.write("\t<foreignObject style=\"visibility: hidden;\">")
                        svgFile.write("\t\t<node-details>")
                        svgFile.write(f"\t\t\t<p>name: {shape['id']}</p>")
                        svgFile.write(f"\t\t\t<p>length: {node.nodeLength}</p>")
                        svgFile.write("\t\t</node-details>")
                        svgFile.write("\t</foreignObject>")
            for edge in self.m_pggraph.pgedges.values():
                if edge.isDrawn():
                    shape = edge.GetGraphicsItemEdge().GetShape()
                    if shape is not None:
                        svgFile.write(f"\t<path d=\"{shape['path']}\" fill=\"none\" stroke=\"{shape['line_color']}\" stroke-width=\"{shape['line_width']}\"/>\n")
            svgFile.write("</svg>")
        return svgFile.name
    
    # def GetGraphJSON(self):
    #     # TODO - this is just a list of SVG paths
    #     # currently plotting with plotly, but maybe will have
    #     # more control if we just plot with d3 or some other library?
    #     # plotly doesn't seem to allow interaction with shapes at least
    #     # not easily
    #     graph_shapes = self.GetGraphShapes() 
    #     fig = go.Figure()
    #     # Update axes properties
    #     fig.update_xaxes(
    #         range=[0, self.max_x*1.1],
    #         zeroline=False,
    #         showgrid=False,
    #         showticklabels=False
    #     )

    #     fig.update_yaxes(
    #         range=[0, self.max_y*1.1],
    #         zeroline=False,
    #         showgrid=False,
    #         showticklabels=False
    #     )
    #     fig.update_layout(shapes=graph_shapes, plot_bgcolor="rgba(0,0,0,0)")
    #     plotly_plot_json = json.dumps(fig.to_plotly_json(), cls=plotly.utils.PlotlyJSONEncoder)
    #     return plotly_plot_json