"""Tool registry."""

from argparse import ArgumentParser, Namespace
from argparse import _SubParsersAction as SubParser
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class Tool:
    """Tool information.

    A tool is defined by being of the :class:`Tool` class and being named `_tool_`.

    :attr:`run` will receive the namespace returned from :attr:`arg_parser`.
    """

    run: Callable[[Namespace], Any]
    arg_parser: Callable[[SubParser | None], ArgumentParser]


def main_or_sub_parser(parser: SubParser | None = None,
                       *,
                       name: str,
                       description: str,
                       aliases: Sequence[str] = (),
                       **kwargs) -> ArgumentParser:
    """Get a parser from parameters.

    If there is not an existing parser create a new
    one, otherwise adds it to the subparser.

    Parameters
    ----------
    parser : SubParser, optional
        SubParser to add parser to.
    name : str
        Name of the script.
    description : str
        Description of the purpose.
    aliases : Sequence[str]
        Other names which might be used.

    Returns
    -------
    ArgumentParser
        Parser/Subparser ready to add args.
    """

    if parser is None:
        return ArgumentParser(
            prog=name,
            description=description,
            **kwargs,
        )

    return parser.add_parser(
        name,
        help=description,
        description=description,
        aliases=aliases,
        **kwargs,
    )
