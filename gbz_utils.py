"""
Utilities for dealing with GBZ files
"""

import logging
import os
from shutil import which
import subprocess
import tempfile
from pathlib import Path
from panct.utils import Region


def extract_region_from_gbz(gbz_file: Path, region: Region, reference: str, gfa_output: Path) -> str:
    """
    Extract GFA for a region from an indexed GBZ file

    Parameters
    ----------
    gbz_file : Path
        Path to GBZ file. Must be indexed
    region : Region
        Region to extract
    reference : str
        Sample to use as reference

    Returns
    -------
    gfa_file : str
        Path to GFA file
    """

    cmd = [
        "query",
        "--sample",
        reference,
        "--contig",
        region.chrom,
        "--interval",
        str(region.start) + ".." + str(region.end),
        str(gbz_file) + ".db",
    ]
    with open(gfa_output, "w") as out_file:
        proc = subprocess.run(cmd, stdout=out_file)
    if proc.returncode != 0:
        return None
    else:
        return gfa_output


def check_gbzbase_installed(log: logging.Logger):
    """
    Check that gbz2db and query from
    gbz-base are installed

    Returns
    -------
    passed : bool
       True if both tools are found
    """
    if which("gbz2db") is None:
        log.warning("Could not find gbz2db")
        return False
    if which("query") is None:
        log.critical("Could not find query")
        return False
    return True


def index_gbz(gbz_file: Path):
    """
    Index the GBZ file with gbz2db

    Parameters
    ----------
    gbz_file : Path
        Path to the GBZ file

    Returns
    -------
    passed : bool
        True if we were able to create the .gbz.db file
    """
    cmd = ["gbz2db", gbz_file]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE)
    return proc.returncode == 0


def check_gbzfile(gbz_file: Path, log: logging.Logger):
    """
    Check if the GBZ file exists and is
    indexed by GBZ-Base

    Parameters
    ----------
    gbz_file : Path
        Path to the GBZ file
    log : logging.Logger

    Returns
    -------
    passed : bool
        True if GBZ file and GBZ-base database exist
    """
    if not gbz_file.exists():
        log.critical(f"{gbz_file} does not exist\n")
        return False
    if not os.path.exists(str(gbz_file) + ".db"):
        log.info(f"{gbz_file}.db does not exist. Attempting to create")
        if not index_gbz(gbz_file):
            log.critical("Failed to create GBZ index")
            return False
    return True
