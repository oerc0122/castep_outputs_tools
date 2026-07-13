from pathlib import Path

import pytest

h5py = pytest.importorskip("h5py")
from castep_outputs_tools.md.md_to_h5md import main as conv

FILE = Path(__file__).parent / "test.md"

def test_md_to_h5md():
    conv(FILE, "test.out")
