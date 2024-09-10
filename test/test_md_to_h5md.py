from pathlib import Path
from unittest import TestCase, main

from castep_outputs_tools.md_to_h5md import main as conv


class test_md_to_h5md(TestCase):
    FILE = Path(__file__).parent / "test.md"

    def test_convert(self):
        conv(self.FILE, "test.out")

if __name__ == "main":
    main()
