"""
Convert CASTEP .md/geom format to h5md output.

References
----------
.. [1] https://www.nongnu.org/h5md/
"""

from __future__ import annotations

import argparse
from argparse import ArgumentParser
from argparse import _SubParsersAction as SubParser
from functools import singledispatch
from pathlib import Path

import h5py
import numpy as np
from castep_outputs.parsers.md_geom_file_parser import MDGeomTimestepInfo

from castep_outputs_tools import __version__
from castep_outputs_tools.tools.md.md_geom_parser import MDGeomParser as parser
from castep_outputs_tools.utils.tool import Tool, main_or_sub_parser
from castep_outputs_tools.utils.unit_converter import UNITS, UnitSchemes, get_unit_name, set_units
from castep_outputs_tools.utils.unit_converter import convert_frame as convert_units

try:
    from tqdm import tqdm
except ImportError:

    def tqdm(x, *_args, **_kwargs):
        """Return dummy function for tqdm."""
        yield from x


def _dump_config(out_path: str | Path, frame: MDGeomTimestepInfo):
    """
    Dump configuration as a DLPoly CONFIG format.

    Parameters
    ----------
    out_path: Path
        Path to dump file to.
    frame: MDGeomTimestepInfo
        Frame to dump as config format.

    Notes
    -----
    Used only for passing to MDAnalysis as does not parse CASTEP .cell.
    """
    out_path = Path(out_path)

    with out_path.open("w", encoding="utf-8") as out_file:
        print("Dump from castep", file=out_file)
        print(f"{2:10d}{3:10d}{len(frame['ions']):10d}", file=out_file)

        for vec in frame["lattice_vectors"]:
            print("".join(map("{:20.10f}".format, vec)), file=out_file)

        for key, ion in frame["ions"].items():
            print(f"{key[0]:<8}{key[1]:10d}", file=out_file)
            for vec in ("R", "V", "F"):
                print("".join(map("{:20.10f}".format, ion[vec])), file=out_file)


