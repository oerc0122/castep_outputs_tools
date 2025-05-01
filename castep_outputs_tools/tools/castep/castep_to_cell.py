"""Convert .castep, .md or .geom to castep cell files."""

import argparse
import sys
from argparse import ArgumentParser
from operator import itemgetter
from pathlib import Path
from typing import Literal, TextIO

from castep_outputs import parse_castep_file, parse_md_geom_file, parse_single
from castep_outputs.parsers.md_geom_file_parser import MDGeomTimestepInfo

from castep_outputs_tools.tools.md.md_geom_parser import MDGeomParser
from castep_outputs_tools.utils.castep_dumper import castep_dumper
from castep_outputs_tools.utils.tool import Tool

_PARSERS = {"castep": parse_castep_file, "md": parse_md_geom_file, "geom": parse_md_geom_file}
Parsers = Literal["castep", "md", "geom"]


def _nop(x):
    return x


def atreg_to_list(dict_in: dict, subelem: str | None = None, *, no_ind=False):
    """Transform an atreg block to a list."""
    getter = _nop if subelem is None else itemgetter(subelem)

    return [
        (*(atom[0:1] if no_ind else atom), *getter(ind))
        for atom, ind in dict_in.items()
        if isinstance(atom, tuple)
    ]


def _get_md_geom_struct(parsed: MDGeomTimestepInfo) -> dict:
    """Get structure from a parsed .md or .geom file."""
    accum = {}
    accum["lattice_cart"] = parsed["lattice_vectors"]
    accum["positions_abs"] = atreg_to_list(parsed["ions"], "R", no_ind=True)
    if "V" in next(iter(parsed["ions"].values()), {}):
        accum["ionic_velocities"] = [ion["V"] for ion in parsed["ions"].values()]

    return accum


def _get_castep_struct(parsed: dict, frame: int = -1):
    """Get structure from a parsed .castep file."""
    accum = {}

    if "geom_opt" in parsed:
        source = "Geometry Optimisation"
        if "final_configuration" not in parsed["geom_opt"]:
            raise KeyError(
                "Cannot find final configuration, are you sure your geom opt ran to completion?",
            )

        data = parsed["geom_opt"]["final_configuration"]
        if "atoms" in data:
            accum["positions_frac"] = atreg_to_list(data["atoms"], no_ind=True)
        else:
            accum["positions_frac"] = atreg_to_list(parsed["initial_positions"], no_ind=True)

        if "cell" in data:
            accum["lattice_cart"] = data["cell"]["real_lattice"]
        else:
            accum["lattice_cart"] = parsed["initial_cell"]["real_lattice"]

    elif "md" in parsed:
        source = "Molecular Dynamics"
        data = parsed["md"][frame]

        accum["positions_frac"] = atreg_to_list(data["positions"], no_ind=True)

        if "cell" in data:
            accum["lattice_cart"] = data["cell"]["real_lattice"]
        else:
            accum["lattice_cart"] = parsed["initial_cell"]["real_lattice"]

    else:
        if frame != -1:
            raise ValueError("Reading from a .castep file must take the default frame.")

        source = "Initial positions"
        accum["positions_frac"] = atreg_to_list(parsed["initial_positions"], no_ind=True)
        if "initial_velocities" in parsed:
            accum["ionic_velocities"] = list(parsed["initial_velocities"].values())
        accum["lattice_cart"] = parsed["initial_cell"]["real_lattice"]

    return accum, source


def get_parser() -> ArgumentParser:
    """Get the argument parser for this script."""
    arg_parser = ArgumentParser(
        prog="castep2cell",
        description="Simple .castep, .md, .geom to .cell tool.",
    )

    arg_parser.add_argument("file", help="Source file to convert", type=Path)
    arg_parser.add_argument("-o", "--output", help="File to dump to, default: screen", default=None)
    arg_parser.add_argument(
        "-f", "--format", help="Parse FILE as this type", choices=_PARSERS.keys(),
    )
    arg_parser.add_argument("-F", "--frame", help="Parse given frame", type=int, default=-1)

    return arg_parser


def main(
    source: str | Path | TextIO,
    out_file: str | Path | TextIO,
    *,
    frame: int = -1,
    source_format: Parsers | None = None,
) -> None:
    """Convert .castep/.md/.geom to .cell format."""
    if isinstance(source, TextIO):
        name = None

        if source_format is None:
            raise TypeError("For parsing open file, must give explicit source_format.")

        fmt = source_format
    else:
        if isinstance(source, str):
            source = Path(source)

        name = str(source)
        fmt: Parsers = source_format if source_format is not None else source.suffix[1:]

    if fmt not in _PARSERS:
        raise OSError(f"Do not know how to parse '{fmt}' file.")

    if fmt == "castep":
        parsed = parse_single(source, parser=_PARSERS.get(fmt))[-1]
        accum, calc = _get_castep_struct(parsed, frame)

    else:
        calc = "MD/Geometry run"
        if isinstance(source, Path | str):
            parsed = MDGeomParser(source)
        else:
            parsed = parse_single(source, parser=_PARSERS.get(fmt))

        accum = _get_md_geom_struct(parsed[frame])

    castep_dumper(out_file, accum, name, calc)


def _run(args: argparse.Namespace) -> None:
    """Run the main calculation."""
    file = args.file
    if not file.exists():
        raise FileNotFoundError(f"File {file} not found.")

    fmt = args.format if args.format else args.file.suffix[1:]
    if fmt not in _PARSERS:
        raise OSError(f"Do not know how to parse '{fmt}' file.")

    output = args.output if args.output else sys.stdout

    main(file, output, fmt=fmt, frame=args.frame)


def cli() -> None:
    """Parse file and dump as castep .cell format."""
    arg_parser = get_parser()
    args = arg_parser.parse_args()
    _run(args)


_tool_ = Tool(arg_parser=get_parser, run=_run)

if __name__ == "__main__":
    cli()
