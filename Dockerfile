#gbz base build step
FROM rust:1.95-slim-bookworm AS builder

#get git
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

#build gbz-base
RUN git clone https://github.com/jltsiren/gbz-base.git /build/gbz-base
WORKDIR /build/gbz-base
RUN cargo build --release

#actual runtime
FROM python:3.11-slim-bookworm

#get git, curl, pysam system deps, and cppyy build tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    cmake \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/gbz-base/target/release/gbz2db /usr/local/bin/gbz2db
COPY --from=builder /build/gbz-base/target/release/query /usr/local/bin/query
RUN chmod +x /usr/local/bin/gbz2db /usr/local/bin/query

#install gfabase from their precompiled binary
RUN curl -L https://github.com/mlin/gfabase/releases/download/v0.6.0/gfabase-linux-x86-64 \
    -o /usr/local/bin/gfabase && \
    chmod +x /usr/local/bin/gfabase

WORKDIR /app

#install deps & panct
RUN git clone https://github.com/CAST-genomics/panCT.git /opt/panct/panCT \
    && cd /opt/panct/panCT && git checkout 03c406b

#fix ogdf and wheel to specific versions to avoid mismatch which currently exists
RUN pip install --no-cache-dir pathlib "fastapi[standard]" pysam numpy click typer "ogdf-python==0.3.4" "ogdf-wheel==2023.9"

COPY . /app

RUN git config --global tools.path /opt/panct \
    && git config --global data.path /data

EXPOSE 8000
VOLUME ["/data"]

CMD ["fastapi", "dev", "--host", "0.0.0.0", "main.py"]

# instructions to run docker image:
# build image (run from project root):
#   docker build -t pangenome-api .
# start container
#   docker run -p 8000:8000 -v /data:/data -v "$(pwd)":/app pangenome-api