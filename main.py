import sys
sys.path.append('/home/ec2-user/lab')
from panCT.panct.data import Region
from panCT.panct.logging import getLogger

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import requests
import gbz_utils as gbz
from pathlib import Path
import tempfile
import os
import gfa_utils as gfa
import graph_plotter
import bandage_graph
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import json
import pysam

class Settings(BaseModel):
    chr_input: str
    start_loc_input: int
    end_loc_input: int
    graph_type: str
    DEBUG_SMALL_GRAPHS: bool
    MINNODELENGTH: float
    NODESEGLEN: float
    EDGELEN: float
    NODELENPERMB: float
    NAMELABEL: bool

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to restrict access in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mc_hg38_gbz_v1 = Path("/data/hprc-v1.1-mc-grch38.gbz")
mc_hg38_gbz_v2 = Path("/data/hprc-v2.0-mc-grch38.gbz")
minigraph_hg38_gfa_v1 = Path("/data/hprc-v1.0-minigraph-grch38.gfa")
minigraph_hg38_gfa_v2 = Path("/data/hprc-v2.0-minigraph-grch38.gfa")
mc_mapped_walks_v1 = pysam.TabixFile("/data/hprc-v1.1-mc-grch38-mapped-flattened.walk.gz")
mc_mapped_walks_v2 = None
minigraph_walks_v1 = pysam.TabixFile("/data/hprc_v1.0_minigraph_filtered_with_id.walk.gz")
minigraph_walks_v2 = pysam.TabixFile("/data/hprc_v2.0_minigraph_filtered_with_id.walk.gz")

#TODO check if all chopped node id finds a mapped unchopped node id
def SubgraphMC(query_region, gfa_preprocessed, gfa_postprocessed, reference_gbz, mc_mapped_walks, log):
    # check gbz.db file and create subgraph
    if not gbz.check_gbzfile(reference_gbz, log):
        gbz.index_gbz(reference_gbz)
    subgraph_gfa = gbz.extract_region_from_gbz(reference_gbz,query_region,"GRCh38", gfa_preprocessed)
    if subgraph_gfa is None:
        log.error("Subset GFA is None")
        return
    
    header = ""
    nodes_got_chopped = {} # record the node id for nodes that was chopped (id before chopping) for debugging purpose
    chopped_node_dict = {}
    unchopped_node_dict = {}
    node_id_mapping = {} #{chopped_id: unchopped_id}
    subgfa_preprocess = open(gfa_preprocessed, "r")
    subgfa_postprocess = open(gfa_postprocessed, "w")
    links = []
    updated_links = []
    node_id_range_list = []
    for line in subgfa_preprocess:
        if line[0] == "S":
            splitted_line = line.strip().split("\t")
            # add gbz node ids into lists to get ranges for tabix
            node_id = int(splitted_line[1])
            if len(node_id_range_list) == 0 or node_id_range_list[-1][-1]+1 != node_id:
                node_id_range_list.append([node_id])
            else:
                node_id_range_list[-1].append(node_id)
            chopped_node_dict[node_id] = splitted_line
        elif line[0] == "L":
            splitted_line = line.strip().split("\t")
            links.append(splitted_line)
        elif line[0] == "H":
            header = line
        #TODO may need to add path. We don't need it in the rest of the algorithm for now so
        #the processed subgraph file doesn't have any path lines
    # print(f"nodeid_list_range is {node_id_range_list}")
    for node_id_range in node_id_range_list:
        # print(f"in node id range: {node_id_range}")
        for mapping_line in mc_mapped_walks.fetch(" ", node_id_range[0]-1, node_id_range[-1]):
            splitted_mapping_line = mapping_line.strip().split("\t")
            unchopped_node_id = int(splitted_mapping_line[0])
            chopped_node_id = int(splitted_mapping_line[1])
            assembly_list = ""
            for i in range(2, len(splitted_mapping_line)):
                assembly_list = assembly_list + splitted_mapping_line[i] + ","
            assembly_list = assembly_list[:-1]
            # print(splitted_mapping_line)
            
            adding_node = chopped_node_dict[chopped_node_id]
            if unchopped_node_id not in unchopped_node_dict:
                adding_node[1] = str(unchopped_node_id)
                # TODO this may not be a good tag to use
                adding_node.insert(3, f"SN:Z:{assembly_list}")
                unchopped_node_dict[unchopped_node_id] = adding_node
            else:
                adding_sequence = adding_node[-1]
                unchopped_node_dict[unchopped_node_id][-2] += adding_sequence
                
            node_id_mapping[chopped_node_id] = unchopped_node_id
        # print(f"unchopped_node_dict is: {unchopped_node_dict}")
    for link in links:
        #TODO find actual cases and see how it worked, there's nothing to test based on now
        start = int(link[1])
        start_strand = link[2]
        end = int(link[3])
        end_strand = link[4]
        if node_id_mapping[start] == node_id_mapping[end]:
            if start_strand != "+" or end_strand != "+":
                log.debug(f"negative strands between unchopped nodes: {link}")
        elif node_id_mapping[start] != node_id_mapping[end]:
            new_link = link
            new_link[1] = node_id_mapping[start] 
            new_link[3] = node_id_mapping[end]
            updated_links.append(new_link) 
            # TODO filter out links that involved in chopped nodes and negative strand, examine these cases
    subgfa_postprocess.write(header)
    for key in unchopped_node_dict:
        subgfa_postprocess.write(f"S\t{unchopped_node_dict[key][1]}\t{unchopped_node_dict[key][2]}\t{unchopped_node_dict[key][3]}\n")
    for link in updated_links:
        subgfa_postprocess.write(f"L\t{link[1]}\t{link[2]}\t{link[3]}\t{link[4]}\t{link[5]}\n")


