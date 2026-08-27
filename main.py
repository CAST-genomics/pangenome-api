import subprocess
import sys

tool_path = subprocess.check_output(
    ["git", "config", "--get", "tools.path"], text=True
).strip()
data_path = subprocess.check_output(
    ["git", "config", "--get", "data.path"], text=True
).strip()

sys.path.append(tool_path)

from contextlib import asynccontextmanager, contextmanager
import logging
import time
import signal
import ssl
import traceback
import numpy as np
import os
from panCT.panct.data import Region
from panCT.panct.logging import getLogger
from fastapi import FastAPI, Query, Security, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import gbz_utils as gbz
from pathlib import Path
import gfa_utils as gfa
import bandage_graph
from pydantic import BaseModel
import tempfile
import json
import pysam
import re
import adaptagrams_converter

ssl_context = None
cert_path = os.getenv("SSL_CERT_PATH")
key_path = os.getenv("SSL_KEY_PATH")

if cert_path and key_path:
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(cert_path, keyfile=key_path)

logging.basicConfig(level=logging.INFO)
api_log = logging.getLogger("app")

app = FastAPI()

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
mc_mapped_walks_v2 = pysam.TabixFile(f"{data_path}/hprc-v2.0-mc-grch38-v2.2.walk.gz")
minigraph_walks_v1 = pysam.TabixFile(f"{data_path}/hprc_v1.0_minigraph_filtered_with_id.walk.gz")
generate_svg_js_script = Path("./seqtubemap/generate-svg.mjs")

# walks updated in 4/22/2026 with features:
#   1. filled missing nodes
#   2. pclai for both hg38 and asm coordinates
#   3. discarded median approach, used impainting methods on euclidean distance
#   4. with assembly coordinates
minigraph_walks_v2_updated = pysam.TabixFile(f"{data_path}/v1_1_hprc_v2.0_minigraph.sorted.pclai.walk.gz")

def delete_files(path_list):
    for path in path_list:
        os.remove(path)
    
#TODO check if all chopped node id finds a mapped unchopped node id
def SubgraphMC(query_region, gfa_preprocessed, reference_gbz, log):
    # check gbz.db file and create subgraph
    if not gbz.check_gbzfile(reference_gbz, log):
        gbz.index_gbz(reference_gbz)
    subgraph_gfa = gbz.extract_region_from_gbz(reference_gbz,query_region,"GRCh38", gfa_preprocessed)
    if subgraph_gfa is None:
        log.error("Subset GFA is None")
    return

def PreprocessMCSubgraphV1(gfa_preprocessed, gfa_postprocessed, mc_mapped_walks, log):
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

