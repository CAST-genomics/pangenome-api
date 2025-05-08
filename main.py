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

mc_hg38_gbz = Path("/data/hprc-v1.1-mc-grch38.gbz")
minigraph_hg38_gfa = Path("/data/hprc-v1.0-minigraph-grch38.gfa")

#TODO add gfa_output
def SubgraphMC(query_region, gfa_output, log, reference_gbz):
    
    # check gbz.db file and create subgraph
    if not gbz.check_gbzfile(reference_gbz, log):
        gbz.index_gbz(reference_gbz)
    subgraph_gfa = gbz.extract_region_from_gbz(reference_gbz,query_region,"GRCh38", gfa_output)
    if subgraph_gfa is None:
        log.error("Subset GFA is None")

def SubgraphMini(query_region, gfa_output, log, reference_gfa):
    
    # check gbz.db file and create subgraph
    gfa.check_gfabase_installed(log)
    gfa.check_gfafile(reference_gfa, log)
    
    subgraph_gfa = gfa.extract_region_from_gfa(reference_gfa,query_region,gfa_output)
    if subgraph_gfa is None:
        log.error("Subset GFA is None")

# for debugging only - this page will output parsed gfa content in dictionary 
# TODO update the the filename when calling gfa related
@app.get("/subgraph/gfa/debug/")
async def read_items(chrom: str, start: int, end: int, graphtype: str):
    """
    get the GFA format of queried region

    Parameters
    ----------
    chrom : str
        example: "chr5, chrX"
    start : int
    end: int
    graphtype: str
        MC (minigraph-cactus), or Minigraph
    
    Returns
    -------
    GFA file content : dict
        GFA format of the specific region queried
    """

    log = getLogger(name="complexity", level="INFO")
    
    tempfile.tempdir = Path(__file__).parent.joinpath(".")
    query_region = Region(chrom, start, end)

    # create minigraph cactus GFA subgraph
    if graphtype == "MC" or graphtype == "mc":
        gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}.gfa")
        if not gfa_output.exists():
            SubgraphMC(query_region, gfa_output, log, mc_hg38_gbz)
    
    # create minigraph GFA subgraph
    elif graphtype == "minigraph":
        gfa_output = Path(f"./cache/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}.gfa")
        if not gfa_output.exists():
            SubgraphMini(query_region, gfa_output, log, minigraph_hg38_gfa)
    
    else:
        # return error message WIP
        return
    
    output_gfa = {"H":[], "S":[], "L":[], "J":[], "C":[], "W":[]}
    with open(gfa_output, 'r') as gfa_file:
        for line in gfa_file:
            gfa_line = line.strip().split("\t")
            gfa_line = [int(num) if num.isdigit() else str(num) for num in gfa_line]
            output_gfa[gfa_line[0]].append(gfa_line)
    
    # keep track of file size
    with open("size_track.txt", "a") as size_tracking:
        size_tracking.write(f"file name: {str(gfa_output)}, file size: {os.path.getsize(gfa_output)/(1024*1024)}")
    
    # TODO remove gfa_output if the size is too big

    return output_gfa

@app.get("/json")
async def read_items(    
    chrom: str = Query(..., description='Chromosome, e.g. `"chr5, chrX"`'),
    start: int = Query(..., description="Start coordinate"),
    end: int = Query(..., description="End coordinate"),
    graphtype: str = Query(..., description='Graph type: `"MC"` (minigraph-cactus) or `"Minigraph"`'),
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
    - `graphtype`: str — `"MC"` (minigraph-cactus) or `"Minigraph"`
    - `debug_small_graphs`: bool — If true, each node's length = number of basepairs
    - `minnodelen`: float — Minimum node length to draw
    - `nodeseglen`: float — Node length for every OGDF node
    - `edgelen`: float — Edge length between nodes
    - `nodelenpermb`: float — Drawn node length scaling factor

    ## Returns

    - **GFA file content**: `dict`  
      GFA format of the specific region queried.
    """
    log = getLogger(name="complexity", level="INFO")
    
    query_region = Region(chrom, start, end)

    # create minigraph cactus GFA subgraph
    if graphtype == "MC" or graphtype == "mc":
        gfa_output = Path(f"./cache/mc/subgraph_{chrom}_{str(start)}_{str(end)}.gfa")
        if not gfa_output.exists():
            SubgraphMC(query_region, gfa_output, log, mc_hg38_gbz)
    # create minigraph GFA subgraph
    elif graphtype == "minigraph":
        gfa_output = Path(f"./cache/minigraph/subgraph_{chrom}_{str(start)}_{str(end)}.gfa")
        if not gfa_output.exists():
            SubgraphMini(query_region, gfa_output, log, minigraph_hg38_gfa)
    else:
        log.error(f"Invalid graph tyle {graphtype}(valid graph types: \"minigraph\" or \"MC\")")
        return
    settings = {
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
            node_info["assembly"] = pgnodes.m_assembly
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


@app.post("/subgraph/svg/")
async def read_items(settings: Settings):
    log = getLogger(name="complexity", level="INFO")
    
    query_region = Region(settings.chr_input, settings.start_loc_input, settings.end_loc_input)

    # create minigraph cactus GFA subgraph
    if settings.graph_type == "MC" or settings.graph_type == "mc":
        gfa_output = Path(f"./cache/mc/subgraph_{settings.chr_input}_{str(settings.start_loc_input)}_{str(settings.end_loc_input)}.gfa")
        if not gfa_output.exists():
            SubgraphMC(query_region, gfa_output, log, mc_hg38_gbz)
    # create minigraph GFA subgraph
    elif settings.graph_type == "minigraph":
        gfa_output = Path(f"./cache/minigraph/subgraph_{settings.chr_input}_{str(settings.start_loc_input)}_{str(settings.end_loc_input)}.gfa")
        if not gfa_output.exists():
            SubgraphMini(query_region, gfa_output, log, minigraph_hg38_gfa)
    else:
        log.error(f"Invalid graph tyle {settings.graph_type}(valid graph types: \"minigraph\" or \"MC\")")
        return
    settings_dict = settings.model_dump()
    pggraph = bandage_graph.PGGraph(str(gfa_output), settings_dict)
    pggraph.BuildOGDFGraph()
    pggraph.LayoutGraph()
    graphPlotter = graph_plotter.GraphPlotter(pggraph, settings_dict)
    svgFile = graphPlotter.BuildSvg()
    
    with open(svgFile, "r") as file:
        content = file.read()
    os.remove(svgFile)
    
    return {"svg": content}

@app.get("/geneannot/")
async def get_gene_annot(genome: str, chromosome: str, start: int, end: int):
    # start-end can't do too large, need to choose a cap
    api_url = f"https://api.genome.ucsc.edu/getData/track?genome={genome};track=knownGene;chrom={chromosome};start={start};end={end}"
    url_dict = requests.get(api_url).json()
    all_genes = url_dict["knownGene"]
    gene_list = {}
    for gene in all_genes:
        gene_info = {}
        gene_info["chromosome"] = gene["chrom"]
        gene_info["start"] = gene["chromStart"]
        gene_info["end"] = gene["chromEnd"]
        gene_info["tag"] = gene["tag"]
        gene_name = gene["name"]
        gene_list[gene_name] = gene_info
    return gene_list