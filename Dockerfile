#gbz base build step
FROM rust:1.95-slim-bookworm AS builder

#get git
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

#build gbz-base
RUN git clone https://github.com/jltsiren/gbz-base.git /build/gbz-base
WORKDIR /build/gbz-base
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/build/gbz-base/target \
    cargo build --release && \
    cp target/release/gbz2db /usr/local/bin/gbz2db && \
    cp target/release/query /usr/local/bin/query

# compile adaptagrams & generate swig bindings
# note: needs to be the same python version as runtime
FROM python:3.11-slim-bookworm AS adaptagrams-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    swig \
    autoconf \
    automake \
    libtool \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir setuptools

RUN git clone https://github.com/mjwybrow/adaptagrams.git /build/adaptagrams \
    && cd /build/adaptagrams && git checkout 840ebcff

WORKDIR /build/adaptagrams/cola
RUN mkdir -p m4 \
    && autoreconf --install --verbose \
    && ./configure \
    && make -j"$(nproc)" \
    && make -f Makefile-swig-python
    
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

COPY --from=builder /usr/local/bin/gbz2db /usr/local/bin/gbz2db
COPY --from=builder /usr/local/bin/query /usr/local/bin/query
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
RUN pip install --no-cache-dir "fastapi[standard]" pysam numpy click typer "ogdf-python==0.3.4" "ogdf-wheel==2023.9"

#install vg from precompiled static binary (instead of conda)
RUN curl -L https://github.com/vgteam/vg/releases/download/v1.75.0/vg \
    -o /usr/local/bin/vg && \
    chmod +x /usr/local/bin/vg

#install node.js from tarball (version 24.9.0)
RUN curl -L https://nodejs.org/dist/v24.9.0/node-v24.9.0-linux-x64.tar.gz \
    -o /tmp/node.tar.gz && \
    tar -xzf /tmp/node.tar.gz -C /usr/local --strip-components=1 && \
    rm /tmp/node.tar.gz

#move node modules to root since . is mounted into /app
COPY package.json package-lock.json /tmp/npm/
RUN --mount=type=cache,target=/root/.npm \
    cd /tmp/npm && npm ci && \
    mv /tmp/npm/node_modules / && \
    rm -rf /tmp/npm

# binary + bindings, and add adaptagrams to pythonpath so import finds it
COPY --from=adaptagrams-builder /build/adaptagrams/cola/adaptagrams.py /opt/adaptagrams/
COPY --from=adaptagrams-builder /build/adaptagrams/cola/_adaptagrams*.so /opt/adaptagrams/
ENV PYTHONPATH=/opt/adaptagrams
# this should be uncommented if the code is needed in the image, but with docker
# compose it shouldn't be (but with docker build it is)
# COPY . /app

RUN git config --global tools.path /opt/panct \
    && git config --global data.path /data

EXPOSE 8000