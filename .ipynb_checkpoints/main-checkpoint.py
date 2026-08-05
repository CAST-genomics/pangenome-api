import subprocess

tool_path = subprocess.check_output(
    ["git", "config", "--get", "tools.path"], text=True
).strip()
data_path = subprocess.check_output(
    ["git", "config", "--get", "data.path"], text=True
).strip()

import sys
sys.path.append(tool_path)
from panCT.panct.data import Region
from panCT.panct.logging import getLogger

from fastapi import FastAPI, Query, Security, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
from typing import Optional
import gbz_utils as gbz
from pathlib import Path
import os
import gfa_utils as gfa
import bandage_graph
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import json
import pysam
import numpy as np

from contextlib import asynccontextmanager
import logging
import signal
import subprocess
import ssl
import traceback
import numpy as np

logging.basicConfig(level=logging.INFO)
api_log = logging.getLogger("app")

def log_signal(signum, frame):
    api_log.error("Received signal %s in pid=%s", signum, os.getpid())
    api_log.error("".join(traceback.format_stack(frame)))

for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(sig, log_signal)

@asynccontextmanager
async def lifespan(app: FastAPI):
    api_log.info("startup pid=%s", os.getpid())
    try:
        yield
    finally:
        api_log.error("lifespan shutdown reached pid=%s", os.getpid())

app = FastAPI(lifespan=lifespan)

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

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain('/home/xbu/pgapi_cert/pangenome-api_ucsd_edu.pem', keyfile='/home/xbu/pgapi_cert/pangenome-api_ucsd_edu.key')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to restrict access in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mc_hg38_gbz_v1 = Path(f"{data_path}/hprc-v1.1-mc-grch38.gbz")
mc_hg38_gbz_v2 = Path(f"{data_path}/hprc-v2.0-mc-grch38.gbz")
minigraph_hg38_gfa_v1 = Path(f"{data_path}/hprc-v1.0-minigraph-grch38.gfa")
minigraph_hg38_gfa_v2 = Path(f"{data_path}/hprc-v2.0-minigraph-grch38.gfa")
mc_mapped_walks_v1 = pysam.TabixFile(f"{data_path}/hprc-v1.1-mc-grch38-mapped-flattened.walk.gz")
mc_mapped_walks_v2 = None
minigraph_walks_v1 = pysam.TabixFile(f"{data_path}/hprc_v1.0_minigraph_filtered_with_id.walk.gz")

# walks updated in 4/22/2026 with features:
#   1. filled missing nodes
#   2. pclai for both hg38 and asm coordinates
#   3. discarded median approach, used impainting methods on euclidean distance
#   4. with assembly coordinates
minigraph_walks_v2_updated = pysam.TabixFile(f"{data_path}/v1_1_hprc_v2.0_minigraph.sorted.pclai.walk.gz")

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


def SubgraphMini(query_region, gfa_preprocessed, gfa_postprocessed, reference_gfa, minigraph_walks, pca, log):
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
            node_id = int(splitted_line[1])
            # default_coord = ""
            # non_duplicated_assembly_coord = ""
            # duplicated_assembly_coord = "."

            # updated to new walks format: 
            # .	48	GRCh38#0#chr1:356372-362698	HG00544#2#CM089383.1|+:>:17162-23470|hg38:.:.:.:.:.:.|asm:.:.:.:.:.:., ...
            for mapping_line in minigraph_walks.fetch(".", node_id-1, node_id):
                mapping_parts = mapping_line.strip().split("\t")
                default_coord = mapping_parts[2]
                non_duplicated_assembly_coord = mapping_parts[3]
                duplicated_assembly_coord = mapping_parts[4]
                    
            splitted_line[4] = f"SN:Z:{default_coord}"
            splitted_line[5] = (f"na:Z:{non_duplicated_assembly_coord}") # Non-duplicated Assembly list
            splitted_line[6] = (f"da:Z:{duplicated_assembly_coord}") # Duplicated Assembly list
            nodes.append(splitted_line)
        elif line[0] == "L":
            splitted_line = line.strip().split("\t")
            links.append(splitted_line)
        elif line[0] == "H":
            header = line
        #TODO may need to add path. We don't need it in the rest of the algorithm for now so
        #the processed subgraph file doesn't have any path lines
    subgfa_postprocess.write(header)
    for node in nodes:
        subgfa_postprocess.write(f"S\t{node[1]}\t{node[2]}\t{node[3]}\t{node[4]}\t{node[5]}\t{node[6]}\n")
    for link in links:
        subgfa_postprocess.write(f"L\t{link[1]}\t{link[2]}\t{link[3]}\t{link[4]}\t{link[5]}\t{link[6]}\t{link[7]}\t{link[8]}\n")