def GenerateWalksMC(preprocess_gfa_subgraph_no_walk, preprocess_gfa_subgraph_w_walk, mc_mapped_walks_v2, log):
    
    """
    Add W lines to minigraph cactus subgraph .gfa

    Parameters
    ----------
        preprocess_gfa_subgraph_no_walk: Path
            subgraph minigraph cactus gfa w/o W lines
        preprocess_gfa_subgraph_w_walk: Path
            output file path; subgraph minigraph cactus gfa w W lines added
        mc_mapped_walks_v2: pysam.TabixFile Object
            minigraph cactus walk file
    """
    
    gfa_no_walk = open(preprocess_gfa_subgraph_no_walk, "r")
    gfa_w_walk = open(preprocess_gfa_subgraph_w_walk, "w")
    strand_translation = {"+":">", "-":"<"}
    
    #coord_table = {assembly:{contig:[[coordinate],[node_id],[strand]]}}
    coord_table = {}
    #dup_coord_table = {assembly:{contig:{nodeid:[coordinate_x, coordinate_y, strand]}}}
    dup_coord_table = {}
    for line in gfa_no_walk:
        if line[0] == "S":
            node_id = int(line.split("\t")[1])
            
            # for each node, record their walks coord in coord_table
            for walk_line in mc_mapped_walks_v2.fetch(".", node_id-1, node_id):
                _, _, length, asm_coord, asm_coord_dup = walk_line.strip().split("\t")
                length = int(length)
                for single_coord in asm_coord.split(","):
                    asm,contig_coord_strand = single_coord.split("|")
                    contig, coord, strand = contig_coord_strand.split(":")
                    coord = int(coord)
                    if asm not in coord_table:
                        coord_table[asm] = {contig:[[(coord,coord+length)],[node_id],[strand]]}
                    else:
                        if contig not in coord_table[asm]:
                            coord_table[asm][contig] = [[(coord,coord+length)],[node_id],[strand]]
                        else:
                            coord_table[asm][contig][0].append((coord,coord+length))
                            coord_table[asm][contig][1].append(node_id)
                            coord_table[asm][contig][2].append(strand)
                
                if asm_coord_dup != ".":
                    for dup_coord in asm_coord_dup.split(","):
                        part = dup_coord.split("|")
                        asm = part[0]
                        if asm not in dup_coord_table:
                            dup_coord_table[asm] = {}
                        for i in range(1, len(part)):
                            contig, coord, strand = part[i].split(":")
                            coord = int(coord)
                            if contig not in dup_coord_table[asm]:
                                dup_coord_table[asm][contig] = {node_id:[[(coord,coord+length)],[strand]]}
                            else:
                                if node_id not in dup_coord_table[asm][contig]:
                                    dup_coord_table[asm][contig][node_id] = [[(coord,coord+length)],[strand]]
                                else:
                                    # we have duplicated dup entries, so have to filter that out
                                    # TODO fix the walks file
                                    if any(coord == t[0] for t in dup_coord_table[asm][contig][node_id][0]):
                                        continue
                                    else:
                                        dup_coord_table[asm][contig][node_id][0].append((coord,coord+length))
                                        dup_coord_table[asm][contig][node_id][1].append(strand)
                        
            gfa_w_walk.write(line)
        elif line[0] == "L" or line[0] == "H":
            gfa_w_walk.write(line)
        # we don't record anything else other than the H, S and L lines
        else:
            continue
    if dup_coord_table == {}:
        print("no duplicated node")
    print(dup_coord_table)
        
    # use the coord_table to generate walks lines
    for asm in coord_table:
        if len(coord_table[asm]) > 1:
            print(f"assembly {asm} spans more than 1 contigs")
        
        for contig in coord_table[asm]:
            asm_contig = f"{asm}:{contig}"
            sample, haplo = asm.split("#")
            coords = coord_table[asm][contig][0]
            node_ids = coord_table[asm][contig][1]
            strands = coord_table[asm][contig][2]
            
            # add dup coords back to the regular coord lists
            min_coord = min(t[0] for t in coords)
            max_coord = max(t[-1] for t in coords)
            if asm in dup_coord_table and contig in dup_coord_table[asm]:
                for node_id in dup_coord_table[asm][contig]:
                    # DEBUG
                    capture = 0 
                    for i in range(0, len(dup_coord_table[asm][contig][node_id][0])):
                        # if more than 1 coordinate of the same asm, same contig, same node is
                        # added, we assume that this happened in the original walks file
                        # TODO need further check on this
                        node_coord = dup_coord_table[asm][contig][node_id][0][i]
                        strand = dup_coord_table[asm][contig][node_id][1][i]
                        if node_coord[0] >= min_coord and node_coord[1] <= max_coord:
                            coords.append(node_coord)
                            node_ids.append(node_id)
                            strands.append(strand)
                            capture += 1
                    if capture > 1:
                        print(f"in this region, we added 2 coordinates from node {node_id} into the walk line of assembly {asm_contig}")
                
            # Pair each coordinate with its node_id, then sort by start position
            paired = sorted(zip(coords, node_ids, strands), key=lambda x: x[0])

            sorted_coords = [p[0] for p in paired]
            sorted_node_ids = [p[1] for p in paired]
            sorted_strands = [p[2] for p in paired]
            sorted_coords_final = []
            sorted_node_ids_final = []
            sorted_strands_final = []

            # Walk through consecutive intervals and check prev_end vs curr_start
            start_index = 0
            for i in range(1, len(sorted_coords)):
                prev_end = sorted_coords[i - 1][1]
                curr_start = sorted_coords[i][0]
                if curr_start != prev_end:
                    sorted_coords_final.append(sorted_coords[start_index:i])
                    sorted_node_ids_final.append(sorted_node_ids[start_index:i])
                    sorted_strands_final.append(sorted_strands[start_index:i])
                    start_index = i
                    print(f"gaps between node {sorted_node_ids[i - 1]} and {sorted_node_ids[i]} in assembly {asm_contig} is {prev_end-curr_start}")
            sorted_coords_final.append(sorted_coords[start_index:])
            sorted_node_ids_final.append(sorted_node_ids[start_index:])
            sorted_strands_final.append(sorted_strands[start_index:])
            
            for q in range(0, len(sorted_node_ids_final)):
                write_walk = ""
                for j in range(0, len(sorted_node_ids_final[q])):
                    write_walk += f"{strand_translation[sorted_strands_final[q][j]]}{sorted_node_ids_final[q][j]}"
                walk_start = sorted_coords_final[q][0][0]
                walk_end = sorted_coords_final[q][-1][1]
                gfa_w_walk.write(f"W\t{sample}\t{haplo}\t{contig}\t{walk_start}\t{walk_end}\t{write_walk}\n")
            
