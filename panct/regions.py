"""
Utilities for processing regions
"""

from __future__ import annotations
import re
from typing import Type


class Region:
    """
    Store information about a genomic region

    Attributes
    ----------
    chrom : str
        Chromosome
    start : int
        Start coordinate
    end : int
        End coordinate
    """

    def __init__(self, chrom: str, start: int, end: int):
        self.chrom = chrom
        self.start = start
        self.end = end

    @classmethod
    def read(cls: Type[Region], region: str) -> Region:
        """
        Extract chrom, start, end from coordinate string

        Parameters
        ----------
        region : str
            Coordinate string in the form 'chrom:start-end'

        Returns
        -------
        region : Region
            Region object

        Raises
        ------
        ValueError
            If the region region string could not be parsed
        """
        if type(region) != str:
            raise ValueError(f"Problem parsing coordinates {region}. Invalid type")
        if re.match(r"\w+:\d+-\d+", region) is None:
            raise ValueError(f"Problem parsing coordinates {region}")
        chrom = region.split(":")[0]
        start = int(region.split(":")[1].split("-")[0])
        end = int(region.split(":")[1].split("-")[1])
        if start >= end:
            raise ValueError(f"Problem parsing coordinates {region}. start>=end")
        return cls(chrom, start, end)