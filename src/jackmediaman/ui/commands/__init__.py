"""Command definitions and builder for the interactive UI."""

from .definitions import (
    ArgumentDef,
    CommandDef,
    OptionDef,
    OptionType,
    SubcommandDef,
)
from .builder import CommandBuilder
from .registry import COMMANDS, get_command, get_subcommand

__all__ = [
    "ArgumentDef",
    "CommandBuilder",
    "CommandDef",
    "COMMANDS",
    "get_command",
    "get_subcommand",
    "OptionDef",
    "OptionType",
    "SubcommandDef",
]
