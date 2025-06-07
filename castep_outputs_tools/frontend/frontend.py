"""User-facing frontend for castep_outputs_tools."""

import argparse
from argparse import _SubParsersAction as SubParser
from collections.abc import Iterable
from importlib.metadata import entry_points

import castep_outputs_tools
import castep_outputs_tools.tools
from castep_outputs_tools.utils.tool import Tool


def main_to_sub_parser(
    sub_parser: SubParser,
    tool: Tool,
) -> None:
    """Turn a parser into a subparser.

    Parameters
    ----------
    sub_parser : SubParser
        SubParser to add parser to.
    tool : Tool
        Parser to add.
    """
    if not isinstance(tool, Tool):
        raise TypeError(
            f"`_tool_` not defined as `Tool` class (received {type(tool).__name__}.",
        )

    parser = tool.arg_parser()
    parser.set_defaults(func=tool.run)

    sub_parser.add_parser(
        parser.prog,
        aliases=tool.aliases,
    )

    for key in (parser.prog, *tool.aliases):
        sub_parser.choices[key] = parser


def _get_tools(subparser: SubParser):
    """Get tools and add them to subparser.

    Parameters
    ----------
    subparser : SubParser
        Parser to build.
    """
    for package in entry_points(group="castep_outputs.tools"):
        tools = package.load()

        if not isinstance(tools, Iterable):
            tools = (tools,)

        for tool in tools:
            main_to_sub_parser(subparser, tool)


def main():
    """User facing frontend.

    Looks for tools defined in entry-points.
    """
    arg_parser = argparse.ArgumentParser(
        prog="castep_tools",
        description="Interface for calling castep tools.",
    )
    arg_parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s v{castep_outputs_tools.__version__}",
    )
    subparser = arg_parser.add_subparsers(
        title="Scripts",
        required=True,
        help="Run script from castep_tools",
    )

    _get_tools(subparser)

    args = arg_parser.parse_args()

    if not args:
        arg_parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
