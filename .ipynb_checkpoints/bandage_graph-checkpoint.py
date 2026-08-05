"""
Classes for drawing the GFA as a graph
"""

# Standard imports
import math
import json
import subprocess
import pysam
import statistics
import numpy as np

data_path = subprocess.check_output(
    ["git", "config", "--get", "data.path"], text=True
).strip()

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
assembly_metadata_v1 = f"{data_path}/hprc_assembly_metadata_v1.0.json"
assembly_metadata_v2 = f"{data_path}/hprc_assembly_metadata_v2.0.json"
assembly_metadata_grouped_v1 = f"{data_path}/hprc_assembly_grouping_v1.0.json"
assembly_metadata_grouped_v2 = f"{data_path}/hprc_assembly_grouping_v2.0.json"
pclai_coord_naming_conventions = {"hg38": "GRCh38", "asm": "assembly"}

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
        return True

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
    # self.pgnodes[nodeName] = PGNode(nodeName, sequence, seqlen, node_assembly, node_pclai, node_range, self.m_settings)
    # self.pgnodes[nodeName] = PGNode(nodeName, sequence, seqlen, node_np_assembly, node_dup_assembly, node_default_coord, self.m_settings)
    def __init__(self, nodeName, sequence, seqlen, nd_assembly, dup_assembly, default_node_range, settings):
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
        self.m_nd_assembly = nd_assembly
        self.m_dup_assembly = dup_assembly
        self.m_assembly = self.getAssemblyList()
        self.m_assembly_metadata = self.createAssemblyMetadata()
        self.m_range = default_node_range
        # self.m_ref_start = int((node_range.split(":")[1].split("-")[0]).replace(",", ""))
        # self.m_ref_end = int((node_range.split(":")[1].split("-")[1]).replace(",", ""))
        # self.m_ref_chrom = node_range.split(":")[0]
        # self.m_average_rgb = 0

    # archived function: get pclai directly from bed files without preadding them into the walks files.
    # def GetPclaiCoords(self):
    #     if "#" in self.m_ref_chrom:
    #         return None
    #     else:
    #         pclai_tabix_file = pysam.TabixFile("/home/ec2-user/lab/pca/tabix_fit_pclai_all_samples_all_chr.sorted.bed.gz")
    #         pclai_coords = {}
    #         rgb = []
    #         for pclai_assembly in pclai_ref:
    #             x_coords = []
    #             y_coords = []
    #             r = []
    #             g = []
    #             b = []
    #             for line in pclai_tabix_file.fetch(f"{pclai_assembly}:{self.m_ref_chrom}", self.m_ref_start, self.m_ref_end):
    #                 parts = line.strip().split("\t")
    #                 x_coords.append(float(parts[3]))
    #                 y_coords.append(float(parts[4]))
    #                 r.append(int(parts[5].split(",")[0]))
    #                 g.append(int(parts[5].split(",")[1]))
    #                 b.append(int(parts[5].split(",")[2]))
    #             if len(x_coords) == 0:
    #                 pclai_coords[f"{pclai_assembly.split(':')[0]}#{pclai_assembly.split(':')[1]}"] = {
    #                     "coordinates": [],
    #                     "RGB": []
    #                 }
    #             else:
    #                 pclai_coords[f"{pclai_assembly.split(':')[0]}#{pclai_assembly.split(':')[1]}"] = {
    #                     "coordinates": [statistics.median(x_coords), statistics.median(y_coords)],
    #                     "RGB": [statistics.median(r), statistics.median(g), statistics.median(b)]
    #                 }
    #                 rgb.append((statistics.median(r), statistics.median(g), statistics.median(b)))
    #         if len(rgb)>0:
    #             print("yes")
    #             self.m_average_rgb = np.mean(rgb, axis=0).tolist()
    #         return pclai_coords
                
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
    
    # collect a list of assembly name form both the duplicated and non-duplicated assembly list
    def getAssemblyList(self):
        assembly_lst = []
        for nd_entry in self.m_nd_assembly:
            assembly = nd_entry["assembly_name"]
            # if assembly not in assembly_lst:
            assembly_lst.append(assembly)
                
        for dup_entry in self.m_dup_assembly:
            assembly = dup_entry["assembly_name"]
            # if assembly not in assembly_lst:
            assembly_lst.append(assembly)

        return assembly_lst
    
    
    def createAssemblyMetadata(self):
        """
        create m_assembly_metadata based on assembly list
        m_assembly_metadata = {
            count:{
                sex:{},
                superpopulation:{},
                population:{}
            },
            frequency:{
                sex:{},
                superpopulation:{},
                population:{}
            }
        }
        """
        if self.m_settings["VERSION"] == "v1":
            with open(assembly_metadata_v1, "r") as f:
                hprc_assembly_metadata = json.load(f)
            with open(assembly_metadata_grouped_v1, "r") as f:
                hprc_assembly_grouped = json.load(f)
        elif self.m_settings["VERSION"] == "v2":
            with open(assembly_metadata_v2, "r") as f:
                hprc_assembly_metadata = json.load(f)
            with open(assembly_metadata_grouped_v2, "r") as f:
                hprc_assembly_grouped = json.load(f)
        else:
            raise ValueError(f"invalid setting version value: {self.m_settings['VERSION']}")
        
        node_assembly_metadata = {}
        count = {"sex":{}, "superpopulation":{}, "population":{}}
        frequency = {"sex":{}, "superpopulation":{}, "population":{}}
        for category in hprc_assembly_grouped["count"]:
            for group in hprc_assembly_grouped["count"][category]:
                count[category][group] = 0
                frequency[category][group] = 0.0

        for assembly_name in self.m_assembly:
            if assembly_name == "GRCh38" or assembly_name == "CHM13":
                continue
            assembly_sex = hprc_assembly_metadata[assembly_name]["sex"]
            assembly_population = hprc_assembly_metadata[assembly_name]["population"]
            assembly_superpopulation = hprc_assembly_metadata[assembly_name]["superpopulation"]
            count["sex"][assembly_sex] += 1
            count["population"][assembly_population] += 1
            count["superpopulation"][assembly_superpopulation] += 1
        
        for category in count:
            for group in count[category]:
                frequency[category][group] = count[category][group]/(hprc_assembly_grouped["count"][category][group]*2)

        node_assembly_metadata["count"] = count
        node_assembly_metadata["frequency"] = frequency
        
        return node_assembly_metadata
    
    def getNodeAssemblies(self):
        # if self.m_settings["GRAPHTYPE"] == "mc" or self.m_settings["GRAPHTYPE"] == "MC":
        #     walks = gzip.open(f"{data_path}/hprc-v1.1-mc-grch38.walk.gz", "rt")
        #     for line in walks:
        #         walk_list = line.strip().split("\t")
        #         if walk_list[0] == self.nodeName[0:-1]:
        #             for i in range(1, len(walk_list)):
        #                 self.m_assembly.append(walk_list[i])
        #             break
        # print(self.m_assembly)
        return