def SubgraphMini(query_region, gfa_preprocessed, gfa_postprocessed, reference_gfa, minigraph_walks, log):
    # check gbz.db file and create subgraph
    gfa.check_gfabase_installed(log)
    gfa.check_gfafile(reference_gfa, log)
    
    subgraph_gfa = gfa.extract_region_from_gfa(reference_gfa,query_region,gfa_preprocessed)
    if subgraph_gfa is None:
        log.error("Subset GFA is None")
    
    header = ""

    subgfa_preprocess = open(gfa_preprocessed, "r")
    subgfa_postprocess = open(gfa_postprocessed, "w")
    links = []
    nodes = []
    node_id_range_list = []
    for line in subgfa_preprocess:
        if line[0] == "S":
            splitted_line = line.strip().split("\t")
            # add gbz node ids into lists to get ranges for tabix
            node_id = int(splitted_line[1])
            assembly_list = [splitted_line[4].split(":")[2]]
            assembly_final = ""
            if "#" not in assembly_list[0]:
                if assembly_list[0][:3] == "chr":
                    assembly_list[0] = f"GRCh38#0#{assembly_list[0]}"
                else:
                    print(f"original assembly is {assembly_list[0]}")
            for mapping_line in minigraph_walks.fetch(" ", node_id-1, node_id):
                splitted_mapping_line = mapping_line.strip().split("\t")
                for i in range(1, len(splitted_mapping_line)):
                    if splitted_mapping_line[i] not in assembly_list:
                        assembly_list.append(splitted_mapping_line[i])
            for assembly in assembly_list:
                assembly_final += f",{assembly}"
            splitted_line[4] = f"SN:Z:{assembly_final[1:]}"
            nodes.append(splitted_line)
            # print(splitted_mapping_line)
        elif line[0] == "L":
            splitted_line = line.strip().split("\t")
            links.append(splitted_line)
        elif line[0] == "H":
            header = line
        #TODO may need to add path. We don't need it in the rest of the algorithm for now so
        #the processed subgraph file doesn't have any path lines
    subgfa_postprocess.write(header)
    for node in nodes:
        subgfa_postprocess.write(f"S\t{node[1]}\t{node[2]}\t{node[3]}\t{node[4]}\t{node[5]}\t{node[6]}\t{node[7]}\n")
    for link in links:
        subgfa_postprocess.write(f"L\t{link[1]}\t{link[2]}\t{link[3]}\t{link[4]}\t{link[5]}\t{link[6]}\t{link[7]}\t{link[8]}\n")

