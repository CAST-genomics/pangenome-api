# How to Install Pangenome-api Locally

Follow these instructions to install pangenome-api on your local machine. This guide is intended for people who want to modify our code or add their own datasets or functions. If you don't plan to extend the API, we recommend using our [official pangenome-api](https://pangenome-api.ucsd.edu:8000/docs) instead, which is easier to access.

Additional links to get started with pangenome-api and the Pangenome Browser it powers, see:
- [How to use the pangenome-api](../README.md)
- [Official pangenome-api](https://pangenome-api.ucsd.edu:8000/docs)
- [Official Pangenome Browser](https://pangenome.ucsd.edu/)

## Install With Docker

### Install Docker
The required tools for this project are the Docker Engine, some method to interface with it (e.g. the Docker CLI client), and Docker Compose.

The easiest, most convenient, and most platform agnostic way of ensuring all dependencies are met is through the installation of [Docker Desktop](https://docs.docker.com/desktop/), which bundles all the necessary tools together (and more), though there are other methods should one want to minimize unecessary bloat.

### Repo Setup
Ensure the reference data ([download instructions](#download-reference-data-files)) lives in a *sibling* directory titled `/data`.
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

```bash
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

gbz-base and gfabase are subgraphing tools built in Rust. Please follow the links below to build these tools from source.
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

### Download Reference Data Files

TODO: would be best if we can store all the large data files in a s3 folder

Add the path to the data files to git config
```
git config --local data.path [PATH_TO_DATA_DIR_WITH_MINIGRAPH_AND_MINIGRAPH-CACTUS_GFA]
```

### Run Pangenome-api
For local development:
```
fastapi dev main.py
```

Once the server is running, the interactive API docs are available at <http://127.0.0.1:8000/docs>.

From there, expand an endpoint, click **Try it out**, enter your parameters, and click **Execute** to send the request. The docs page shows the generated request URL along with the response. Alternatively, you can call the API directly by editing the query parameters in the URL.

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