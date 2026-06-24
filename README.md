# About Pangenome-api
*source links: [UCSD PangenomeAPI](https://pangenome-api.ucsd.edu:8000/docs) | [UCSD Pangenome Browser](https://pangenome.ucsd.edu/)*

Pangenome-api is the backend API that powers the [Pangenome Browser](https://pangenome.ucsd.edu/). Using the pangenome reference and tools from the Human Pangenome Reference Consortium (HPRC).

Given a genomic region, the Pangenome-api returns the  corresponding pangenome graph coordinate of either minigraph or minigraph-cactus, using either Bandage or Sequence Tube Map(TODO:reference) algorithms. Each response includes aggregated metadata - populations, pclai, and assembly coordinates - mapped onto the graph structure. Pangenome-api uses GRCh38 coordinates only.


## How to Use

Open the pangenome-api documentation page [here](https://pangenome-api.ucsd.edu:8000/docs). Follow these steps: 
- expand the endpoint of interest
- check its parameters and their definitions
- click **Try it out**
- enter your parameters
- click **Execute**

The page will display the request URL and the response body. You can also copy the request URL and open it directly in your browser.

> [!NOTE]
> When the response is very large, the page may not render the request URL and response body. If that happens, use the approach below to open and adjust the URL directly.

Alternatively, you can call the API directly by editing the query parameters in the URL. The links below are good starting points — changing the value after each `=` sign will update the corresponding parameter and the response.

Default link for `/json`
```
https://pangenome-api.ucsd.edu:8000/json?chrom=chr1&start=25240000&end=25460000&graphtype=minigraph&version=v2&debug_small_graphs=false&minnodelen=5&nodeseglen=20&edgelen=5&nodelenpermb=1000
```

Default link for `/seqtubemap`
```
https://pangenome-api.ucsd.edu:8000/seqtubemap?chrom=chr1&start=25251923&end=25252095&version=v2&pathnumoption=compressed&nodewidthoption=compressed
```

## Functions

### json
(TODO: change function name to bandage)

`json` function uses the Bandage layout. It takes a genomic region, and returns a JSON file of the queired region with Bandage coordinates and metadata.

> [!WARNING]
> json is currently only available for minigraph v2.

> [!NOTE]
> Due to the tools and commands we used, regions returned with minigraph always extends beyond the actual queried regions on both side. Please check the actual region and the queried region in the json output for more details.

#### Parameters

##### General parameters

General parameters define the region and data requested.

- `chrom`: `str` — Chromosome to query. Example: "`chr5`", "`chrX`"
- `start`: `int` — Start coordinate of the queried region
- `end`: `int` — End coordinate of the queried region
- `graphtype`: `str` — `mc` (minigraph-cactus) or `minigraph`
- `version`: `str` — HPRC reference version: `v1` (release 1) or `v2` (release 2)

##### Bandage-specific parameters

Bandage-specific parameters define the visualization, including the drawn length of nodes and edges.

- `debug_small_graphs`: `bool` — If true, each node's drawn length equals its base-pair length
- `minnodelen`: `float` — Minimum node length to draw. If a node's drawn length fall below `minnodelen`, it is set to `minnodelen`
- `nodeseglen`: `float` — Node length for each OGDF node (TODO)
- `edgelen`: `float` — Drawn edge length between nodes
- `nodelenpermb`: `float` — Scaling factor for drawn node length, computed as `nodelenpermb * node_length_in_bp / 1,000,000`

#### Output

`json` output a JSON file with bandage coordinates and metadata attached to graph structures

Example of `json` output with a short annotation of each entry: 
```json
{
    "queried_locus": "GRCh38#0#chr1:25240000-25460000",                  # region the user requested
    "actual_locus": "GRCh38#0#chr1:25200904-25582458",                   # region actually returned
    "node": {                                                            # dictionary of all the nodes in the requested region
        "5504+": {
            "name": "5504+",
            "length": 35895,                                             # base-pair length of the node
            "assembly": [                                                # list of assemblies that this node goes through, with associated metadata that binds to each node-assembly pair
                {
                    "assembly_name": "HG00408",                          # TODO: change to sample_name?
                    "haplotype": "1",
                    "metadata": [
                        {
                            "sequence_id": "JBHDVK010000002.1",          # contig of this assembly (HG00408#1) that this node (5504) goes through
                            "path_strand": "+",                          # path strand in the mapping file (see Additional Information)
                            "node_strand": "\u003E",                     # node strand in the mapping file (see Additional Information)
                            "start": 25931795,                           # start coordinate of this node in this contig (HG00408#1#JBHDVK010000002.1)
                            "end": 25967693,                             # end coordinate of this node in this contig (HG00408#1#JBHDVK010000002.1)
                            "pclai_hg38": {                              # GRCh38 coordinate-based PCLAI data of this node-assembly pair (node 5504 in HG00408#1)
                                "pclai_coord_system": "GRCh38",
                                "coordinates": [0.762, 1.382],           # predicted PCLAI coordinate in the PCA space
                                "RGB": [255, 114, 53],                   # associated color in the PCA space
                                "confidence_score": "997"                # confidence score of the predicted PCLAI coordinate (if marked as "impainted", we applied impainting methods to obtain the PCLAI data of this node and no confidence score is available; see Additional Information for more details)
                            },
                            "pclai_asm": {                               # assembly coordinate-based PCLAI data of this node-assembly pair (node 5504 in HG00408#1)
                                "pclai_coord_system": "assembly",
                                "coordinates": [0.765, 1.384],
                                "RGB": [255, 114, 53],
                                "confidence_score": "impainted"
                            },
                            "take": "yes"
                        }
                    ]
                },
                ...
            ]
            "duplicated_assembly": [],                                   # if this node got mapped twice to two separate coordinates in this assembly, they will be listed here. The likelihood of one coordinate being the "ground truth" is large when we mark "take" as "yes"
            "assembly_metadata": {                                       # population metadata of this node
                "count": {                                               # for each population category, the number of assemblies that has this node (5504)
                    "sex": { "female": 232, "male": 232 },
                    "superpopulation": {"AFR": 140, ...},
                    "population": {"ACB": 24, ...}
                },
                "frequency": {                                           # for each population category, the frequency of assemblies that has this node (5504) - number_of_assemblies_that_have_the_node / total_number_of_assemblies_in_this_population_category
                    "sex": { "female": 1.0, "male": 1.0 },
                    "superpopulation": {"AFR": 1.0, ... },
                    "population": {"ACB": 1.0, ... }
                }
            },
            "default_range": "GRCh38#0#chr1:25200904-25236799",          # the coordinate of this node as listed in the reference file
            "ogdf_coordinates": [                                        # drawn coordinates from Bandage
                { "x": 5696.0, "y": 2560.0 },
                { "x": 5464.0, "y": 2413.0 },
                { "x": 5162.0, "y": 2221.0 }
            ]
        },
        ...
    },
    "edge": [                                                            # list of edges from the requested region
        { "starting_node": "5504+", "ending_node": "5505+" },
        { "starting_node": "5504+", "ending_node": "618382+" },
        { "starting_node": "5505+", "ending_node": "5506+" },
        ...
    ],
    "sequence": {                                                        # list of the full sequence of each node
        "5504+":"AGATGAGGTCTC...",
        "5505+":"GTGTGGTAAAAA...",
        "5506+":"CTCTCTTGCCCA...",
        ...
    },
    "assembly": {                                                        # list of all assemblies with the contig and coordinates of where the requested region falls into
        "HG00408#1": {
            "sequence_id": "JBHDVK010000002.1",                          # contig of assembly HG00408#1 where the requested region falls
            "region": "25931795-26244085"                                # coordinates of assembly HG00408#1 where the requested region falls
        },
        "HG00597#1": { 
            "sequence_id": "CM085766.1", 
            "region": "25491473-25873995" 
        },
        ...
    }
}
```

#### Additional information

For details on how some of the data in the `json` output was generated, see [Additional Details](./docs/details.md).

### seqtubmap

`seqtubemap` uses Sequence Tube Map layout. It takes a genomic region, and directly returns a svg with all the metadata lies within.

> [!WARNING]
> seqtubemap is currently only available for minigraph-cactus.

#### Parameters

- `chrom`: `str` — Chromosome to query. Example: "`chr5`", "`chrX`"
- `start`: `int` — Start coordinate of the queried region
- `end`: `int` — End coordinate of the queried region
- `graphtype`: `str` — `mc` (minigraph-cactus) or `minigraph`
- `version`: `str` — HPRC reference version: `v1` (release 1) or `v2` (release 2)
- `pathnumoption`: `str` - options for the number of path: "compressed"(compress same path as one single path) or "normal" (show each path seperately)
- `nodewidthoption`: `str` - options for the width of sequence nodes:"compressed"(scale node width with log2 of number of bp) or "normal"(scale node width linearly with number of bp)

#### Output

`seqtubemap` directly returns the Sequence Tube Map layout of the requested region in svg format.

## Installation
 
Installation is not needed if you are not intended to change our source code. If you would like to modify our code or add your own datasets or functions, follow [this instruction](./docs/installation.md) to install pangenome-api on your local machine. 