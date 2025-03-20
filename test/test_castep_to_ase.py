from pathlib import Path

import numpy as np
import pytest
from castep_outputs import parse_cell_param_file

from castep_outputs_tools.castep.castep_to_ase import main as castep_to_ase

SELF_DIR = Path(__file__).parent
FILES = {"md": SELF_DIR / "test.md",
         "castep-md": SELF_DIR / "test-md.castep",
         "castep-geom": SELF_DIR / "test-geom.castep",
         "castep-spe": SELF_DIR / "test-spe.castep"}

@pytest.mark.parametrize("source,typ,scaled,expected", [
    ("md", "md", False, SELF_DIR / "md.cell"),
    ("castep-md", "castep", True, SELF_DIR / "castep-md.cell"),
    ("castep-geom", "castep", True, SELF_DIR / "castep-geom.cell"),
    ("castep-spe", "castep", True, SELF_DIR / "castep-spe.cell"),
])
def test_castep_to_ase(source, typ, scaled, expected):
    out = castep_to_ase(FILES[source], typ)
    expected = parse_cell_param_file(expected)[-1]

    cell = np.array(expected["lattice_cart"]["data"])

    if scaled:
        pos = np.array([val["pos"] for val in expected["positions_frac"].values()])
        # Issue with loading wrong source.
        assert np.allclose(out.get_scaled_positions(wrap=False), pos, atol=1e-2)
    else:
        pos = np.array([val["pos"] for val in expected["positions_abs"].values()])
        assert np.allclose(out.get_positions(), pos)

    assert np.allclose(out.cell, cell)
