from fastapi import Depends, FastAPI, Header, HTTPException
from typing_extensions import Annotated
import requests
import sys
from panct import gbz_utils
from panct.logging import getLogger
from panct.utils import Region
from pathlib import Path
import tempfile
import os

app = FastAPI()

@app.get("/subgraph/")
async def read_items(chrom: str, start: int, end: int, graphtype: str, genome: str, gene: bool):
    log = getLogger(name="complexity", level="INFO")
    tempfile.tempdir = Path(__file__).parent.joinpath("data")
    query_region = Region(chrom, start, end)
    if graphtype == "MC":
        path_hg38_gbz = Path("data/hprc-v1.1-mc-grch38.gbz")
        if not gbz_utils.check_gbzfile(path_hg38_gbz, log):
            gbz_utils.index_gbz(path_hg38_gbz)
        path_gfa = gbz_utils.extract_region_from_gbz(path_hg38_gbz,query_region,"GRCh38")
        gfa = {"H":[], "S":[], "L":[], "J":[], "C":[], "W":[]}
        with open(path_gfa, 'r') as gfa_file:
            for line in gfa_file:
                gfa_line = line.strip().split("\t")
                gfa_line = [int(num) if num.isdigit() else str(num) for num in gfa_line]
                gfa[gfa_line[0]].append(gfa_line)
        os.remove(path_gfa)
        return gfa
    else:
        return "work in progress ..."


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