class PGGraph:
    def __init__(self, gfadata, settings):
        self.gfadata = gfadata
        self.m_settings = settings
        self.pgnodes = {} # nodename->node
        self.pgedges = {} # (node1, node2)->edge
        self.pgassemblies = {} # {assembly: {min_start, max_end, contig1_name:[contig1_lenof_node,contig1_numof_node], contig2_name:[min_start, max_end, contig2_lenof_node,contig2_numof_node]}]}
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
        # if not isOwnPair:
        #     self.pgedges[(backwardEdge.getStartingNode(), backwardEdge.getEndingNode())] = backwardEdge
        node1.addEdge(forwardEdge)
        node2.addEdge(forwardEdge)
        # negNode1.addEdge(backwardEdge)
        # negNode2.addEdge(backwardEdge)

    def makeReverseComplementNodeIfNecessary(self, node):
        reverseComplementName = getOppositeNodeName(node.nodeName)
        if reverseComplementName in self.pgnodes:
            return # no need to add
        reverseComplementNode = PGNode(reverseComplementName, reverseComplement(node.nodeSequence), \
                           node.nodeLength, node.m_nd_assembly, node.m_dup_assembly, node.m_range, self.m_settings)
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
                node_nd_assembly = []
                node_dup_assembly = []
                node_default_coord = ""
                for i in range(3, len(lineParts)):
                    tag = lineParts[i].split(":")[0]
                    valString = lineParts[i][5:]
                    
                    # TODO: understand why sequence can be * or ""
                    if tag == "LN":
                        ln = int(valString)
                        if sequence in ["*", ""]:
                            seqlen = ln
                    
                    # GRCh38#0#chr1:356372-362698	HG00544#2#CM089383.1|+:>:17162-23470|.:.:.:.:.:.:.:.
                    elif tag == "na":
                        for non_dup_assembly_info in valString.split(","):
                            assembly_contig_name, coord_info, pclai_hg38, pclai_asm = non_dup_assembly_info.split("|")
                            
                            # process contig ids
                            assembly, haplo, seq_id = assembly_contig_name.split("#")
                            
                            # process assembly coordinates
                            path_strand, node_strand, coord =coord_info.split(":")
                            start_str, end_str = coord.split("-")
                            start = int(start_str)
                            end = int(end_str)
                            
                            # process pclais
                            assign_pclai = {"hg38": {}, "asm": {}}
                            for pclai in [pclai_hg38, pclai_asm]:
                                pclai_coord, pclai_x, pclai_y, pclai_r, pclai_g, pclai_b, pclai_score = pclai.split(":")
                                if pclai_x == ".":
                                    continue
                                if self.m_settings["API"] == "v3":
                                    assign_pclai[pclai_coord] = {
                                        "pclai_coord_system": pclai_coord_naming_conventions[pclai_coord],
                                        "coordinates": [float(pclai_x), float(pclai_y)],
                                        "RGB": [float(pclai_r), float(pclai_g), float(pclai_b)],
                                        "confidence_score": pclai_score
                                    }
                                else:
                                    assign_pclai[pclai_coord] = {
                                        "coordinates": [float(pclai_x), float(pclai_y)],
                                        "RGB": [float(pclai_r), float(pclai_g), float(pclai_b)],
                                        "start": start,
                                        "end": end,
                                        "percentage": 1.0
                                    }   
                                                     
                            #TODO delete this part after fixing the bug in walks file
                            ###########
                            if start == end and seqlen > 0:
                                end = start + seqlen
                            ###########
                                
                            # add assembly information to node_nd_assembly, which will be added into the json_file --> node --> assembly_list
                            if self.m_settings["PCLAI"] == "assembly" and self.m_settings["API"] != "v3":
                                node_nd_assembly.append({
                                    "assembly_name": assembly,
                                    "haplotype": haplo, 
                                    "metadata": [
                                        {
                                            "sequence_id": seq_id,
                                            "path_strand": path_strand,
                                            "node_strand": node_strand,
                                            "start": start,
                                            "end": end,
                                            "pclai": [] if assign_pclai["asm"] == {} else [assign_pclai["asm"]],
                                            "take": "yes"
                                        }
                                    ]
                                })
                            
                            elif self.m_settings["PCLAI"] == "hg38" and self.m_settings["API"] != "v3":
                                node_nd_assembly.append({
                                    "assembly_name": assembly,
                                    "haplotype": haplo, 
                                    "metadata": [
                                        {
                                            "sequence_id": seq_id,
                                            "path_strand": path_strand,
                                            "node_strand": node_strand,
                                            "start": start,
                                            "end": end,
                                            "pclai": [] if assign_pclai["hg38"] == {} else [assign_pclai["hg38"]],
                                            "take": "yes"
                                        }
                                    ]
                                })
                            
                            else:
                                node_nd_assembly.append({
                                    "assembly_name": assembly,
                                    "haplotype": haplo, 
                                    "metadata": [
                                        {
                                            "sequence_id": seq_id,
                                            "path_strand": path_strand,
                                            "node_strand": node_strand,
                                            "start": start,
                                            "end": end,
                                            "pclai_hg38":  assign_pclai["hg38"],
                                            "pclai_asm": assign_pclai["asm"],
                                            "take": "yes"
                                        }
                                    ]
                                })                                                        
                            
                            
                            # udpate pggraph.pgassemblies, which will be used to determine the range of the node, and whether a duplicated node will be taken or not
                            # self.pgassemblies = {assembly: {contig1_name:[min_start, max_end, contig1_lenof_node,contig1_numof_node], contig2_name:[min_start, max_end, contig2_lenof_node,contig2_numof_node]}]}
                            
                            # if this assembly was not already recorded in pggraph.pgassemblies, we add it in
                            if f"{assembly}#{haplo}" not in self.pgassemblies:
                                self.pgassemblies[f"{assembly}#{haplo}"] = {seq_id: [start, end, seqlen, 1]}
                            
                            # if this assembly is already recorded in pggraph.pgassemblies, we will update the minimum start locus, maximum end locus, and contig info accordingly
                            else:
                                if seq_id in self.pgassemblies[f"{assembly}#{haplo}"]:
                                    self.pgassemblies[f"{assembly}#{haplo}"][seq_id][2] += seqlen
                                    self.pgassemblies[f"{assembly}#{haplo}"][seq_id][3] += 1
                                    
                                    if start < self.pgassemblies[f"{assembly}#{haplo}"][seq_id][0]:
                                        self.pgassemblies[f"{assembly}#{haplo}"][seq_id][0] = start
                                    if end > self.pgassemblies[f"{assembly}#{haplo}"][seq_id][1]:
                                        self.pgassemblies[f"{assembly}#{haplo}"][seq_id][1] = end
                                else:
                                    self.pgassemblies[f"{assembly}#{haplo}"][seq_id] = [start, end, seqlen, 1]
                                
                    
                    # GRCh38#0#chr1:356372-362698	HG03521#2|JBIREG010000046.1$+:>:1218553-1228497$hg38:.:.:.:.:.:.$asm:.:.:.:.:.:.|JBIREG010000050.1$+:>:108575287-108585205$.:.:.:.:.:.:.:.
                    elif tag == "da":
                        # we only consider when we have duplicated coordinates. If we do not, the duplicated assembly list will be an empty dict
                        if valString != ".":
                            for dup_assembly_info in valString.split(","):
                                dup_assembly_info_parts = dup_assembly_info.split("|")
                                assembly, haplo = dup_assembly_info_parts[0].split("#")
                                duplicated_coords = dup_assembly_info_parts[1:]
                                metadata = []
                                
                                for duplicated_coord in duplicated_coords:
                                    seq_id, coord_info, pclai_hg38, pclai_asm = duplicated_coord.split("$")
                                    path_strand, node_strand, coord =coord_info.split(":")
                                    start_str, end_str = coord.split("-")
                                    start = int(start_str)
                                    end = int(end_str)

                                    assign_pclai = {"hg38": {}, "asm": {}}
                                    for pclai in [pclai_hg38, pclai_asm]:
                                        pclai_coord, pclai_x, pclai_y, pclai_r, pclai_g, pclai_b, pclai_score = pclai.split(":")
                                        if pclai_x == ".":
                                            continue
                                        if self.m_settings["API"] == "v3":
                                            assign_pclai[pclai_coord] = {
                                                "pclai_coord_system": pclai_coord_naming_conventions[pclai_coord],
                                                "coordinates": [float(pclai_x), float(pclai_y)],
                                                "RGB": [float(pclai_r), float(pclai_g), float(pclai_b)],
                                                "confidence_score": pclai_score
                                            }
                                        else:
                                            assign_pclai[pclai_coord] = {
                                                "coordinates": [float(pclai_x), float(pclai_y)],
                                                "RGB": [float(pclai_r), float(pclai_g), float(pclai_b)],
                                                "start": start,
                                                "end": end,
                                                "percentage": 1.0
                                            }       
                                                            
                                    #TODO delete this part after fixing the bug in walks file
                                    ###########
                                    if start == end and seqlen > 0:
                                        end = start + seqlen
                                    ###########
                                        
                                    # add assembly information to node_nd_assembly, which will be added into the json_file --> node --> assembly_list
                                    if self.m_settings["PCLAI"] == "assembly" and self.m_settings["API"] != "v3":
                                        metadata_entry = {
                                            "sequence_id": seq_id,
                                            "path_strand": path_strand,
                                            "node_strand": node_strand,
                                            "start": start,
                                            "end": end,
                                            "pclai": [] if assign_pclai["asm"] == {} else [assign_pclai["asm"]],
                                            "take": "no"
                                        }
                                    
                                    elif self.m_settings["PCLAI"] == "hg38" and self.m_settings["API"] != "v3":
                                        metadata_entry = {
                                            "sequence_id": seq_id,
                                            "path_strand": path_strand,
                                            "node_strand": node_strand,
                                            "start": start,
                                            "end": end,
                                            "pclai": [] if assign_pclai["hg38"] == {} else [assign_pclai["hg38"]],
                                            "take": "no"
                                        } 
                                    
                                    else:
                                        metadata_entry = {
                                            "sequence_id": seq_id,
                                            "path_strand": path_strand,
                                            "node_strand": node_strand,
                                            "start": start,
                                            "end": end,
                                            "pclai_hg38": assign_pclai["hg38"],
                                            "pclai_asm": assign_pclai["asm"],
                                            "take": "no"
                                        }
                                    
                                    metadata.append(metadata_entry)
                                    
                                node_dup_assembly.append({
                                    "assembly_name": assembly,
                                    "haplotype": haplo, 
                                    "metadata": metadata
                                })
                                
                    elif tag == "SN":
                        node_default_coord = valString
                        
                
                # Check node orientation
                # If not given, assume "+"
                lastChar = nodeName[-1]
                if lastChar not in ["+", "-"]:
                    nodeName += "+"
                    
                # Add to list of nodes
                # self.pgnodes[nodeName] = PGNode(nodeName, sequence, seqlen, node_assembly, node_pclai, node_range, self.m_settings)
                self.pgnodes[nodeName] = PGNode(nodeName, sequence, seqlen, node_nd_assembly, node_dup_assembly, node_default_coord, self.m_settings)
                # self.pgnodes[nodeName].getNodeAssemblies()

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

"""
### For debugging - show how to access the node coordinates ####

for node in self.pgnodes.values():
    # if node.isDrawn():
    print(node.nodeName)
    print(node.GetOgdfNode())
    # if node.inOgdf():
    for ogdf_node in node.GetOgdfNode().m_ogdfNodes:
        print("%s, %s"%(self.m_graphAttributes.x(ogdf_node), \
            self.m_graphAttributes.y(ogdf_node)))
        print("hi")
"""