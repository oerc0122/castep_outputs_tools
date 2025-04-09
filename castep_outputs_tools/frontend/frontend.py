"""User-facing frontend for castep_outputs_tools."""

import argparse
from pkgutil import resolve_name, walk_packages

import castep_outputs_tools
import castep_outputs_tools.tools
from castep_outputs_tools.utils.tool import Tool


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
    subparser = arg_parser.add_subparsers()

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
        sp = tool.arg_parser(subparser)
        sp.set_defaults(func=tool.run)

    args = arg_parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
