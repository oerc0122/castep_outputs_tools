"""Lazy MD/Geom parser object."""
from __future__ import annotations

from collections.abc import Generator, Sequence
from functools import singledispatchmethod
from pathlib import Path

from castep_outputs.parsers.md_geom_file_parser import (
    MDGeomTimestepInfo,
    parse_md_geom_frame,
)
from castep_outputs.utilities.filewrapper import Block


class MDGeomParser:
    """Lazy MD/Geom parser."""

    def __init__(self, md_geom_file: Path | str):
        self.file = Path(md_geom_file)

        if not self.file.exists() or not self.file.is_file():
            raise FileNotFoundError(f"Cannot open file ({md_geom_file.absolute()}).")

        self._handle = self.file.open()
        while "END header" not in self._handle.readline():
            pass
        self._handle.readline()
        self._start = self._handle.tell()

        self._frame_len = 0
        while self._handle.readline().strip():
            self._frame_len += 1
        self._byte_len = self._handle.tell() - self._start
        stat = self.file.stat()
        self._len = (stat.st_size - self._start) // self._byte_len

    def _get_index(self, frame: int) -> int:
        """Get index of given frame in bytes."""
        return self._start + (self._byte_len * frame)

    def _go_to_frame(self, frame: int) -> None:
        """Set file pointer to given index."""
        ind = self._get_index(frame)
        self._handle.seek(ind)

    def get_frame(self, frame: int) -> MDGeomTimestepInfo:
        """Get particular frame of md/geom."""
        if -len(self) > frame > len(self):
            print("Cannot get {frame}th frame. File only has {len(self)} frames.")

        if frame < 0:
            frame = len(self) - frame

        self._go_to_frame(frame)
        block = Block.get_lines(self._handle, self._frame_len)

        return parse_md_geom_frame(block)

    def __len__(self) -> int:
        """Get number of frames in file."""
        return self._len

    def __iter__(self) -> Generator[MDGeomTimestepInfo, int, None]:
        """Iterate over all frames in system. Jumps permitted."""
        self._handle.seek(self._start)
        while block := Block.get_lines(self._handle, self._frame_len, eof_possible=True):
            jump = yield parse_md_geom_frame(block)
            if jump is not None:
                self._go_to_frame(jump)

    @singledispatchmethod
    def __getitem__(self, frame) -> list[MDGeomTimestepInfo] | MDGeomTimestepInfo:
        """Get particular frame of md/geom."""
        raise NotImplementedError(f"Can't get {frame}th frame.")

    @__getitem__.register(int)
    def _(self, frame) -> MDGeomTimestepInfo:
        """Get particular frame of md/geom."""
        return self.get_frame(frame)

    @__getitem__.register(Sequence)
    def _(self, frames) -> list[MDGeomTimestepInfo]:
        """Get particular frame of md/geom."""
        return [self.get_frame(frame) for frame in frames]

    @__getitem__.register(slice)
    def _(self, frames) -> list[MDGeomTimestepInfo]:
        """Get particular frame of md/geom."""
        range_ = frames.start or 0, frames.stop or len(self), frames.step or 1

        return self[range(*range_)]

    def __del__(self):
        """Close file before deletion."""
        self._handle.close()
