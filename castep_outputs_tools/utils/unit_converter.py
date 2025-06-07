"""Units manager."""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

import numpy as np
from castep_outputs.parsers.md_geom_file_parser import MDGeomTimestepInfo
from castep_outputs.utilities.constants import TAG_ALIASES
from castep_outputs.utilities.utility import add_aliases

DIMENSIONS = Literal[
    "length",
    "force",
    "velocity",
    "stress",
    "temperature",
    "energy",
    "time",
]
UnitSchemes = Literal["ATOMIC", "CASTEP", "MDANALYSIS", "ELECTRONIC"]


@dataclass(frozen=True)
class Unit:
    """Basic unit holder."""

    name: str
    fac: float


@dataclass(frozen=True)
class UnitScheme:
    """Unit scheme holder."""

    length: Unit
    force: Unit
    velocity: Unit
    stress: Unit
    temperature: Unit
    energy: Unit
    time: Unit

    def get_name(self, key: DIMENSIONS) -> str:
        """Get name of unit for given dimension.

        Parameters
        ----------
        key : DIMENSIONS
            Dimension to get name of.

        Returns
        -------
        str
            Unit name.
        """
        return getattr(self, key).name

    def get_fac(self, key: DIMENSIONS) -> float:
        """Get atomic conversion factor of unit for given dimension.

        Parameters
        ----------
        key : DIMENSIONS
            Dimension to get factor of.

        Returns
        -------
        float
            Atomic conversion factor.
        """
        return getattr(self, key).fac

    def convert_to(
        self,
        value: float,
        key: DIMENSIONS,
        *,
        in_scheme: UnitSchemes = "ATOMIC",
        in_unit: str | None = None,
    ) -> float:
        """Convert a value in the given unit to the current scheme.

        Parameters
        ----------
        value : float
            Value to convert.
        key : DIMENSIONS
            Dimension on value.
        in_scheme : UnitSchemes
            Scheme units in.
        in_unit : str
            Unit value currently in (assumed atomic).

        Returns
        -------
        float
            Converted value.

        Examples
        --------
        >>> UNITS["CASTEP"].convert_to(1., "length")
        1.8897268777743552
        """
        if in_unit is None:
            in_unit = UNITS[in_scheme].get_name(key)

        return convert_value(value, in_unit, self.get_name(key))

    def convert_from(
        self,
        value: float,
        key: DIMENSIONS,
        *,
        out_scheme: UnitSchemes = "ATOMIC",
        out_unit: str | None = None,
    ) -> float:
        """Convert a value in the current scheme to the given unit.

        Parameters
        ----------
        value : float
            Value to convert.
        key : DIMENSIONS
            Dimension on value.
        out_unit : str
            Unit to convert value to.

        Returns
        -------
        float
            Converted value.

        Examples
        --------
        >>> UNITS["CASTEP"].convert_from(1., "length")
        0.529177
        >>> UNITS["CASTEP"].convert_from(1., "length", out_unit="m")
        1e-10
        """
        if out_unit is None:
            out_unit = UNITS[out_scheme].get_name(key)

        return convert_value(value, self.get_name(key), out_unit)


_units_from_atomic = {
    key: Unit(key, val)
    for key, val in {
        "Angstrom fs-1": 0.002187690392268886,
        "Angstrom ps-1": 2.187690392268886,
        "Angstrom": 0.529177,
        "m_e": 1.0,
        "GPa": 2942.0427769057487,
        "Ha a0-1": 1.0,
        "Ha a0-3": 1.0,
        "Ha kB-1": 1.0,
        "Ha": 1.0,
        "K": 31577.50248,
        "a0 aut-1": 1.0,
        "a0": 1.0,
        "aut": 1.0,
        "eV Angstrom-1": 51.421,
        "eV Angstrom-3": 183.6278707918808,
        "eV": 27.211386245988,
        "fs": 241.8884326,
        "kJ mol-1 Angstrom-1": 0.5329426703,
        "kJ mol-1 Angstrom-3": 1.9031743412482902,
        "kJ mol-1": 0.2820269704692934,
        "ps": 241888.4326,
        "m": 5.29177e9,
        "kg": 1.0977691e30,
        "s": 241.8884326 * 1e15,
        "J": 2.2937123e17,
        "N": 12137802.6528,
        "m s-1": 4.57102891e-7,
        "Pa": 2942.0427769057487 * 1e-9,
    }.items()
}

