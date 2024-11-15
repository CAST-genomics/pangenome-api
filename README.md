# pangenome-api

This is the API for the backend of the Pangenome Browser.

## How to Install

#### Step 1: Clone the repository

#### Step 2: Install gbz-base following the instructions from https://github.com/jltsiren/gbz-base

To check if gbz-base is correctly installed, run:

```
which gbz2db
which query
```

#### Step 3: Install python packages

```
pip install panct pathlib fastapi 
```

#### Step 4: Download Minigraph-Cactus GRCh38 graph [here](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.gbz) and store it in the pangenome-api folder

We will use the database from HPRC which you can find more through [this link](https://github.com/human-pangenomics/hpp_pangenome_resources?tab=readme-ov-file#minigraph-cactus). Current, our API subgraph function only support the minigraph-cactus hg38 gbz file (with name "hprc-v1.1-mc-grch38" directly downloaded from the link above).

## How to Use:
In your local pangenome-api folder, run:
```
fastapi dev main.py
```
This will run a live server. And now, you can open the interactive API doc at http://127.0.0.1:8000/docs.

![fastapi_doc](/image/fastapi_doc.png)

Click "try it out" and input the genome region of interest. Then click "execute" to generate the url.

Alternatively, you can run the API directly from the url ` http://127.0.0.1:8000/subgraph/?chrom=chrX&start=1000&end=100000&graphtype=MC ` by manually changing the chromosome, start location, end location, and graphtype.

(Note: the api will likely take a couple of minutes to load when you run the function for the first time. The code will need to indexing the gbz file to generate the gbz.db file in order for gbz-base to query the data. This may take around 5 minutes.)

## Example:

```
http://127.0.0.1:8000/subgraph/?chrom=chrX&start=100000&end=150000&graphtype=MC
```
This will return a Minigraph-cactus(MC) GFA stored in a dictionary of a region in chromosome X, starting from 100000bp, and ending at 150000bp.

![example](/image/example.png)
