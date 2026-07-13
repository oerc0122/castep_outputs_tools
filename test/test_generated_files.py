from pathlib import Path
from castep_outputs_tools.tools.inputs.get_generated_files import cli

import pytest

INP_SEED = Path(__file__).parent / "test"


def test_get_generated_files(capsys):
    cli([str(INP_SEED.absolute())])

    cap = capsys.readouterr()
    assert cap.out == """\
test
- test.bands
- test.castep
- test.castep_bin
- test.check
- test.cst_esp
"""
