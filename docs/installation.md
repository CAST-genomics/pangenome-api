# How to Install PangenomeAPI Locally

Follow these instructions to install PangenomeAPI on your local machine. This guide is intended for people who want to modify our code or add their own datasets or functions. If you don't plan to extend the API, we recommend using our [official PangenomeAPI](https://pangenome-api.ucsd.edu:8000/docs) instead, which is easier to access.

Additional links to get started with pangenome-api and the Pangenome Browser it powers, see:
- [How to use the PangenomeAPI](../README.md)
- [Official PangenomeAPI](https://pangenome-api.ucsd.edu:8000/docs)
- [Official Pangenome Browser](https://pangenome.ucsd.edu/)

## Install With Docker

### Install Docker
The required tools for this project are the Docker Engine, some method to interface with it (e.g. the Docker CLI client), and Docker Compose.

The easiest, most convenient, and most platform agnostic way of ensuring all dependencies are met is through the installation of [Docker Desktop](https://docs.docker.com/desktop/), which bundles all the necessary tools together (and more), though there are other methods should one want to minimize unecessary bloat.

### Repo Setup
By default the reference data ([download instructions](#download-reference-data-files)) should live in a *sibling* directory titled `/data`.
```
/some-root
    /data
        *.gbz
        *.gfa
        ...
    /pangenome-api
        ...
```
This is to prevent the large data files being included in Docker's build cache.

If you wish to specify a different directory, add the following to a file named `.env`:
```
DATA_DIR=path/to/data
```
Where `path/to/data` is replaced with the actual path to your data directory.

### First Time Run
Simply run
```bash
docker compose up --build
```
This will build the image (`Dockerfile`), then mount the necessary volumes and start the fastapi server (`docker-compose.yml`).
> [!NOTE]
> The first build will take a while (~10 minutes) as some dependencies are compiled.
> Future builds will be significantly shorter, since each build step will be cached.

> [!NOTE]
> `docker compose up` will run the command `fastapi dev --host "0.0.0.0" main.py` by default.
> The command can be changed by editing `docker-compose.yml`.
> Different commands can be executed in a running container with `docker compose exec api [command]`

### Future Runs
The `--build` flag can be omitted in future runs. It only needs to be included if `Dockerfile` was updated.

Optionally, to run the container detached from the terminal, the `-d` flag can be included. This is not recommended
for development, as it makes logs more difficult to access.

### Stopping the Image
Simply run
```bash
docker compose down
```
This will stop the running image and free up the space it occupied.

### Dev Containers
A dev container configuration file has been included. This can be used for convenient local development in VSCode.
More information about using dev containers can be found in [this article from its developers](https://code.visualstudio.com/docs/devcontainers/containers),
but it should work out of the box if the extension is installed.

## Install Without Docker

### Clone Pangenome-api

```
git clone https://github.com/CAST-genomics/pangenome-api
```

### Install Dependencies

We recommand installing inside a conda environment:

```bash
# create a conda environment for pangenome-api
conda create -n pangenome-api python=3.11
conda activate pangenome-api

# install Python packages
pip install -r requirements.txt
pip install 'ogdf-python[quickstart]'

# install node.js and node packages
conda install -c conda-forge nodejs=24.9.0

# install vg
conda install -c bioconda vg

# move to the pangenome-api directory
cd pangenome-api
npm ci
```

gbz-base and gfabase Rust tools that we use for subgraphing. Please follow the links below to build these tools from source.
- gbz-base: https://github.com/jltsiren/gbz-base
- gfabase: https://github.com/mlin/gfabase/tree/main 
    - Follow the installation process, and adjust these lines before running `./cargo build --release`
        - **Cargo.toml.in**: change `clap = "3.0.0-beta.2"` to `clap = { version = "3.0.0-beta.2", features = ["derive"] }`
        - **add_mappings.rs, load.rs, main.rs, sub.rs, view.rs**: change `use clap::Clap;` to `use clap::Parser;`, change `#[derive(Clap)]` to `#[derive(Parser)]`
    - TODO: test the updated versions for mac and linux

To enable calling the gfabase and gbz-base without specializing their path, you can add the executable path to your system with the following command

```txt
#TODO
```

### Download Reference and Walk Files
TODO: would be best if we can store all the large data files in a s3 folder

The PangenomeAPI requires a set of datasets, including the pangenome reference and the `.walk` files, which contain metadata associated with each node. You can download these datasets as instructed below and store then in a user defined data folder. We recommand creating the data folder outside of the pangenomeAPI repository to avoid any conflict with git and docker. 

List of datasets required:

**Reference File**
- 3.1G, [GRCh38 minigraph version1 reference](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph/hprc-v1.0-minigraph-grch38.gfa.gz), `hprc-v1.0-minigraph-grch38.gfa.gz`
- 3.3G, [GRCh38 minigraph version2 reference](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/scratch/2025_02_28_minigraph_cactus/hprc-v2.0-mc-grch38/hprc-v2.0-mc-grch38.sv.gfa.gz), `hprc-v2.0-mc-grch38.sv.gfa.gz`
(TODO: add functions to modify minigraph v2 reference file; unzip if gzipped)
- 5.6G, [GRCh38 minigraph cactus version 1 reference](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.gbz), `hprc-v1.1-mc-grch38.gbz`
- 8.7G, [GRCh38 minigraph cactus version 2 reference](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/scratch/2025_02_28_minigraph_cactus/hprc-v2.0-mc-grch38/hprc-v2.0-mc-grch38.gbz), `hprc-v2.0-mc-grch38.gbz`

**Walk File**
- 9.9M, minigraph version1 walk file, `hprc_v1.0_minigraph_filtered_with_id.walk.gz`
- 415, minigraph version1 walk file (tabix), `hprc_v1.0_minigraph_filtered_with_id.walk.gz.tbi`
- 3.5G, minigraph version2 walk file, `v1_1_hprc_v2.0_minigraph.sorted.pclai.walk.gz`
- 688, minigraph version2 walk file (tabix),  `v1_1_hprc_v2.0_minigraph.sorted.pclai.walk.gz.tbi`
- 3.3G, minigraph cactus version1 walk file, `hprc-v1.1-mc-grch38-mapped-flattened.walk.gz`
- 76K, minigraph cactus version1 walk file (tabix), `hprc-v1.1-mc-grch38-mapped-flattened.walk.gz.tbi`
- 250G, minigraph cactus version2 walk file, `hprc-v2.0-mc-grch38.walk.gz`
- 157K, minigraph cactus version2 walk file (tabix), `hprc-v2.0-mc-grch38.walk.gz.tbi`

In git config, add the path to where you store these data files
```
git config --local data.path [PATH_TO_DATA_DIR_WITH_MINIGRAPH_AND_MINIGRAPH-CACTUS_GFA]
```

### Run Pangenome-api
For local development:
```
fastapi dev main.py
```

Once the server is running, the interactive API docs will be available at <http://127.0.0.1:8000/docs>.

From there, expand an endpoint, click **Try it out**, enter the parameters, and click **Execute** to send the request. The docs page shows the generated request URL along with the response. Alternatively, you can call the API directly by editing the query parameters in the URL.

If you need an HTTPS deployment, run the server with certificates:
```
uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --ssl-keyfile /path/to/your.key \
  --ssl-certfile /path/to/your.pem
```

> [!WARNING]
> current restrictions for the API during development
>
> - json is only available for minigraph v2.
> - seqtubemap is only available for minigraph-cactus

> [!NOTE]
> the api will take around 5 minutes to load when it is deployed for the first time to indexing the .gbz and .gfa reference files