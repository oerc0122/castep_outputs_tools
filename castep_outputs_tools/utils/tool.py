"""Tool registry."""

from argparse import ArgumentParser, Namespace
from argparse import _SubParsersAction as SubParser
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True, kw_only=True)
class Tool:
    """Tool information.

    A tool is defined by being of the :class:`Tool` class and being named `_tool_`.

    :attr:`run` will receive the namespace returned from :attr:`arg_parser`.
    """

    run: Callable[[Namespace], Any]
    arg_parser: Callable[[], ArgumentParser]
    aliases: Sequence[str] = ()
