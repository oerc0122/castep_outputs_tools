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
from typing import Literal, TextIO

import h5py
import pint
from castep_outputs.parsers import parse_md_geom_file as parser

from castep_outputs_tools import __version__

UREG = pint.UnitRegistry()

Dimensions = Literal["length", "velocity", "force",
                     "energy", "pressure", "temperature", "time"]
UnitSystems = Literal["MDANALYSIS", "CASTEP", "ELECTRONIC"]
UNITS = {
    "MDANALYSIS":
    {
        "length": "angstrom",
        "velocity": "angstrom/ps",
        # Newtons because MDAnalysis wants kJ/(mol*Angstrom)
        # where according to pint "mol" has dimensions
        "force": "N",
        "energy": "eV",
        "pressure": "eV / angstrom^3",
        "temperature": "K",
        "time": "ps",
    },
    "CASTEP":
    {
        "length": "bohr",
        "velocity": "bohr / atomic_unit_of_time",
        "force": "hartree / bohr",
        "energy": "hartree",
        "pressure": "hartree / bohr^3",
        "temperature": "atomic_unit_of_temperature",
        "time": "atomic_unit_of_time",
    },
    "ELECTRONIC":
    {
        "length": "angstrom",
        "velocity": "angstrom / ps",
        "force": "eV / angstrom",
        "energy": "eV",
        "pressure": "eV / angstrom^3",
        "temperature": "K",
        "time": "ps",
    },
}

def _convert_unit(
        val: float,
        unit: Dimensions,
        *,
        frm: UnitSystems = "CASTEP",
        to: UnitSystems = "MDANALYSIS",
) -> float:
    """
    Convert between unit sets as defined in units for in/output.

    Parameters
    ----------
    val : float
        Value to convert.
    unit : Dimensions
        Dimension to convert.
    frm : UnitSystems
        Unit set to pull units from.
    to : UnitSystems
        Unit set to convert to.

    Returns
    -------
    Magnitude of unit in `to` units.
    """
    return (val * getattr(UREG, UNITS[frm][unit])).to(getattr(UREG, UNITS[to][unit])).magnitude


def _convert_frame(
        out_file: h5py.File,
        frame: dict,
        frame_id: int,
        *,
        units: UnitSystems,
):
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

    part["box/edges/time"][frame_id] = _convert_unit(frame["time"], "time", to=units)
    part["box/edges/value"][frame_id] = _convert_unit(frame["h"], "length", to=units)

    for i, elem in enumerate(frame["ions"].values()):
        part["position/value"][frame_id, i] = _convert_unit(elem["R"], "length", to=units)
        part["velocity/value"][frame_id, i] = _convert_unit(elem["V"], "velocity", to=units)
        part["force/value"][frame_id, i] = _convert_unit(elem["F"], "force", to=units)

    for i, prop in enumerate(("hamiltonian_energy", "potential_energy", "kinetic_energy")):
        obs[f"{prop}/value"][frame_id] = _convert_unit(frame["E"][0][i], "energy", to=units)

    obs["temperature/value"][frame_id] = _convert_unit(frame["T"], "temperature", to=units)
    obs["pressure/value"][frame_id] = _convert_unit(frame["P"], "pressure", to=units)
    obs["stress/value"][frame_id] = _convert_unit(frame["S"], "pressure", to=units)
    obs["lattice_velocity/value"][frame_id] = _convert_unit(frame["hv"], "velocity", to=units)

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

def _create_groups(
        out_file: h5py.File,
        n_steps: int,
        species: set[str],
        atoms: list[str],
        *,
        units: UnitSystems,
):
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

    unit_scheme = UNITS[units]

    part.create_dataset("species", (n_atoms,), dtype=spec_enum, data=atom_ind)

    box = part.create_group("box")
    box.attrs["dimension"] = 3
    box.attrs["boundary"] = "periodic"
    edge = box.create_group("edges")
    edge["step"] = list(range(1, n_steps+1))
    edge.create_dataset("time", (n_steps,), dtype=float)
    edge["time"].attrs["unit"] = unit_scheme["time"]
    edge.create_dataset("value", (n_steps, 3, 3), dtype=float)
    edge["value"].attrs["unit"] = unit_scheme["length"]

    for prop, unit in zip(("position", "velocity", "force"),
                          ("length", "velocity", "force")):
        grp = part.create_group(prop)
        grp["step"] = edge["step"]
        grp["time"] = edge["time"]
        grp.create_dataset("value", (n_steps, n_atoms, 3), dtype=float)
        grp["value"].attrs["unit"] = unit_scheme[unit]

    for prop, unit in zip(("hamiltonian_energy", "potential_energy",
                           "kinetic_energy", "pressure", "temperature"),
                          ("energy", "energy", "energy", "pressure", "temperature")):
        grp = obs.create_group(prop)
        grp["step"] = edge["step"]
        grp["time"] = edge["time"]
        grp.create_dataset("value", (n_steps,), dtype=float)
        grp["value"].attrs["unit"] = unit_scheme[unit]

    for prop, unit in zip(("lattice_velocity", "stress"),
                          ("velocity", "pressure")):
        grp = obs.create_group(prop)
        grp["step"] = edge["step"]
        grp["time"] = edge["time"]
        grp.create_dataset("value", (n_steps, 3, 3), dtype=float)
        grp["value"].attrs["unit"] = unit_scheme[unit]


def md_to_h5md(
        md_geom_file: TextIO,
        out_path: Path | str,
        *,
        units: UnitSystems = "MDANALYSIS",
        **metadata,
) -> None:
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
    print(f"{parsed=}")
    atoms = [x[0] for x in parsed[0]["ions"]]
    species = set(atoms)
    n_steps = len(parsed)

    with h5py.File(out_path, "w") as out_file:

        _create_header_info(out_file, **metadata)
        _create_groups(out_file, n_steps, species, atoms, units=units)

        for i, frame in enumerate(parsed):
            _convert_frame(out_file, frame, i, units=units)

@singledispatch
def main(source, output, *, units: UnitSystems = "MDANALYSIS", **metadata):
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
def _(source, output: Path | str, *, units: UnitSystems = "MDANALYSIS", **metadata):
    main(Path(source), output, units=units, **metadata)

@main.register(Path)
def _(source, output: Path | str, *, units: UnitSystems = "MDANALYSIS", **metadata):
    with source.open("r") as in_file:
        md_to_h5md(in_file, output, units=units, **metadata)

@main.register(TextIO)
def _(source, output: Path | str, *, units: UnitSystems = "MDANALYSIS", **metadata):
    md_to_h5md(source, output, units=units, **metadata)


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
    arg_parser.add_argument("-u", "--units", choices=UNITS.keys(), default="MDANALYSIS")
    arg_parser.add_argument("-V", "--version", action="version", version=f"%(prog)s v{__version__}")
    args = arg_parser.parse_args()

    main(args.source, args.output, author=args.author, email=args.email, units=args.units.upper())


if __name__ == "__main__":
    cli()