def _convert_frame(
    out_file: h5py.File,
    frame: MDGeomTimestepInfo,
    frame_id: int,
    units: UnitSchemes = "MDANALYSIS",
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
    units : UnitSchemes
        Units to use.

    Examples
    --------
    .. code-block:: python

        with h5py.open("out.h5"):
            _create_header_info(out_file, **metadata)
            _create_groups(out_file, n_steps, species, atoms, parsed[0])

            for i, frame in enumerate(frames):
                _convert_frame(out_file, frame, i)

    Notes
    -----
    Shouldn't really be used.

    Provided for processing *extremely* large files where binary data
    will not fit in memory and can only process-framewise.
    """
    part = out_file["particles/all"]
    obs = out_file["observables"]

    with set_units(units):
        frame = convert_units(frame, units)

        part["box/edges/time"][frame_id] = frame["time"]
        part["box/edges/value"][frame_id] = frame["h"]

        for i, elem in enumerate(frame["ions"].values()):
            part["position/value"][frame_id, i] = elem["R"]
            part["velocity/value"][frame_id, i] = elem["V"]
            part["force/value"][frame_id, i] = elem["F"]

        for i, prop in enumerate(("hamiltonian_energy", "potential_energy", "kinetic_energy")):
            obs[f"{prop}/value"][frame_id] = frame["E"][0][i]

        obs["temperature/value"][frame_id] = frame["T"]

        for key in ("pressure", "stress", "lattice_velocity"):
            if key in frame:
                obs[f"{key}/value"] = frame[key]


def _fill_groups(
    out_file: h5py.File,
    frames: list[MDGeomTimestepInfo],
    units: UnitSchemes = "MDANALYSIS",
):
    """
    Convert frames and fill the data blocks.

    Parameters
    ----------
    frame : dict
        Incoming read frame.
    frame_id : int
        Index of current frame.
    out_file : h5py.File
        File to write.
    units : UnitSchemes
        Units to use.
    """
    part = out_file["particles/all"]
    obs = out_file["observables"]

    n_steps = len(frames)
    n_atoms = len(frames[0]["ions"])
    part_props, props = _get_props(frames[0], n_steps, n_atoms, units)

    part_props = {key: np.empty(val) for key, (val, _) in part_props.items()}
    props = {key: np.empty(val) for key, (val, _) in props.items()}
    time = np.empty(n_steps)
    edges = np.empty((n_steps, 3, 3))

    with set_units(units):
        for i, frame in tqdm(enumerate(map(convert_units, frames)), total=len(frames)):
            time[i] = frame["time"]
            edges[i, :, :] = frame["h"]

            for j, ion in enumerate(frame["ions"].values()):
                part_props["position"][i, j, :] = ion["R"]
                part_props["velocity"][i, j, :] = ion["V"]
                part_props["force"][i, j, :] = ion["F"]

            for key, val in zip(
                ("hamiltonian_energy", "potential_energy", "kinetic_energy"),
                frame["E"][0],
                strict=True,
            ):
                props[key][i] = val

            props["temperature"][i] = frame["T"][0][0]
            for key in ("pressure", "lattice_velocity", "stress"):
                if key in props:
                    props[key][i, ...] = frame[key]

    part["box/edges/time"][:] = time
    part["box/edges/value"][:] = edges

    for key, val in part_props.items():
        part[f"{key}/value"][:] = val

    for key, val in props.items():
        obs[f"{key}/value"][:] = val


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


def _get_props(
    frame: MDGeomTimestepInfo,
    n_steps: int,
    n_atoms: int,
    units: UnitSchemes = "MDANALYSIS",
):
    """
    Get properties from frame data.

    Parameters
    ----------
    frame : MDGeomTimestepInfo
        Example frame to determine properties present.
    n_steps : int
        Number of steps in MD run.
    n_atoms : int
        Number of ions in MD run.
    units : UnitSchemes
        Units to use.
    """
    with set_units(units):
        part_props = {
            "position": ((n_steps, n_atoms, 3), get_unit_name("length")),
            "velocity": ((n_steps, n_atoms, 3), get_unit_name("velocity")),
            "force": ((n_steps, n_atoms, 3), get_unit_name("force")),
        }

        props = {
            "hamiltonian_energy": ((n_steps,), get_unit_name("energy")),
            "potential_energy": ((n_steps,), get_unit_name("energy")),
            "kinetic_energy": ((n_steps,), get_unit_name("energy")),
            "temperature": ((n_steps,), get_unit_name("temperature")),
        }

        if "pressure" in frame:
            props["pressure"] = ((n_steps,), get_unit_name("stress"))
        if "lattice_velocity" in frame:
            props["lattice_velocity"] = ((n_steps, 3, 3), get_unit_name("velocity"))
        if "stress" in frame:
            props["stress"] = ((n_steps, 3, 3), get_unit_name("stress"))

    return part_props, props


def _create_groups(
    out_file: h5py.File,
    n_steps: int,
    species: set[str],
    atoms: list[str],
    frame: MDGeomTimestepInfo,
    units="MDANALYSIS",
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
    units : UnitSchemes
        Units to use.
    """
    n_atoms = len(atoms)
    n_species = len(species)

    # Units module
    mod = out_file.create_group("modules")
    uni = mod.create_group("units")
    uni.attrs["version"] = (1, 0)

    part = out_file.create_group("particles").create_group("all")
    obs = out_file.create_group("observables")
    obs.attrs["dimension"] = 3

    atom_dict = dict(zip(species, range(n_species), strict=True))
    spec_enum = h5py.enum_dtype(atom_dict)
    atom_ind = [atom_dict[atm] for atm in atoms]

    with set_units(units):
        part.create_dataset("species", (n_atoms,), dtype=spec_enum, data=atom_ind)

        box = part.create_group("box")
        box.attrs["dimension"] = 3
        box.attrs["boundary"] = "periodic"
        edge = box.create_group("edges")
        edge["step"] = list(range(1, n_steps + 1))
        edge.create_dataset("time", (n_steps,), dtype=float)
        edge["time"].attrs["unit"] = get_unit_name("time")
        edge.create_dataset("value", (n_steps, 3, 3), dtype=float)
        edge["value"].attrs["unit"] = get_unit_name("length")

        part_props, props = _get_props(frame, n_steps, n_atoms, units)

        for elem, typ in zip((part_props, props), (part, obs), strict=True):
            for prop, (size, unit) in elem.items():
                grp = typ.create_group(prop)
                grp["step"] = edge["step"]
                grp["time"] = edge["time"]
                grp.create_dataset("value", size, dtype=float)
                grp["value"].attrs["unit"] = unit


def md_to_h5md(
    md_geom_file: Path,
    out_path: Path | str,
    units: str = "MDANALYSIS",
    *,
    dump_config: bool = False,
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
    units : UnitSchemes
        Units to use.
    **metadata : dict
        Username and email of author.
    """
    parsed = parser(md_geom_file)
    atoms = [x[0] for x in parsed[0]["ions"]]
    species = set(atoms)
    n_steps = len(parsed)

    if dump_config:
        _dump_config(out_path.with_suffix(".config"), parsed[0])

    with h5py.File(out_path, "w") as out_file:
        _create_header_info(out_file, **metadata)
        _create_groups(out_file, n_steps, species, atoms, parsed[0], units)
        _fill_groups(out_file, parsed, units)


def get_parser(parser: SubParser | None = None) -> ArgumentParser:
    """Get the argument parser for this script."""
    arg_parser = main_or_sub_parser(
        parser,
        name="md_to_h5md",
        description="Convert a castep .md file to .h5md format.",
        epilog="See https://www.nongnu.org/h5md/ for more info on h5md.",
        aliases=("h5md",),
    )

    arg_parser.add_argument("source", type=Path, help=".md file to parse")
    arg_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="File to write output.",
        required=True,
    )
    arg_parser.add_argument(
        "-a",
        "--author",
        type=str,
        help="Author for metadata.",
        default="Unknown",
    )
    arg_parser.add_argument(
        "-e",
        "--email",
        type=str,
        help="Email for metadata.",
        default="Unknown",
    )
    arg_parser.add_argument(
        "-u",
        "--units",
        choices=UNITS.keys(),
        default="MDANALYSIS",
        help="Select units for output h5md file",
    )
    arg_parser.add_argument(
        "-x",
        "--dump-config",
        action="store_true",
        help="Dump initial configuration (for MDAnalysis). Dumps to output.with_suffix('.config').",
    )
    return arg_parser


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
    md_to_h5md(source, output, **metadata)


@main.register(argparse.Namespace)
def _(args):
    main(
        args.source,
        args.output,
        units=args.units,
        dump_config=args.dump_config,
        author=args.author,
        email=args.email,
    )


def cli():
    """
    Run md_to_h5md through command line.

    Examples
    --------
    .. code-block:: sh

       md_to_h5md -o my_file.h5md my_input.md
       md_to_h5md --author "Jacob Wilkins" --email "e.mail@email.org" -o my_file.h5md my_input.md
    """
    arg_parser = get_parser()
    args = arg_parser.parse_args()
    main(args)


_tool_ = Tool(arg_parser=get_parser, run=main)

if __name__ == "__main__":
    cli()
