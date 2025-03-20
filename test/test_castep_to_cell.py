from pathlib import Path

import pytest
from castep_outputs.parsers.cell_param_file_parser import parse_cell_param_file as parse

from castep_outputs_tools.castep.castep_to_cell import main as conv

SELF_DIR = Path(__file__).parent
FILES = {"md": SELF_DIR / "test.md",
         "castep-md": SELF_DIR / "test-md.castep",
         "castep-geom": SELF_DIR / "test-geom.castep",
         "castep-spe": SELF_DIR / "test-spe.castep"}


@pytest.mark.parametrize("source,typ,expected", [
    ("md", "md", SELF_DIR / "md.cell"),
    ("castep-md", "castep", SELF_DIR / "castep-md.cell"),
    ("castep-geom", "castep", SELF_DIR / "castep-geom.cell"),
    ("castep-spe", "castep", SELF_DIR / "castep-spe.cell"),
])
def test_castep_to_cell(tmp_path, source, typ, expected):
    out = tmp_path / "test.cell"
    conv(FILES[source], out_file=out, source_format=typ)

    assert parse(out) == parse(expected)
