"""
Convert CASTEP .md file to potfit format.

Multiple files may be provided and they may be zipped (.gz, .zip).

Notes
-----
Based on original version (castep2force.py) by Corwin Kuiper 2020
"""

from __future__ import annotations

import argparse
import itertools
import sys
import tarfile
import tempfile
import zipfile
from collections import Counter
from functools import singledispatch
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, SupportsIndex, TextIO

from castep_outputs.tools.md_geom_parser import MDGeomParser

from castep_outputs_tools.utils.unit_converter import convert_frame

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from castep_outputs.parsers.md_geom_file_parser import MDGeomTimestepInfo


class PotParser(argparse.Action):
    """Parse the potential string into output argument."""

    def __call__(self, _parser, namespace, values, _option_string=None):
        """Parse comma separated list of `key=val` pairs."""
        out = {pair.split("=")[0]: float(pair.split("=")[1]) for pair in values.split(",")}
        setattr(namespace, self.dest, out)


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse incoming CLI arguments."""
    arg_parser = argparse.ArgumentParser(
        description=(
            "Converts a castep molecular dynamics output file "
            "(or set of files) to a potfit force configuration file"
        ),
        epilog="Example usage: ./castep2force -p Ar=0.01 -o configuration mdinput.md",
    )

    arg_parser.add_argument(
        "files",
        type=Path,
        nargs="+",
        help=("CASTEP .md files as files also loads '.md' files from directory, tar or zip."),
    )
    arg_parser.add_argument(
        "-p",
        "--potential",
        action=PotParser,
        required=True,
        help=(
            "Chemical potentials for the elements used in electronvolts in the format:\n"
            "Element1=Potential1,Element2=Potential2. For example Ar=0.01,Si=0.01,Ne=0.01"
        ),
    )
    arg_parser.add_argument(
        "-o",
        "--output",
        type=argparse.FileType("w"),
        help="File to output force configuration to, default is to standard output.",
        default=sys.stdout,
    )

    arg_parser.add_argument(
        "-F",
        "--frames",
        type=int,
        action="append",
        help="Frames to extract.",
        default=[0],
    )

    arg_parser.add_argument(
        "-f",
        "--final",
        action="store_true",
        help="Only use the final configuration in each file (overrides --frames).",
    )

    return arg_parser.parse_args(args)


def conf_to_potfit(frame: MDGeomTimestepInfo, potentials: dict[str, float]) -> str:
    """Convert a single MD frame for potfit."""
    # convert from atomic to physics units for potfit
    frame = convert_frame(frame, "POTFIT")
    ions = [key[0] for key in frame["ions"]]
    species = dict(zip(set(ions), itertools.count()))

    if species.keys() - potentials.keys():
        raise KeyError(
            f"Potentials not provided for all species "
            f"(missing: {', '.join(species.keys() - potentials.keys())}).",
        )

    # calculate cohesive energy from the input potential_energy & the chemical potentials
    pot_energy = frame["energy"][0][1]  # in eV after convert_frame call
    n_atoms = Counter(ions)

    coh_energy = pot_energy - sum(potentials[element] * n_atoms[element] for element in species)
    coh_energy /= n_atoms.total()

    out = StringIO()

    def _floatfmt(x: float) -> str:
        return format(x, "23.16E")

    cell = [_floatfmt(elem) for row in frame["lattice_vectors"] for elem in row]

    print(
        f"""\
#N {n_atoms.total()} 1
#C {" ".join(species)}
#X {" ".join(cell[:3])}
#Y {" ".join(cell[3:6])}
#Z {" ".join(cell[6:9])}
#E {_floatfmt(coh_energy)}""",
        file=out,
    )
    if "stress" in frame:
        stress = [_floatfmt(elem) for row in frame["stress"] for elem in row]
        print(f"#S {' '.join(stress[ind] for ind in (0, 4, 8, 1, 5, 2))}", file=out)
    print("#F", file=out)
    for (spec, _), data in frame["ions"].items():
        print(
            f"{species[spec]} "
            f"{' '.join(map(_floatfmt, data['position']))} "
            f"{' '.join(map(_floatfmt, data['force']))}",
            file=out,
        )

    return out.getvalue()


def _get_files(files: list[Path]) -> Generator[Path, None, None]:
    """Normalise files whether from directory, files, zip or tar."""
    for file in files:
        if file.is_dir():
            yield from file.glob("*.md")
        elif file.suffix == ".zip":
            with zipfile.ZipFile(file, "r") as zipf, tempfile.TemporaryDirectory() as tmp:
                tmppath = Path(tmp)
                for member in zipf.namelist():
                    path = zipfile.Path(zipf, member)
                    if path.is_file() and member.endswith(".md"):
                        zipf.extract(member, path=tmppath)
                        yield tmppath / member
                        (tmppath / member).unlink(missing_ok=True)
        elif tarfile.is_tarfile(file):
            with tarfile.open(file, "r") as tarf, tempfile.TemporaryDirectory() as tmp:
                tmppath = Path(tmp)
                for member in tarf:
                    if member.isfile() and member.name.endswith(".md"):
                        tarf.extract(member, path=tmppath)
                        yield tmppath / member.name
                        (tmppath / member.name).unlink(missing_ok=True)
        else:
            yield file


@singledispatch
def main(
    output: TextIO,
    md_files: Sequence[Path],
    potential: dict[str, float],
    frames: Sequence[SupportsIndex],
) -> None:
    """Convert a castep MD output file (or set of files) to a potfit force configuration file.

    Parameters
    ----------
    output : TextIO
        File to write to.
    md_files : Sequence[Path]
        Files to parse.
    potential : dict[str, float]
        Chemical potential dictionary (in eV).
    frames : Sequence[SupportsIndex]
        Frames to extract.
    """
    configurations = map(MDGeomParser, _get_files(md_files))
    all_configurations = (conf[frame] for frame in frames for conf in configurations)

    output.writelines(conf_to_potfit(conf, potential) for conf in all_configurations)


@main.register(Path)
@main.register(str)
def _(
    output: Path,
    md_files: Sequence[Path],
    potential: dict[str, float],
    frames: Sequence[SupportsIndex],
) -> None:
    output = Path(output)
    with output.open("w") as file:
        main(file, md_files, potential, frames)


def cli(args: list[str] | None = None) -> None:
    """Convert a castep MD output file (or set of files) to a potfit force configuration file."""
    args = parse_args(args)

    frames = [-1] if args.final else args.frames

    main(args.output, args.files, args.potential, frames)


if __name__ == "__main__":
    cli()