UNITS = {
    "ATOMIC": UnitScheme(
        length=_units_from_atomic["a0"],
        force=_units_from_atomic["Ha a0-1"],
        velocity=_units_from_atomic["a0 aut-1"],
        stress=_units_from_atomic["Ha a0-3"],
        temperature=_units_from_atomic["Ha kB-1"],
        energy=_units_from_atomic["Ha"],
        time=_units_from_atomic["aut"],
    ),
    "CASTEP": UnitScheme(
        length=_units_from_atomic["Angstrom"],
        force=_units_from_atomic["eV Angstrom-1"],
        velocity=_units_from_atomic["Angstrom ps-1"],
        stress=_units_from_atomic["GPa"],
        temperature=_units_from_atomic["K"],
        energy=_units_from_atomic["eV"],
        time=_units_from_atomic["ps"],
    ),
    "ELECTRONIC": UnitScheme(
        length=_units_from_atomic["Angstrom"],
        force=_units_from_atomic["eV Angstrom-1"],
        velocity=_units_from_atomic["Angstrom fs-1"],
        stress=_units_from_atomic["eV Angstrom-3"],
        temperature=_units_from_atomic["K"],
        energy=_units_from_atomic["eV"],
        time=_units_from_atomic["fs"],
    ),
    "MDANALYSIS": UnitScheme(
        length=_units_from_atomic["Angstrom"],
        force=_units_from_atomic["kJ mol-1 Angstrom-1"],
        velocity=_units_from_atomic["Angstrom ps-1"],
        stress=_units_from_atomic["kJ mol-1 Angstrom-3"],
        temperature=_units_from_atomic["K"],
        energy=_units_from_atomic["kJ mol-1"],
        time=_units_from_atomic["ps"],
    ),
    "SI": UnitScheme(
        length=_units_from_atomic["m"],
        force=_units_from_atomic["N"],
        velocity=_units_from_atomic["m s-1"],
        stress=_units_from_atomic["Pa"],
        temperature=_units_from_atomic["K"],
        energy=_units_from_atomic["J"],
        time=_units_from_atomic["s"],
    ),
}


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
        yield UNITS[UNIT_SCHEME]
    finally:
        if units is not None:
            UNIT_SCHEME = units_bak


def get_conv_fac(key: str) -> float:
    """Get the conversion factor for the given unit."""
    return _units_from_atomic[key].fac


def get_unit_fac(key: DIMENSIONS) -> float:
    """Get the factor of the given unit, for the current unit scheme."""
    return UNITS[UNIT_SCHEME].get_fac(key)


def get_unit_name(key: DIMENSIONS) -> str:
    """Get the name of the given unit, for the current unit scheme.

    Parameters
    ----------
    key : str
        Dimension

    Returns
    -------
    str
        Name of unit in current scheme.

    Examples
    --------
    >>> with set_units("ATOMIC"):
    ...     get_unit_name("length")
    'a0'
    """
    return UNITS[UNIT_SCHEME].get_name(key)


def convert_value(value: float, unit_from: str, unit_to: str) -> float:
    """Convert a value between unit sets.

    Parameters
    ----------
    value : float
        Value to convert.

    Examples
    --------
    >>> convert_value(1., "Angstrom", "m")
    1e-10
    >>> convert_value(1., "s", "ps")
    1000000000000.0
    """
    return value * get_conv_fac(unit_from) / get_conv_fac(unit_to)


def convert_frame(frame: MDGeomTimestepInfo, units: UnitSchemes = None):
    """Convert all the units of an MD frame."""
    with set_units(units) as scheme:
        data = {
            key: scheme.convert_to(np.array(val), MD_PROP_UNITS[key])
            for key, val in frame.items()
            if key == "time" or key in TAG_ALIASES
        }
        data["ions"] = {
            ion: {
                key: scheme.convert_to(np.array(val), MD_PROP_UNITS[key])
                for key, val in data.items()
                if key in TAG_ALIASES
            }
            for ion, data in frame["ions"].items()
        }

    add_aliases(data, TAG_ALIASES)
    for ion in data["ions"].values():
        add_aliases(ion, TAG_ALIASES)

    return data
