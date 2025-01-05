from fastapi import FastAPI
import requests
from panct import gbz_utils as gbz
from panct.logging import getLogger
from panct.utils import Region
from pathlib import Path
import tempfile
import os
import gfa_utils as gfa

app = FastAPI()

@app.get("/subgraph/")
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
        
        # set path to gbz reference file
        mc_hg38_gbz = Path("hprc-v1.1-mc-grch38.gbz")
        
        # check gbz.db file and create subgraph
        if not gbz.check_gbzfile(mc_hg38_gbz, log):
            gbz.index_gbz(mc_hg38_gbz)
        subgraph_gfa = gbz.extract_region_from_gbz(mc_hg38_gbz,query_region,"GRCh38")
        
        # output gfa subgraph
        output_gfa = {"H":[], "S":[], "L":[], "J":[], "C":[], "W":[]}
        with open(subgraph_gfa, 'r') as gfa_file:
            for line in gfa_file:
                gfa_line = line.strip().split("\t")
                gfa_line = [int(num) if num.isdigit() else str(num) for num in gfa_line]
                output_gfa[gfa_line[0]].append(gfa_line)
        os.remove(subgraph_gfa)
        return output_gfa
    
    # create minigraph GFA subgraph
    if graphtype == "minigraph":
        
        # set path to minigraph gfa reference file
        minigraph_hg38_gfa = Path("hprc-v1.0-minigraph-grch38.gfa")
        
        # check gbz.db file and create subgraph
        gfa.check_gfabase_installed(log)
        gfa.check_gfafile(minigraph_hg38_gfa, log)
        
        subgraph_gfa = gfa.extract_region_from_gfa(minigraph_hg38_gfa,query_region)
        
        output_gfa = {"H":[], "S":[], "L":[], "J":[], "C":[], "W":[]}
        
        with open(subgraph_gfa, 'r') as gfa_file:
            for line in gfa_file:
                gfa_line = line.strip().split("\t")
                gfa_line = [int(num) if num.isdigit() else str(num) for num in gfa_line]
                output_gfa[gfa_line[0]].append(gfa_line)
        os.remove(subgraph_gfa)
        
        return output_gfa
    
    else:
        # return error message WIP
        return


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