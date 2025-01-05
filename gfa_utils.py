"""
Utilities for dealing with GFA files for minigraph
"""

import logging
import os
from shutil import which
import subprocess
import tempfile
from pathlib import Path
from panct.utils import Region


def extract_region_from_gfa(gfa_file: Path, region: Region) -> str:
    """
    Extract GFA for a region from an indexed GFA file

    Parameters
    ----------
    gfa_file : Path
        Path to GFA file. Must be indexed
    region : Region
        Region to extract

    Returns
    -------
    gfa_file : str
        Path to subgraph GFA file
    """
    tmpfile = tempfile.NamedTemporaryFile(delete=False)

    cmd = [
        "gfabase",
        "sub",
        str(gfa_file) + "b",
        "-o", tmpfile.name,
        str(region.chrom) + ":" + str(region.start) + "-" + str(region.end),
        "--range",
        "--view",
    ]
    
    proc = subprocess.run(cmd, stdout=subprocess.PIPE)
    if proc.returncode != 0:
        return None
    else:
        return tmpfile.name


def check_gfabase_installed(log: logging.Logger):
    """
    Check that gfabase is installed

    Returns
    -------
    passed : bool
       True if gfabase is found
    """
    if which("gfabase") is None:
        log.warning("Could not find gfabase")
        return False
    return True


def index_gfa(gfa_file: Path, gfab_file: Path):
    """
    Index the GFA file

    Parameters
    ----------
    gfa_file : Path
        Path to the GFA file
    gfab_file: Path
        Path to the indexed gfab file

    Returns
    -------
    passed : bool
        True if we were able to create the .gfab file and add mappings into the .gfab file
    """
    cmd_load = ["gfabase", "load", "-o", gfab_file, gfa_file]
    proc_load = subprocess.run(cmd_load, stdout=subprocess.PIPE)
    if proc_load.returncode != 0:
        log.critical(proc_load.stdout)

    return proc_load.returncode == 0


def check_gfafile(gfa_file: Path, log: logging.Logger):
    """
    Check if the gfa file exists and is
    indexed by gfabase

    Parameters
    ----------
    gfa_file : Path
        Path to the GFA file
    log : logging.Logger

    Returns
    -------
    passed : bool
        True if GFA file and gfab database exist
    """
    if not gfa_file.exists():
        log.critical(f"{gfa_file} does not exist\n")
        return False
    if not os.path.exists(str(gfa_file) + "b"):
        log.info(f"{gfa_file}b does not exist. Attempting to create")
        if not index_gfa(gfa_file, Path(str(gfa_file) + "b")):
            log.critical("Failed to create GFA index")
            return False
    return True