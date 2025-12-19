# pangenome-api

This is the backend API of the Pangenome Browser.

## How to Install
 
 If you are using the AWS instance, you can skip this part and directly navigate to the [How to Use](#how-to-use) section. If you are using the pangenome-api on your own computer instead, please follow the steps below to install. (Note that the gfabase associated to minigraph subgraph extraction are not compatible with the MacOS system)

#### Step 1: Clone the repository

#### Step 2: Install gbz-base and gfabase 
- gbz-base: https://github.com/jltsiren/gbz-base
- gfabase: https://github.com/mlin/gfabase/tree/main 
    - Follow the installation process, and adjust these lines before running `./cargo build --release`
        - **Cargo.toml.in**: change `clap = "3.0.0-beta.2"` to `clap = { version = "3.0.0-beta.2", features = ["derive"] }`
        - **add_mappings.rs, load.rs, main.rs, sub.rs, view.rs**: change `use clap::Clap;` to `use clap::Parser;`, change `#[derive(Clap)]` to `#[derive(Parser)]`
- panct: https://github.com/CAST-genomics/panCT.git

#### Step 3: Install python packages
```
pip install pathlib fastapi 
```

#### Step 4: Download the graph files and store them in a data folder

- [Minigraph-Cactus GRCh38](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.gbz)
- [Minigraph GRCh38](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph/hprc-v1.0-minigraph-grch38.gfa.gz)

We use the database from HPRC which you can find more through [this link](https://github.com/human-pangenomics/hpp_pangenome_resources?tab=readme-ov-file#minigraph-cactus).

#### Step 5: Add the source directories to git config
```
git config --local tools.path [PATH_TO_TOOL_DIR_WITH_PANCT]
git config --local data.path [PATH_TO_DATA_DIR_WITH_MINIGRAPH_AND_MINIGRAPH-CACTUS_GFA]
```

## How to Use:
In the pangenome-api folder, run:
```
fastapi dev main.py
```
You can then open the interactive API doc at http://127.0.0.1:8000/docs.

![fastapi_doc](/image/fastapi_doc.png)

Click "try it out" and input the genome region of interest. Then click "execute" to generate the url.

Alternatively, you can run the API directly from the url ` http://127.0.0.1:8000/json?chrom=chr1&start=25280000&end=25290000&graphtype=minigraph&version=v1&debug_small_graphs=false&minnodelen=5&nodeseglen=20&edgelen=5&nodelenpermb=1000 ` by manually changing the chromosome(eg. chr1, chrX), start location, end location, and graphtype("mc" for minigraph-cactus, or "minigraph").

(Note: the api will likely take a couple of minutes to load when you run the function for the first time. The code will need to indexing the gbz file and gfa file first. This may take around 5 minutes.)

## Example:

```
http://127.0.0.1:8000/json?chrom=chr1&start=25240000&end=25460000&graphtype=minigraph&version=v1&debug_small_graphs=false&minnodelen=5&nodeseglen=20&edgelen=5&nodelenpermb=1000
```
This will return a JSON file with the nodeID, coordinates, assembly list, assembly metadata, etc. of each node, along with the corresponding edges and sequence information. 

![example](/image/example.png)