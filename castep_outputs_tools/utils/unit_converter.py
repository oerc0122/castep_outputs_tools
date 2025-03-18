"""Units manager."""
from contextlib import contextmanager
from typing import Literal, NamedTuple

import numpy as np
from castep_outputs.parsers.md_geom_file_parser import MDGeomTimestepInfo
from castep_outputs.utilities.constants import TAG_ALIASES
from castep_outputs.utilities.utility import add_aliases


class Unit(NamedTuple):
    """Basic unit holder."""

    name: str
    fac: float

_units_from_atomic = {key: Unit(key, val)
                      for key, val in {"Angstrom fs-1": 0.002187690392268886,
                                       "Angstrom ps-1": 2.187690392268886,
                                       "Angstrom": 0.529177,
                                       "GPa": 2942.0427769057487,
                                       "Ha a0-1": 1.,
                                       "Ha a0-3": 1.,
                                       "Ha kB-1": 1.,
                                       "Ha": 1.,
                                       "K": 31577.50248,
                                       "a0 aut-1": 1.,
                                       "a0": 1.,
                                       "aut": 1.,
                                       "eV Angstrom-1": 51.421,
                                       "eV Angstrom-3": 183.6278707918808,
                                       "eV": 27.211386245988,
                                       "fs": 241.8884326,
                                       "kJ mol-1 Angstrom-1": 0.5329426703,
                                       "kJ mol-1 Angstrom-3": 1.9031743412482902,
                                       "kJ mol-1": 0.2820269704692934,
                                       "ps": 241888.4326,
                                       }.items()}


UNITS = {
    "ATOMIC": {
        "length": _units_from_atomic["a0"],
        "force": _units_from_atomic["Ha a0-1"],
        "velocity": _units_from_atomic["a0 aut-1"],
        "stress": _units_from_atomic["Ha a0-3"],
        "temperature": _units_from_atomic["Ha kB-1"],
        "energy": _units_from_atomic["Ha"],
        "time": _units_from_atomic["aut"],
    },
    "CASTEP": {
        "length": _units_from_atomic["Angstrom"],
        "force": _units_from_atomic["eV Angstrom-1"],
        "velocity": _units_from_atomic["Angstrom ps-1"],
        "stress": _units_from_atomic["GPa"],
        "temperature": _units_from_atomic["K"],
        "energy": _units_from_atomic["eV"],
        "time": _units_from_atomic["ps"],
    },
    "ELECTRONIC": {
        "length": _units_from_atomic["Angstrom"],
        "force": _units_from_atomic["eV Angstrom-1"],
        "velocity": _units_from_atomic["Angstrom fs-1"],
        "stress": _units_from_atomic["eV Angstrom-3"],
        "temperature": _units_from_atomic["K"],
        "energy": _units_from_atomic["eV"],
        "time": _units_from_atomic["fs"],
    },
    "MDANALYSIS": {
        "length": _units_from_atomic["Angstrom"],
        "force": _units_from_atomic["kJ mol-1 Angstrom-1"],
        "velocity": _units_from_atomic["Angstrom ps-1"],
        "stress": _units_from_atomic["kJ mol-1 Angstrom-3"],
        "temperature": _units_from_atomic["K"],
        "energy": _units_from_atomic["kJ mol-1"],
        "time": _units_from_atomic["ps"],
    },
}

UnitSchemes = Literal["ATOMIC", "CASTEP", "MDANALYSIS", "ELECTRONIC"]

MD_PROP_UNITS = {
    "time": "time",
    "R": "length",
    "h": "length",
    "V": "velocity",
    "hv": "velocity",
    "F": "force",
    "P": "stress",
    "S": "stress",
    "T": "temperature",
    "hamiltonian_energy": "energy",
    "potential_energy": "energy",
    "kinetic_energy": "energy",
    "E": "energy",
}
add_aliases(MD_PROP_UNITS, TAG_ALIASES)

# Singleton config
UNIT_SCHEME: UnitSchemes = "MDANALYSIS"

@contextmanager
def set_units(units: UnitSchemes = None):
    """Stable context manager for handling temporary unit setting."""
    global UNIT_SCHEME  # noqa: PLW0603
    units_bak = UNIT_SCHEME
    try:
        if units is not None:
            UNIT_SCHEME = units
        yield
    finally:
        if units is not None:
            UNIT_SCHEME = units_bak


def get_fac(key: str):
    """Get the factor of the given unit, for the current unit scheme."""
    return UNITS[UNIT_SCHEME][key].fac

def get_name(key: str):
    """Get the name of the given unit, for the current unit scheme."""
    return UNITS[UNIT_SCHEME][key].name

def convert_frame(frame: MDGeomTimestepInfo, units: UnitSchemes = None):
    """Convert all the units of an MD frame."""
    with set_units(units):
        data = {key: np.array(val) * get_fac(MD_PROP_UNITS[key])
                for key, val in frame.items()
                if key in TAG_ALIASES}
        data["ions"] = {ion: {key: np.array(val) * get_fac(MD_PROP_UNITS[key])
                              for key, val in data.items()
                              if key in TAG_ALIASES}
                        for ion, data in frame["ions"].items()}

    add_aliases(data, TAG_ALIASES)
    for ion in data["ions"].values():
        add_aliases(ion, TAG_ALIASES)

    return data