def SeqTubeGfaProcessor(preprocess_gfa_subgraph, postprocess_gfa_subgraph, pathnumoption):
    """
    rewrite gfa to fit the input requirements of sequence tube map. Output of this function is 
    different by pathnumoption

    Parameters
    ----------
        preprocess_gfa_subgraph: Path
            subgraph minigraph cactus gfa file generated by gbzbase
        postprocess_gfa_subgraph: Path
            Changed W tag to P tag (which SequenceTubeMap Accepts)
            if pathnumoption is compressed, combine all the identical paths into a single path
    """
    
    input_gfa = open(preprocess_gfa_subgraph, "r")
    output_gfa = open(postprocess_gfa_subgraph, "w")

    path_summary = {}
    hg38_line = ""

    for line in input_gfa:
        parts = line.strip().split("\t")
        header = parts[0]
        if header != "W":
            output_gfa.write(line)
            continue

        sample = parts[1]
        haplo = parts[2]
        contig = parts[3]
        walk = parts[6]
        walk_parts = re.split(r'([<>])', walk)[1:]
        walk_update = ""
        for i in range(1, len(walk_parts), 2):
            if walk_parts[i-1] == ">":
                walk_update += f"{walk_parts[i]}+,"
            else:
                walk_update += f"{walk_parts[i]}-,"
        walk_update = walk_update[:-1]

        if pathnumoption == "compressed":
            if sample == "GRCh38":
                hg38_line = f"P\t{sample}#{haplo}#{contig}\t{walk_update}\t*\n"
            else:
                if walk_update not in path_summary:
                    path_summary[walk_update] = f"{sample}#{haplo}#{contig}"
                else:
                    path_summary[walk_update] += f",{sample}#{haplo}#{contig}"
        else:
            output_gfa.write(f"P\t{sample}#{haplo}#{contig}\t{walk_update}\t*\n")

    if pathnumoption == "compressed":
        output_gfa.write(hg38_line)
        for path, assembly_list in path_summary.items():
            output_gfa.write(f"P\t{assembly_list}\t{path}\t*\n")

    return

def ConvertGfaToVg(gfa_file, vg_file):
    """
    convert .gfa to .vg with vg convert

    Parameters
    ----------
        gfa_file: Path
            path to the gfa file
        vg_file: Path
            path to the vg file

    Returns
    -------
    passed : bool
        True if we were able to create the .vg file
    """
    
    cmd = ["vg", "convert", "-g", gfa_file]
    with open(vg_file, "wb") as out:
        proc = subprocess.run(cmd, stdout=out)
    return proc.returncode == 0
    
def ConvertVgToJson(vg_file, json_file):
    """
    convert .vg to .json with vg view

    Parameters
    ----------
        vg_file: Path
            path to the vg file
        json_file: Path
            path to the json file

    Returns
    -------
    passed : bool
        True if we were able to create the .json file
    """
    
    cmd = ["vg", "view", "-j", vg_file]
    with open(json_file, "wb") as out:
        proc = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE)
    return proc.returncode == 0

def GenerateSeqTubeMapSvg(json_file, svg_file, start, end, nodewidthoption, pclai_color_scheme = None):
    """
    generate sequence tube map svg using the generate-svg javascript in ./seqtubemap

    Parameters
    ----------
        json_file: Path
            path to the mc subgraph json file
        svg_file: 
            path to the output svg file
        nodewidthoption: Str
            generate-svg.mjs params, controls the node width of seq tube map outputs

    Returns
    -------
    passed : bool
        True if we were able to create the .svg file
    """
    cmd = [
        "node", 
        "--max-old-space-size=8192",
        str(generate_svg_js_script), 
        str(json_file), 
        str(svg_file), 
        str(start), 
        str(end), 
        nodewidthoption
    ]
    if pclai_color_scheme is not None:
        cmd.append(json.dumps(pclai_color_scheme))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return proc.returncode == 0

