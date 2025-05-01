from pathlib import Path
from unittest import TestCase, main

from castep_outputs_tools.tools.md.md_geom_parser import MDGeomParser

class test_md_parser(TestCase):
    FILE = Path(__file__).parent / "test.md"

    def test_read(self):
        """Check the parser is reading properly."""
        parser = MDGeomParser(self.FILE)

        # Check frames
        assert len(parser) == 3

        for frame in parser:
            # Check all expected keys present
            assert not ({"ions", "time", "E", "T", "h",
                         "energy", "temperature", "lattice_vectors"} - frame.keys())

            # Check latt vecs
            lattice_vectors = frame["lattice_vectors"]
            assert len(lattice_vectors) == 3 and all(len(vec) == 3 for vec in lattice_vectors)

            # Check ions
            ions = frame["ions"]
            assert len(ions) == 8
            for ion in ions.values():
                assert not ({"R", "V", "F", "position", "velocity", "force"} - ion.keys())

        # Test getitem
        frames = list(parser)
        assert parser[1] == frames[1]

    def test_next_frame(self):
        """Check the next frame counter is working."""
        parser = MDGeomParser(self.FILE)
        it = iter(parser)

        # No frames read
        assert parser.next_frame == 0

        next(it)
        assert parser.next_frame == 1
        next(it)
        assert parser.next_frame == 2

        # Exhausted
        next(it)
        assert parser.next_frame is None

        # Check setting with send (iter resets parser to start)
        it = iter(parser)
        next(it)
        next(it)
        it.send(0)
        assert parser.next_frame == 1

        # Check with getitem
        parser[2]
        assert parser.next_frame is None
        parser[0]
        assert parser.next_frame == 1

if __name__ == "main":
    main()
