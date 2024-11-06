from fastapi import Depends, FastAPI, Header, HTTPException
from typing_extensions import Annotated
import requests
import sys
from panct import gbz_utils

app = FastAPI()

@app.get("/subgraph/")
async def read_items(chromosome: str, start: int, end: int, graphtype: str, genome: str, gene: bool):
    return
    # gfa_p = gbz_utils.extract_region_from_gbz("./data/hprc-v1.1-mc-grch38.gbz")
    # return gfa_p

def get_gene_annot(genome: str, chromosome: str, start: int, end: int):
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