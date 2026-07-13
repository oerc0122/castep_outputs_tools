"""CLI Interface for getting generated files."""

import argparse
from collections.abc import Sequence
from pathlib import Path
from textwrap import indent

from castep_outputs.tools.get_generated_files import get_generated_files


def get_parser():
    """Get the argument parser for this script."""
    arg_parser = argparse.ArgumentParser(
        prog="castep_files",
        description=("Attempts to work out what files will be produced "
                     "from given seeds."),
    )

    arg_parser.add_argument(
        "seedname", nargs=argparse.REMAINDER, type=Path, help="Seed name for data.",
    )

    return arg_parser


def cli(args: Sequence[str] | None = None):
    """Run from CLI."""
    args = get_parser().parse_args(args)

    for seed in args.seedname:
        print(seed.stem)
        out = "\n".join(map(str, get_generated_files(seed)))
        print(indent(out, "- "))
