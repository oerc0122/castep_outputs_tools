"""
Convert CASTEP .md/geom format to h5md output.

References
----------
.. [1] https://www.nongnu.org/h5md/
"""
from __future__ import annotations

import argparse
from functools import singledispatch
from pathlib import Path
from typing import TextIO

import h5py
from castep_outputs.parsers import parse_md_geom_file as parser

from castep_outputs_tools import __version__


def _convert_frame(out_file: h5py.File, frame: dict, frame_id: int):
    """
    Convert a single frame and fill the data blocks.

    Parameters
    ----------
    frame : dict
        Incoming read frame.
    frame_id : int
        Index of current frame.
    out_file : h5py.File
        File to write.
    """
    part = out_file["particles"]
    obs = out_file["observables"]

    part["box/edges/time"][frame_id] = frame["time"]
    part["box/edges/value"][frame_id] = frame["h"]

    atom_props = [val for key, val in frame.items() if isinstance(key, tuple)]

    for i, elem in enumerate(atom_props):
        part["position/value"][frame_id, i] = elem["R"]
        part["velocity/value"][frame_id, i] = elem["V"]
        part["force/value"][frame_id, i] = elem["F"]

    for i, prop in enumerate(("hamiltonian_energy", "potential_energy", "kinetic_energy")):
        obs[f"{prop}/value"][frame_id] = frame["E"][0][i]

    obs["temperature/value"][frame_id] = frame["T"]
    obs["pressure/value"][frame_id] = frame["P"]
    obs["stress/value"][frame_id] = frame["S"]
    obs["lattice_velocity/value"][frame_id] = frame["hv"]

def _create_header_info(out_file: h5py.File, **metadata):
    """
    Create metadata block from provided information.

    Parameters
    ----------
    out_file : h5py.File
        File to write.
    **metadata : dict
        Metadata ("name" and "email")
    """
    grp = out_file.create_group("h5md")
    grp.attrs["version"] = (1, 1)
    auth = grp.create_group("author")
    auth.attrs["name"] = metadata.get("author", "Unknown")
    auth.attrs["email"] = metadata.get("email", "Unknown")
    crea = grp.create_group("creator")
    crea.attrs["name"] = "castep outputs"
    crea.attrs["version"] = __version__

def _create_groups(out_file: h5py.File, n_steps: int, species: set[str], atoms: list[str]):
    """
    Create empty groups for filling with data.

    Parameters
    ----------
    out_file : h5py.File
        File to write.
    n_steps : int
        Number of steps in md file.
    species : set[str]
        Species in file.
    atoms : list[str]
        Complete list of atoms in file.
    """
    n_atoms = len(atoms)
    n_species = len(species)

    part = out_file.create_group("particles")
    obs = out_file.create_group("observables")

    atom_dict = dict(zip(species, range(n_species)))
    spec_enum = h5py.enum_dtype(atom_dict)
    atom_ind = [atom_dict[atm] for atm in atoms]

    part.create_dataset("species", (n_atoms,), dtype=spec_enum, data=atom_ind)

    box = part.create_group("box")
    box.attrs["dimension"] = 3
    box.attrs["boundary"] = "periodic"
    edge = box.create_group("edges")
    edge["step"] = list(range(1, n_steps+1))
    edge.create_dataset("time", (n_steps,), dtype=float)
    edge.create_dataset("value", (n_steps, 3, 3), dtype=float)

    for prop in ("position", "velocity", "force"):
        grp = part.create_group(prop)
        grp["step"] = edge["step"]
        grp["time"] = edge["time"]
        grp.create_dataset("value", (n_steps, n_atoms, 3), dtype=float)

    for prop in ("hamiltonian_energy", "potential_energy",
                 "kinetic_energy", "pressure", "temperature"):
        grp = obs.create_group(prop)
        grp["step"] = edge["step"]
        grp["time"] = edge["time"]
        grp.create_dataset("value", (n_steps,), dtype=float)

    for prop in ("lattice_velocity", "stress"):
        grp = obs.create_group(prop)
        grp["step"] = edge["step"]
        grp["time"] = edge["time"]
        grp.create_dataset("value", (n_steps, 3, 3), dtype=float)


def md_to_h5md(md_geom_file: TextIO, out_path: Path | str, **metadata) -> None:
    """
    Convert an MD file to h5md format [1]_.

    Parameters
    ----------
    md_geom_file : TextIO
        File to parse.
    out_path : Path or str
        File to write.
    **metadata : dict
        Username and email of author.
    """
    parsed = parser(md_geom_file)
    atoms = [x[0] for x in parsed[0] if isinstance(x, tuple)]
    species = set(atoms)
    n_steps = len(parsed)

    with h5py.File(out_path, "w") as out_file:

        _create_header_info(out_file, **metadata)
        _create_groups(out_file, n_steps, species, atoms)

        for i, frame in enumerate(parsed):
            _convert_frame(out_file, frame, i)

@singledispatch
def main(source, output, **metadata):
    """
    Convert an MD file to h5md format [1]_.

    Parameters
    ----------
    source : str or Path or TextIO
        File to parse.
    output : str or Path
        File to write.

    Raises
    ------
    NotImplementedError
        Invalid types passed.
    """
    raise NotImplementedError(f"Unable to convert {type(source).__name__} to h5md")

@main.register(str)
def _(source, output: Path | str, **metadata):
    main(Path(source), output, **metadata)

@main.register(Path)
def _(source, output: Path | str, **metadata):
    with source.open("r") as in_file:
        md_to_h5md(in_file, output, **metadata)

@main.register(TextIO)
def _(source, output: Path | str, **metadata):
    md_to_h5md(source, output, **metadata)


def cli():
    """
    Run md_to_h5md through command line.

    Examples
    --------
    .. code-block:: sh

       md_to_h5md -o my_file.h5md my_input.md
       md_to_h5md --author "Jacob Wilkins" --email "e.mail@email.org" -o my_file.h5md my_input.md
    """
    arg_parser = argparse.ArgumentParser(
        prog="md_to_h5md",
        description="Convert a castep .md file to .h5md format.",
        epilog="See https://www.nongnu.org/h5md/ for more info on h5md.",
    )
    arg_parser.add_argument("source", type=Path, help=".md file to parse")
    arg_parser.add_argument("-o", "--output", help="File to write output.", required=True)
    arg_parser.add_argument("-a", "--author", type=str,
                            help="Author for metadata.", default="Unknown")
    arg_parser.add_argument("-e", "--email", type=str,
                            help="Email for metadata.", default="Unknown")
    arg_parser.add_argument("-V", "--version", action="version", version=f"%(prog)s v{__version__}")
    args = arg_parser.parse_args()

    main(args.source, args.output, author=args.author, email=args.email)


if __name__ == "__main__":
    cli()