def SubgraphMini(query_region, gfa_preprocessed, reference_gfa, log):
    # check gbz.db file and create subgraph
    gfa.check_gfabase_installed(log)
    gfa.check_gfafile(reference_gfa, log)
    
    subgraph_gfa = gfa.extract_region_from_gfa(reference_gfa,query_region,gfa_preprocessed)
    if subgraph_gfa is None:
        log.error("Subset GFA is None")
        
    return

def PreprocessMiniSubgraph(gfa_preprocessed, gfa_postprocessed, minigraph_walks, log):
    if not os.path.exists(gfa_preprocessed):
        log.error(f"Input file not found: {gfa_preprocessed}")
        raise FileNotFoundError(f"Input file not found: {gfa_preprocessed}")

    subgfa_preprocess = open(gfa_preprocessed, "r")
    subgfa_postprocess = open(gfa_postprocessed, "w")
    
    header = ""
    links = []
    nodes = []
    for line in subgfa_preprocess:
        if line[0] == "S":
            splitted_line = line.strip().split("\t")
            node_id = int(splitted_line[1])

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
    
    return

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

# TODO provide option for asm coord based pclai
def GetPclaiColorScheme(minigraph_node, minigraph_walk, log):
    pclai_color_scheme = {}
    for line in minigraph_walk.fetch(".", minigraph_node-1, minigraph_node):
        _, node_id, _, asm_list, _ = line.strip().split("\t")
        print(f"in GetPclaiColorScheme, current node id is {node_id}")
        for asm in asm_list.split(","):
            _, x_coord, y_coord, r, g, b, score = asm.split("|")[2].split(":")
            asm_contig_name = asm.split("|")[0]
            if x_coord == ".":
                # TODO: ask Doug about the grey color he used for pclai
                pclai_color_scheme[asm_contig_name] = [(211.0, 211.0, 211.0), (None, None), None]
            else:
                pclai_color_scheme[asm_contig_name] = [(float(r), float(g), float(b)), (float(x_coord), float(y_coord)), score]
        
    if pclai_color_scheme == {}:
        # print error message node not found
        pclai_color_scheme = None
    return pclai_color_scheme
        
