"""Core dataclasses for command definitions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class OptionType(Enum):
    """Supported option types for UI rendering."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    PATH = "path"
    ENUM = "enum"
    LIST = "list"  # Comma-separated values like "-l en,es"


@dataclass
class OptionDef:
    """Definition of a single command option."""

    name: str  # Python parameter name, e.g., "type", "dry_run"
    cli_flag: str  # CLI flag, e.g., "--type", "--dry-run"
    option_type: OptionType
    description: str = ""
    default: Any = None
    choices: list[str] = field(default_factory=list)  # For ENUM type
    required: bool = False

    # For numeric types
    min_value: Optional[int | float] = None
    max_value: Optional[int | float] = None

    # For path types
    must_exist: bool = False
    is_directory: bool = False

    # For list types
    separator: str = ","

    # UI metadata
    icon: str = ""
    short_name: str = ""  # Short flag like "-t"
    group: str = ""  # Group related options
    order: int = 0  # Display order
    hidden: bool = False  # Hide from UI


@dataclass
class ArgumentDef:
    """Definition of a positional argument."""

    name: str  # e.g., "path"
    arg_type: OptionType
    description: str = ""
    default: Any = None
    required: bool = True

    # Validation
    must_exist: bool = False
    is_directory: bool = False

    # UI metadata
    placeholder: str = ""
    icon: str = ""


@dataclass
class SubcommandDef:
    """Definition of a subcommand."""

    name: str  # e.g., "scan", "clean"
    description: str
    options: list[OptionDef] = field(default_factory=list)
    arguments: list[ArgumentDef] = field(default_factory=list)

    # The actual callable function (set by registry)
    handler: Optional[Callable[..., Any]] = None

    # UI metadata
    icon: str = ""
    category: str = ""  # e.g., "destructive", "read-only"
    confirm_required: bool = False  # Require confirmation before run

    def get_option(self, name: str) -> Optional[OptionDef]:
        """Get option by name."""
        for opt in self.options:
            if opt.name == name:
                return opt
        return None


@dataclass
class CommandDef:
    """Definition of a top-level command group."""

    name: str  # e.g., "duplicates", "process"
    description: str
    subcommands: dict[str, SubcommandDef] = field(default_factory=dict)

    # For commands that can run directly (without subcommand)
    options: list[OptionDef] = field(default_factory=list)
    arguments: list[ArgumentDef] = field(default_factory=list)
    handler: Optional[Callable[..., Any]] = None

    # UI metadata
    icon: str = ""
    order: int = 0  # Display order in command list

    def get_subcommand(self, name: str) -> Optional[SubcommandDef]:
        """Get subcommand by name."""
        return self.subcommands.get(name)

    def get_option(self, name: str) -> Optional[OptionDef]:
        """Get option by name."""
        for opt in self.options:
            if opt.name == name:
                return opt
        return None
