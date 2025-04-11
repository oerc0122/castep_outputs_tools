"""User-facing frontend for castep_outputs_tools."""

import argparse
from argparse import ArgumentParser
from argparse import _SubParsersAction as SubParser
from collections.abc import Sequence
from pkgutil import resolve_name, walk_packages

import castep_outputs_tools
import castep_outputs_tools.tools
from castep_outputs_tools.utils.tool import Tool


def main_to_sub_parser(
    sub_parser: SubParser, tool: Tool,
) -> None:
    """Turn a parser into a subparser.

    Parameters
    ----------
    sub_parser : SubParser, optional
        SubParser to add parser to.
    parser : ArgumentParser
        Parser to add.
    aliases : Sequence[str]
        Other names which might be used.
    """
    parser = tool.arg_parser()

    new_parser = sub_parser.add_parser(
        parser.prog,
        usage=parser.usage,
        description=parser.description,
        help=parser.description,
        epilog=parser.epilog,
        formatter_class=parser.formatter_class,
        prefix_chars=parser.prefix_chars,
        fromfile_prefix_chars=parser.fromfile_prefix_chars,
        argument_default=parser.argument_default,
        conflict_handler=parser.conflict_handler,
        add_help=parser.add_help,
        allow_abbrev=parser.allow_abbrev,
        exit_on_error=True,
        aliases=tool.aliases,
    )
    new_parser._actions = parser._actions
    new_parser.set_defaults(func=tool.run)
    return new_parser

def main():
    """User facing frontend.

    Looks for a `Tool` type called `_tool_` in module.
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

    for package in walk_packages(
        castep_outputs_tools.tools.__path__,
        castep_outputs_tools.tools.__name__ + ".",
    ):
        if package.ispkg:
            continue

        try:
            tool = resolve_name(package.name + ":_tool_")
        except AttributeError:
            continue

        if not isinstance(tool, Tool):
            raise TypeError(
                f"`_tool_` not defined as `Tool` class (received {type(tool).__name__}.",
            )
        main_to_sub_parser(subparser, tool)

    args = arg_parser.parse_args()

    if not args:
        arg_parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