"""
this function will filter the assembly range list which may have multiple ranges based on different contigs per assembly.
for assemblies that has multiple ranges, we take the one of the contig that has the biggest total node sequence length.

Input: assembly_range list, {assembly_id: {contig1_name:[min_start, max_end, contig1_lenof_node,contig1_numof_node], contig2_name:[min_start, max_end, contig2_lenof_node,contig2_numof_node]}]})
Output: adjusted assembly_range list with one range and one contig per assembly
"""
def adjustAssemblyRangeList(assembly_range):
    updated_assembly_range = {}
    for assembly_id, contig_info in assembly_range.items():
        if len(contig_info) > 1:
            seq_id, range_taken = max(contig_info.items(), key=lambda item: item[1][2])
            region = f"{range_taken[0]}-{range_taken[1]}"
            updated_assembly_range[assembly_id] = {"sequence_id": seq_id, "region": region}
        else:
            seq_id = next(iter(contig_info))
            region = f"{contig_info[seq_id][0]}-{contig_info[seq_id][1]}"
            updated_assembly_range[assembly_id] = {"sequence_id": seq_id, "region": region}
    return updated_assembly_range
    
"""
this function will go through every duplicated assembly in a given node, and determine which coordinate to take in this assembly

Input: 
    adjusted assembly_range: {assembly_id1: {"sequence_id": seq_id, "region": 1000-2000}, assembly_id2: ...}
    duplicated assembly list of a node:
        [
            {
                "assembly_name": assembly1,
                "haplotype": haplo1, 
                "metadata": [
                    {
                        "sequence_id": seq_id1,
                        "path_strand": path_strand,
                        "node_strand": node_strand,
                        "start": int(start_str),
                        "end": int(end_str),
                        "pclai": pclai_lst,
                        "take": "no"
                    },
                    {
                        "sequence_id": seq_id2,
                        "path_strand": path_strand,
                        "node_strand": node_strand,
                        "start": int(start_str),
                        "end": int(end_str),
                        "pclai": pclai_lst,
                        "take": "no"
                    },
                    
                ]
            }, 
            {
                "assembly_name": assembly2,
                ...
            }, 
        ]
Output: update the "take" entry of each duplicated coordinates
"""
def determineIfDupCoordShouldBeTaken(assembly_range, dup_assembly):
    for j in range(0, len(dup_assembly)):
        assembly_name = dup_assembly[j]["assembly_name"]
        haplo = dup_assembly[j]["haplotype"]
        assembly_id = f"{assembly_name}#{haplo}"
        
        # if the duplicated assembly has no non-duplicated entry in this region, we will skip it
        if assembly_id not in assembly_range:
            continue
        
        else:
            # index selected node in the right range, same contig
            pre_selected_coord = []
            for i in range(0, len(dup_assembly[j]["metadata"])):
                each_dup_coord = dup_assembly[j]["metadata"][i]
                seq_id = each_dup_coord["sequence_id"]
                start = each_dup_coord["start"]
                end = each_dup_coord["end"]
                if seq_id != assembly_range[assembly_id]["sequence_id"]:
                    continue
                elif end < int(assembly_range[assembly_id]["region"].split("-")[0]):
                    continue
                elif start > int(assembly_range[assembly_id]["region"].split("-")[1]):
                    continue
                else:
                    dup_assembly[j]["metadata"][i]["taken"] = "yes"
                    pre_selected_coord.append(i)
                
            if len(pre_selected_coord) > 1:
                for index in pre_selected_coord:
                    dup_assembly[j]["metadata"][index]["taken"] = "no"
                print(f"[DEBUG]:{assembly_id} has more than one duplicated coordinates in the right contig({dup_assembly[j]['metadata'][i]['sequence_id']}) and right range!")

    return


"""
return an assembly list and a pclai list of the same format as version 1 api, which will be used to directly add to the JSON file

Input:
    nd_assembly: 
    dup_assembly: 

"""
def adjustToApiVersion1(nd_assembly, dup_assembly):
    pclai = {}
    assembly = []
    for asm in nd_assembly:
        assembly_name = asm["assembly_name"]
        haplotype = asm["haplotype"]
        seq_id = asm["metadata"][0]["sequence_id"]
        asm_info = {
            "assembly_name": assembly_name,
            "haplotype": haplotype,
            "sequence_id": seq_id
        }
        assembly.append(asm_info)
        if len(asm["metadata"][0]["pclai"]) > 1:
            coord_lst = []
            rgb_lst = []
            for lai in asm["metadata"][0]["pclai"]:
                coord_lst.append(lai["coordinates"])
                rgb_lst.append(lai["RGB"])
            coord_median = np.median(coord_lst, axis=0)
            updated_coord = coord_median.tolist()
            rgb_median = np.median(rgb_lst, axis=0)
            updated_rgb =rgb_median.tolist()
            pclai[f"{assembly_name}#{haplotype}"] = {
                "coordinates": updated_coord,
                "RGB": updated_rgb
            }
        elif len(asm["metadata"][0]["pclai"]) == 1:
            pclai[f"{assembly_name}#{haplotype}"] = {
                "coordinates": asm["metadata"][0]["pclai"][0]["coordinates"],
                "RGB": asm["metadata"][0]["pclai"][0]["RGB"]
            }
                
    # print(dup_assembly)
    return assembly, pclai
        