@app.get("/json")
async def read_items(    
    chrom: str = Query(..., description='Chromosome, e.g. `"chr5, chrX"`'),
    start: int = Query(..., description="Start coordinate"),
    end: int = Query(..., description="End coordinate"),
    graphtype: str = Query(..., description='Graph type: `"mc"` (minigraph-cactus) or `"minigraph"`'),
    version: str = Query("v1", description='pangenome release version: `"v1"` or `"v2"`'),
    debug_small_graphs: bool = Query(..., description="If true, every node's length is set to the number of basepairs"),
    minnodelen: float = Query(5, description="Minimum node length to draw.\nIf the drawn node length is smaller than this, it defaults to minnodelen."),
    nodeseglen: float = Query(20, description="Node length for each OGDF node"),
    edgelen: float = Query(5, description="Length of edges between nodes"),
    nodelenpermb: float = Query(1000, description="Formula:\n`drawnNodeLength = nodelenpermb * node_length_in_bp / 1,000,000`")
):
    """
    ## Parameters

    - `chrom`: str — Chromosome(s) to query. Example: `"chr5, chrX"`
    - `start`: int — Start coordinate (1-based)
    - `end`: int — End coordinate (inclusive)
    - `graphtype`: str — `"mc"` (minigraph-cactus) or `"minigraph"`
    - `version`: str - `"v1"` or `"v2"`
    - `debug_small_graphs`: bool — If true, each node's length = number of basepairs
    - `minnodelen`: float — Minimum node length to draw
    - `nodeseglen`: float — Node length for every OGDF node
    - `edgelen`: float — Edge length between nodes
    - `nodelenpermb`: float — Drawn node length scaling factor

    ## Returns

    - **GFA file content**: `dict`  
      GFA format of the specific region queried.
    """
    log = getLogger(name="complexity", level="DEBUG")
    
    query_region = Region(chrom, start, end)

    # create minigraph cactus GFA subgraph
    if graphtype == "MC" or graphtype == "mc":
        if version == "v1":
            gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v1.gfa")
            if not gfa_output.exists():
                preprocess_gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v1_pre.gfa")
                SubgraphMC(query_region, preprocess_gfa_output, gfa_output, mc_hg38_gbz_v1, mc_mapped_walks_v1, log)
                os.remove(preprocess_gfa_output)
        elif version == "v2":
            gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v2.gfa")
            if not gfa_output.exists():
                preprocess_gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v2_pre.gfa")
                SubgraphMC(query_region, preprocess_gfa_output, gfa_output, mc_hg38_gbz_v2, mc_mapped_walks_v2, log)
                os.remove(preprocess_gfa_output)
        else:
            log.error(f"Invalid graph version {version}(valid versions: \"v1\" or \"v2\")")     
    # create minigraph GFA subgraph
    elif graphtype == "minigraph" or graphtype == "Minigraph":
        if version == "v1":
            gfa_output = Path(f"./cache/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}_v1.gfa")
            if not gfa_output.exists():
                preprocess_gfa_output = Path(f"./cache/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}_v1_pre.gfa")
                SubgraphMini(query_region, preprocess_gfa_output, gfa_output, minigraph_hg38_gfa_v1, minigraph_walks_v1, log)
                os.remove(preprocess_gfa_output)
        elif version == "v2":
            gfa_output = Path(f"./cache/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}_v2.gfa")
            if not gfa_output.exists():
                preprocess_gfa_output = Path(f"./cache/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}_v2_pre.gfa")
                SubgraphMini(query_region, preprocess_gfa_output, gfa_output, minigraph_hg38_gfa_v2, minigraph_walks_v2, log)
                os.remove(preprocess_gfa_output)
        else:
            log.error(f"Invalid graph version {version}(valid versions: \"v1\" or \"v2\")")  
    else:
        log.error(f"Invalid graph tyle {graphtype}(valid graph types: \"minigraph\" or \"MC\")")
        return
    settings = {
        "GRAPHTYPE": graphtype,
        "DEBUG_SMALL_GRAPHS": debug_small_graphs,
        "MINNODELENGTH": minnodelen,
        "NODESEGLEN": nodeseglen,
        "EDGELEN": edgelen,
        "NODELENPERMB": nodelenpermb
    }
    
    pggraph = bandage_graph.PGGraph(str(gfa_output), settings)
    pggraph.BuildOGDFGraph()
    pggraph.LayoutGraph()
    
    data = {
    "locus": f"{chrom}:{str(start)}-{str(end)}",
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
            node_info["assembly"] = pgnodes.m_assembly
            node_info["range"] = pgnodes.m_range
            sequence[pgnodes.nodeName] = pgnodes.nodeSequence
            odgf_coordinates = []
            for ogdf_node in pgnodes.GetOgdfNode().m_ogdfNodes:
                coordinates = {"x": pggraph.m_graphAttributes.x(ogdf_node), "y": pggraph.m_graphAttributes.y(ogdf_node)}
                odgf_coordinates.append(coordinates)
            node_info["ogdf_coordinates"] = odgf_coordinates
            node[pgnodes.nodeName] = node_info

    for node_pairs in pggraph.pgedges.keys():
        if pggraph.pgedges[node_pairs].isDrawn():
            edge = {}
            edge["starting_node"] = node_pairs[0].nodeName
            edge["ending_node"] = node_pairs[1].nodeName
            edges.append(edge) 

    data["sequence"] = sequence
    data["node"] = node
    data["edge"] = edges
    
    return JSONResponse(content=data)


# @app.post("/subgraph/svg/")
# async def read_items(settings: Settings):
#     log = getLogger(name="complexity", level="INFO")
    
#     query_region = Region(settings.chr_input, settings.start_loc_input, settings.end_loc_input)

#     # create minigraph cactus GFA subgraph
#     if settings.graph_type == "MC" or settings.graph_type == "mc":
#         gfa_output = Path(f"./cache/mc/subgraph_{settings.chr_input}_{str(settings.start_loc_input)}_{str(settings.end_loc_input)}.gfa")
#         if not gfa_output.exists():
#             SubgraphMC(query_region, gfa_output, log, mc_hg38_gbz)
#     # create minigraph GFA subgraph
#     elif settings.graph_type == "minigraph":
#         gfa_output = Path(f"./cache/minigraph/subgraph_{settings.chr_input}_{str(settings.start_loc_input)}_{str(settings.end_loc_input)}.gfa")
#         if not gfa_output.exists():
#             SubgraphMini(query_region, gfa_output, log, minigraph_hg38_gfa)
#     else:
#         log.error(f"Invalid graph tyle {settings.graph_type}(valid graph types: \"minigraph\" or \"MC\")")
#         return
#     settings_dict = settings.model_dump()
#     pggraph = bandage_graph.PGGraph(str(gfa_output), settings_dict)
#     pggraph.BuildOGDFGraph()
#     pggraph.LayoutGraph()
#     graphPlotter = graph_plotter.GraphPlotter(pggraph, settings_dict)
#     svgFile = graphPlotter.BuildSvg()
    
#     with open(svgFile, "r") as file:
#         content = file.read()
#     os.remove(svgFile)
    
#     return {"svg": content}