@contextmanager
def stage_timing(stages, name):
    """
    Record the wall time of one pipeline stage into `stages`.

    Used to attribute request latency across the seqtubemap pipeline. Timings are
    emitted as a single `[stage-timing]` log line per request, so the breakdown can
    be pulled out of the logs with a grep.
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        stages[name] = round(time.perf_counter() - t0, 3)


@app.get("/seqtubemap")
async def seqtubemap(
    background_tasks: BackgroundTasks,
    chrom: str = Query("chr1", description='Chromosome, e.g. `"chr5, chrX"`'),
    start: int = Query(25251923, description="Start coordinate"),
    end: int = Query(25252095, description="End coordinate"),
    version: str = Query("v2", description='pangenome release version: `"v1"` or `"v2"`'),
    pathnumoption: str = Query("normal", description='options for the number of path: `"compressed"`(compress same path as one single path) or `"normal"` (show each path seperately)'),
    nodewidthoption: str = Query("compressed", description='Options for the width of sequence nodes:`"compressed"`(scale node width with log2 of number of bp) or `"normal"`(scale node width linearly with number of bp)'),
    minigraphnode: int = Query(None, description="If the queried region is based on a minigraph node, record the node ID to enable Point Cloud Local Ancestry Inference coloring")
):
    
    log = getLogger(name="complexity", level="DEBUG")
    query_region = Region(chrom, start, end)
    
    preprocess_gfa_subgraph_no_walk = Path(f"./cache/seqtubemap/mc/subgraph_{chrom}_{str(start)}_{str(end)}_{version}_no_walk.gfa")
    preprocess_gfa_subgraph_w_walk = Path(f"./cache/seqtubemap/mc/subgraph_{chrom}_{str(start)}_{str(end)}_{version}_with_walk.gfa")
    postprocess_gfa_subgraph = Path(f"./cache/seqtubemap/mc/subgraph_{chrom}_{str(start)}_{str(end)}_path{pathnumoption}_{version}.gfa")
    vg_subgraph = Path(f"./cache/seqtubemap/mc/subgraph_{chrom}_{str(start)}_{str(end)}_path{pathnumoption}_{version}.vg")
    json_subgraph = Path(f"./cache/seqtubemap/mc/subgraph_{chrom}_{str(start)}_{str(end)}_path{pathnumoption}_{version}.json")
    seqtubemap_svg = Path(f"./cache/seqtubemap/mc/subgraph_{chrom}_{str(start)}_{str(end)}_path{pathnumoption}_{version}.svg")
      
    stages = {}
    subgraph_cached = preprocess_gfa_subgraph.exists()

    with stage_timing(stages, "subgraph_extract"):
        if not subgraph_cached:
            if version == "v1":
                log.error("version 1 is currently unavailable for minigraph cactus")
                # SubgraphMC(query_region, preprocess_gfa_subgraph, mc_hg38_gbz_v1, log)
            elif version == "v2":
                SubgraphMC(query_region, preprocess_gfa_subgraph, mc_hg38_gbz_v2, log)
                GenerateWalksMC(preprocess_gfa_subgraph_no_walk, preprocess_gfa_subgraph_w_walk, mc_mapped_walks_v2, log)   
                background_tasks.add_task(delete_files, [preprocess_gfa_subgraph_no_walk])
            else:
                log.error(f"Invalid graph version {version}(valid versions: \"v1\" or \"v2\")")
    
    # TODO update SeqTubeGfaProcessor; pathnumoption = compressed is currently not supported
    # with stage_timing(stages, "gfa_process"):
        # SeqTubeGfaProcessor(preprocess_gfa_subgraph, postprocess_gfa_subgraph, pathnumoption)
    with stage_timing(stages, "gfa_to_vg"):
        ConvertGfaToVg(preprocess_gfa_subgraph_w_walk, vg_subgraph)
    with stage_timing(stages, "vg_to_json"):
        ConvertVgToJson(vg_subgraph, json_subgraph)
    
    with stage_timing(stages, "get_pclai_color_scheme"):
        pclai_color_scheme = None
        if minigraphnode is not None:
            if version == "v1":
                # TODO
                pclai_color_scheme = None
            elif version == "v2":
                pclai_color_scheme = GetPclaiColorScheme(minigraphnode, minigraph_walks_v2_updated, log)
            
    with stage_timing(stages, "generate_svg"):
        GenerateSeqTubeMapSvg(json_subgraph, seqtubemap_svg, start, end, nodewidthoption, pclai_color_scheme)

    def size_mb(path):
        return round(path.stat().st_size / 1048576, 2) if path.exists() else None

    total = round(sum(stages.values()), 3)
    breakdown = " ".join(f"{name}={secs}s" for name, secs in stages.items())
    log.info(
        f"[stage-timing] {chrom}:{start}-{end} span={end - start}bp {version} "
        f"path={pathnumoption} width={nodewidthoption} cached={subgraph_cached} "
        f"total={total}s {breakdown} "
        f"json_mb={size_mb(json_subgraph)} svg_mb={size_mb(seqtubemap_svg)}"
    )

    background_tasks.add_task(delete_files, [postprocess_gfa_subgraph, vg_subgraph, json_subgraph, seqtubemap_svg])
    return FileResponse(seqtubemap_svg, media_type="image/svg+xml")


@app.get("/json")
async def bandage(
    chrom: str = Query(..., description='Chromosome, e.g. `"chr5, chrX"`'),
    start: int = Query(..., description="Start coordinate"),
    end: int = Query(..., description="End coordinate"),
    graphtype: str = Query(..., description='Graph type: `"mc"` (minigraph-cactus) or `"minigraph"`'),
    version: str = Query("v2", description='pangenome release version: `"v1"` or `"v2"`'),
    debug_small_graphs: bool = Query(..., description="If true, every node's length is set to the number of basepairs"),
    minnodelen: float = Query(5, description="Minimum node length to draw.\nIf the drawn node length is smaller than this, it defaults to minnodelen."),
    nodeseglen: float = Query(20, description="Node length for each OGDF node"),
    edgelen: float = Query(5, description="Length of edges between nodes"),
    nodelenpermb: float = Query(1000, description="Formula:\n`drawnNodeLength = nodelenpermb * node_length_in_bp / 1,000,000`"),
    linear: bool = Query(False, description="If true, linearize the selected assembly via AdaptagramsGraph instead of the default OGDF layout"),
    assembly: str = Query("GRCh38#0", description="Assembly and haplotype to linearize when `linear` is true (in `assembly#haplotype` format - e.g. `GRCh38#0`)")
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
    - `linear`: bool — Whether output should be linearized wrt an assembly
    - `assembly`: str — Assembly to linearize against, provided in `sample_name#haplotype` format.

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
        #     gfa_output = Path(f"./cache/bandage/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v1.gfa")
        #     if not gfa_output.exists():
        #         preprocess_gfa_output = Path(f"./cache/bandage/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v1_pre.gfa")
        #         SubgraphMC(query_region, preprocess_gfa_output, gfa_output, mc_hg38_gbz_v1, mc_mapped_walks_v1, log)
        #         os.remove(preprocess_gfa_output)
        if version == "v2":
            gfa_output = Path(f"./cache/bandage/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v2.gfa")
            if not gfa_output.exists():
                preprocess_gfa_output = Path(f"./cache/bandage/mc/subgraph_{chrom}_{str(start)}_{str(end)}_v2_pre.gfa")
                SubgraphMC(query_region, preprocess_gfa_output, gfa_output, mc_hg38_gbz_v2, mc_mapped_walks_v2, log)
                os.remove(preprocess_gfa_output)
        else:
            log.error(f"Invalid graph version {version}(valid versions: \"v2\", \"v1\" is not available yet)")     
    # create minigraph GFA subgraph
    elif graphtype == "minigraph" or graphtype == "Minigraph":
        # with the updated walks file coordinates and pclai information, we will turn v1 off for now. It will be back later 
        # after we get the walks file running
        # if version == "v1":
        #     gfa_output = Path(f"./cache/bandage/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}_v1.gfa")
        #     if not gfa_output.exists():
        #         preprocess_gfa_output = Path(f"./cache/bandage/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}_v1_pre.gfa")
        #         SubgraphMini(query_region, preprocess_gfa_output, gfa_output, minigraph_hg38_gfa_v1, minigraph_walks_v1, log)
        #         os.remove(preprocess_gfa_output)
        if version == "v2":
            postprocess_gfa_output = Path(f"./cache/bandage/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}_v2.gfa")
            if not postprocess_gfa_output.exists():
                preprocess_gfa_output = Path(f"./cache/bandage/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}_v2_pre.gfa")
                SubgraphMini(query_region, preprocess_gfa_output, minigraph_hg38_gfa_v2, log)
                PreprocessMiniSubgraph(preprocess_gfa_output, postprocess_gfa_output, minigraph_walks_v2_updated, log)
                os.remove(preprocess_gfa_output)
        else:
            log.error(f"Invalid graph version {version}(valid versions: \"v2\") - v1 is temporarily turned off")  
    else:
        log.error(f"Invalid graph tyle {graphtype}(valid graph types: \"minigraph\" or \"MC\")")
        return
    settings = {
        "GRAPHTYPE": graphtype,
        "VERSION": version,
        "DEBUG_SMALL_GRAPHS": debug_small_graphs,
        "MINNODELENGTH": minnodelen,
        "NODESEGLEN": nodeseglen,
        "EDGELEN": edgelen,
        "NODELENPERMB": nodelenpermb
    }
    
    pggraph = bandage_graph.PGGraph(str(postprocess_gfa_output), settings)
    pggraph.BuildOGDFGraph()
    if linear:
        #more input validation may be required but tbd
        parts = assembly.split('#')
        sample = parts[0]
        haplotype = parts[1] if len(parts) > 1 else None
        ag = adaptagrams_converter.AdaptagramsGraph(pggraph)
        ag.seed_linear_layout(assembly=sample, haplotype=haplotype)
        ag.build_fd_layout().run()
    else:
        pggraph.LayoutGraph()
    assembly_range = adjustAssemblyRangeList(pggraph.pgassemblies) # {assembly_id1: {"sequence_id": seq_id, "region": 1000-2000}, assembly_id2: ...}
    # TODO adjust take in non duplicated coordinates if it's not from the right contig. Can look into real cases before this adjustment
    
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
            if linear:
                resolved = ag.resolve(pgnodes)
                odgf_coordinates = [{"x": x, "y": y} for x, y in ag.get_segment_coordinates(resolved)] if resolved else []
            else:
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
    
    #free up refs
    if linear:
        ag.close()

    return JSONResponse(content=data)