@app.get("/json")
async def read_items(
    chrom: str = Query(..., description='Chromosome, e.g. `"chr5, chrX"`'),
    start: int = Query(..., description="Start coordinate"),
    end: int = Query(..., description="End coordinate"),
    graphtype: str = Query(..., description='Graph type: `"mc"` (minigraph-cactus) or `"minigraph"`'),
    version: str = Query("v2", description='pangenome release version: `"v1"` or `"v2"`'),
    api: str = Query("v3", description = 'api release version: `"v1"`(without coordinates), `"v2"`(with coordinates), or `"v3"`(with coordinates and both api coords)'),
    pca: str = Query("hg38", description = 'coordinate system for pclai: `"hg38"`(based on hg38 coordinates) or `"assembly"`(based on coordinates of each assembly)'),
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
        # with the updated walks file coordinates and pclai information, we will turn v1 off for now. It will be back later 
        # after we get the walks file running
        # if version == "v1":
        #     gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v1.gfa")
        #     if not gfa_output.exists():
        #         preprocess_gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v1_pre.gfa")
        #         SubgraphMC(query_region, preprocess_gfa_output, gfa_output, mc_hg38_gbz_v1, mc_mapped_walks_v1, log)
        #         os.remove(preprocess_gfa_output)
        if version == "v2":
            gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v2.gfa")
            if not gfa_output.exists():
                preprocess_gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v2_pre.gfa")
                SubgraphMC(query_region, preprocess_gfa_output, gfa_output, mc_hg38_gbz_v2, mc_mapped_walks_v2, log)
                os.remove(preprocess_gfa_output)
        else:
            log.error(f"Invalid graph version {version}(valid versions: \"v2\", \"v1\" is not available yet)")     
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
                SubgraphMini(query_region, preprocess_gfa_output, gfa_output, minigraph_hg38_gfa_v2, minigraph_walks_v2_updated, pca, log)
                os.remove(preprocess_gfa_output)
        else:
            log.error(f"Invalid graph version {version}(valid versions: \"v1\" or \"v2\")")  
    else:
        log.error(f"Invalid graph tyle {graphtype}(valid graph types: \"minigraph\" or \"MC\")")
        return
    settings = {
        "GRAPHTYPE": graphtype,
        "VERSION": version,
        "API": api,
        "PCLAI": pca,
        "DEBUG_SMALL_GRAPHS": debug_small_graphs,
        "MINNODELENGTH": minnodelen,
        "NODESEGLEN": nodeseglen,
        "EDGELEN": edgelen,
        "NODELENPERMB": nodelenpermb
    }
    
    pggraph = bandage_graph.PGGraph(str(gfa_output), settings)
    pggraph.BuildOGDFGraph()
    pggraph.LayoutGraph()
    assembly_range = adjustAssemblyRangeList(pggraph.pgassemblies) # {assembly_id1: {"sequence_id": seq_id, "region": 1000-2000}, assembly_id2: ...}
    # TODO adjust take in non duplicated coordinates if it's not from the right contig. Can look into real cases before this adjustment
    
    if api in ["v2", "v3"]:
        data = {
            "queried_locus": f"GRCh38#0#{chrom}:{str(start)}-{str(end)}",
            "actual_locus": f"GRCh38#0#{assembly_range['GRCh38#0']['sequence_id']}:{assembly_range['GRCh38#0']['region']}",
            "node": {},
            "edge": [],
            "sequence": {}
        }

        sequence = {}
        node = {}
        edges = []

        for pgnodes in pggraph.pgnodes.values():
            if pgnodes.isDrawn():
                # TODO check if this method can directly adjust the assembly list
                determineIfDupCoordShouldBeTaken(assembly_range, pgnodes.m_dup_assembly)
                node_info = {}
                node_info["name"] = pgnodes.nodeName
                node_info["length"] = pgnodes.nodeLength
                node_info["assembly"] = pgnodes.m_nd_assembly
                node_info["duplicated_assembly"] = pgnodes.m_dup_assembly
                node_info["assembly_metadata"] = pgnodes.m_assembly_metadata
                node_info["default_range"] = pgnodes.m_range
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
        data["assembly"] = assembly_range
        data["edge"] = edges
    
    else:
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
                determineIfDupCoordShouldBeTaken(assembly_range, pgnodes.m_dup_assembly)
                # NOTE: as this is an outdated version just for the use before the new version is updated, we
                # did not consider duplicated assembly. Please try to avoid certain regions like chr6 and chr14.
                assembly, pclai = adjustToApiVersion1(pgnodes.m_nd_assembly, pgnodes.m_dup_assembly)
                node_info = {}
                node_info["name"] = pgnodes.nodeName
                node_info["length"] = pgnodes.nodeLength
                node_info["assembly"] = assembly
                node_info["assembly_metadata"] = pgnodes.m_assembly_metadata
                node_info["range"] = pgnodes.m_range
                if not pclai:
                    node_info["pclai_coordinates"] = None
                else:
                    node_info["pclai_coordinates"] = pclai
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
