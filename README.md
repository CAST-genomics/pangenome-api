# pangenome-api

This is the API for the backend of the Pangenome Browser.

## How to Install
 
 If you are using the AWS instance, you can skip this part and directly navigate to the [How to Use](#how-to-use) section. If you are using the pangenome-api on your own computer instead, please follow the steps below to install. (Note that the minigraph functions are not compatible with the MacOS system)

#### Step 1: Clone the repository

#### Step 2: Install gbz-base and gfabase 
- gbz-base: https://github.com/jltsiren/gbz-base
- gfabase: https://github.com/mlin/gfabase/tree/main 

To check if gbz-base is correctly installed, run:

```
#gbz-base
which gbz2db
which query

#gfabase
which gfabase
```

#### Step 3: Install python packages
@@ -21,30 +29,33 @@
pip install panct pathlib fastapi 
```

#### Step 4: Download the graph files and store them in the pangenome-api folder

- [Minigraph-Cactus GRCh38](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.gbz)
- [Minigraph GRCh38](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph/hprc-v1.0-minigraph-grch38.gfa.gz)

We will use the database from HPRC which you can find more through [this link](https://github.com/human-pangenomics/hpp_pangenome_resources?tab=readme-ov-file#minigraph-cactus).

## How to Use:
In the pangenome-api folder, run:
```
fastapi dev main.py
```
You can then open the interactive API doc at http://127.0.0.1:8000/docs.

![fastapi_doc](/image/fastapi_doc.png)

Click "try it out" and input the genome region of interest. Then click "execute" to generate the url.

Alternatively, you can run the API directly from the url ` http://127.0.0.1:8000/subgraph/?chrom=chrX&start=1000&end=100000&graphtype=MC ` by manually changing the chromosome(eg. chr1, chrX), start location, end location, and graphtype("MC" for minigraph-cactus, or "minigraph").

(Note: the api will likely take a couple of minutes to load when you run the function for the first time. The code will need to indexing the gbz file and gfa file first. This may take around 5 minutes.)

## Example:

```
http://127.0.0.1:8000/subgraph/?chrom=chrX&start=100000&end=150000&graphtype=MC
```
This will return a Minigraph-cactus(MC) GFA stored in a dictionary of a region in chromosome X, starting from 100000bp, and ending at 150000bp.

![example](/image/example.png)