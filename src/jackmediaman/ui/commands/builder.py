"""Command string builder for the interactive UI."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any, Optional

from .definitions import CommandDef, OptionDef, OptionType, SubcommandDef
from .registry import COMMANDS


@dataclass
class OptionValue:
    """A user-selected value for an option."""

    option: OptionDef
    value: Any

    def is_default(self) -> bool:
        """Check if value matches default."""
        return self.value == self.option.default

    def to_cli_parts(self) -> list[str]:
        """Convert to CLI string parts."""
        if self.value is None:
            return []

        # Handle boolean flags
        if self.option.option_type == OptionType.BOOLEAN:
            # Check if it's a toggle flag like --dry-run/--execute
            if "/" in self.option.cli_flag:
                positive, negative = self.option.cli_flag.split("/")
                return [positive if self.value else negative]
            # Simple boolean flag
            if self.value:
                return [self.option.cli_flag]
            return []

        # Handle list type (comma-separated)
        if self.option.option_type == OptionType.LIST:
            if isinstance(self.value, list):
                joined = self.option.separator.join(str(v) for v in self.value)
                return [self.option.cli_flag, joined]
            return [self.option.cli_flag, str(self.value)]

        # Handle path (quote if contains spaces)
        if self.option.option_type == OptionType.PATH:
            path_str = str(self.value)
            return [self.option.cli_flag, shlex.quote(path_str)]

        # Handle enum and other types
        return [self.option.cli_flag, str(self.value)]


@dataclass
class CommandBuilder:
    """Builds CLI command strings from user selections.

    Usage:
        builder = CommandBuilder()
        builder.set_command("duplicates")
        builder.set_subcommand("scan")
        builder.set_option("type", "movies")
        builder.set_option("matcher", "fuzzy")

        print(builder.preview())
        # Output: jmm duplicates scan --type movies --matcher fuzzy
    """

    _command: Optional[CommandDef] = None
    _subcommand: Optional[SubcommandDef] = None
    _options: dict[str, OptionValue] = field(default_factory=dict)
    _arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize mutable defaults."""
        self._options = {}
        self._arguments = {}

    def reset(self) -> CommandBuilder:
        """Reset builder to initial state."""
        self._command = None
        self._subcommand = None
        self._options = {}
        self._arguments = {}
        return self

    def set_command(self, name: str) -> CommandBuilder:
        """Set the command by name."""
        cmd = COMMANDS.get(name)
        if not cmd:
            raise ValueError(f"Unknown command: {name}")

        self._command = cmd
        self._subcommand = None
        self._options = {}
        self._arguments = {}

        # Initialize with defaults from command options
        for opt in cmd.options:
            if opt.default is not None:
                self._options[opt.name] = OptionValue(option=opt, value=opt.default)

        return self

    def set_subcommand(self, name: str) -> CommandBuilder:
        """Set the subcommand by name."""
        if not self._command:
            raise ValueError("Command must be set before subcommand")

        sub = self._command.get_subcommand(name)
        if not sub:
            raise ValueError(f"Unknown subcommand: {name}")

        self._subcommand = sub
        self._options = {}
        self._arguments = {}

        # Initialize with defaults from subcommand options
        for opt in sub.options:
            if opt.default is not None:
                self._options[opt.name] = OptionValue(option=opt, value=opt.default)

        return self

    def set_option(self, name: str, value: Any) -> CommandBuilder:
        """Set an option value."""
        target = self._subcommand or self._command
        if not target:
            raise ValueError("Command/subcommand must be set first")

        opt = target.get_option(name)
        if not opt:
            raise ValueError(f"Unknown option: {name}")

        if value is None:
            # Remove option if set to None
            self._options.pop(name, None)
        else:
            self._options[name] = OptionValue(option=opt, value=value)

        return self

    def toggle_option(self, name: str) -> CommandBuilder:
        """Toggle a boolean option."""
        target = self._subcommand or self._command
        if not target:
            raise ValueError("Command/subcommand must be set first")

        opt = target.get_option(name)
        if not opt:
            raise ValueError(f"Unknown option: {name}")

        if opt.option_type != OptionType.BOOLEAN:
            raise ValueError(f"Option {name} is not a boolean")

        current = self.get_option(name)
        if current is None:
            current = opt.default or False

        self.set_option(name, not current)
        return self

    def set_argument(self, name: str, value: Any) -> CommandBuilder:
        """Set a positional argument value."""
        target = self._subcommand or self._command
        if not target:
            raise ValueError("Command/subcommand must be set first")

        # Verify argument exists
        arg_names = [a.name for a in (target.arguments if hasattr(target, "arguments") else [])]
        if name not in arg_names:
            raise ValueError(f"Unknown argument: {name}")

        if value is None:
            self._arguments.pop(name, None)
        else:
            self._arguments[name] = value

        return self

    def get_option(self, name: str) -> Any:
        """Get the current value of an option."""
        opt_val = self._options.get(name)
        return opt_val.value if opt_val else None

    def get_argument(self, name: str) -> Any:
        """Get the current value of an argument."""
        return self._arguments.get(name)

    @property
    def command(self) -> Optional[CommandDef]:
        """Get the current command."""
        return self._command

    @property
    def subcommand(self) -> Optional[SubcommandDef]:
        """Get the current subcommand."""
        return self._subcommand

    def get_available_options(self) -> list[OptionDef]:
        """Get available options for current command/subcommand."""
        target = self._subcommand or self._command
        if not target:
            return []

        if hasattr(target, "options"):
            return [o for o in target.options if not o.hidden]
        return []

    def get_available_arguments(self) -> list:
        """Get available arguments for current command/subcommand."""
        target = self._subcommand or self._command
        if not target:
            return []

        return getattr(target, "arguments", [])

    def preview(self, include_defaults: bool = False) -> str:
        """Build the CLI command string preview.

        Args:
            include_defaults: If True, include options even if they match defaults

        Returns:
            The full CLI command string, e.g., "jmm duplicates scan --type movies"
        """
        parts = ["jmm"]

        # Add command
        if self._command:
            parts.append(self._command.name)

        # Add subcommand
        if self._subcommand:
            parts.append(self._subcommand.name)

        # Add arguments (positional, before options)
        target = self._subcommand or self._command
        if target and hasattr(target, "arguments"):
            for arg in target.arguments:
                if arg.name in self._arguments:
                    value = self._arguments[arg.name]
                    if value is not None:
                        # Quote paths with spaces
                        str_val = str(value)
                        parts.append(shlex.quote(str_val))

        # Add options (skip defaults unless include_defaults=True)
        for opt_val in self._options.values():
            if include_defaults or not opt_val.is_default():
                cli_parts = opt_val.to_cli_parts()
                parts.extend(cli_parts)

        return " ".join(parts)

    def preview_multiline(self, include_defaults: bool = False) -> str:
        """Build a multiline CLI command preview for display.

        Returns:
            Multiline string with each option on its own line.
        """
        lines = ["jmm"]

        # Add command
        if self._command:
            lines[0] += f" {self._command.name}"

        # Add subcommand
        if self._subcommand:
            lines[0] += f" {self._subcommand.name}"

        # Add arguments
        target = self._subcommand or self._command
        if target and hasattr(target, "arguments"):
            for arg in target.arguments:
                if arg.name in self._arguments:
                    value = self._arguments[arg.name]
                    if value is not None:
                        str_val = shlex.quote(str(value))
                        lines.append(f"    {str_val}")

        # Add options
        for opt_val in self._options.values():
            if include_defaults or not opt_val.is_default():
                cli_parts = opt_val.to_cli_parts()
                if cli_parts:
                    lines.append(f"    {' '.join(cli_parts)}")

        return "\n".join(lines)

    def is_valid(self) -> bool:
        """Check if the builder has enough info to execute."""
        if not self._command:
            return False

        # Check required arguments
        target = self._subcommand or self._command
        if target and hasattr(target, "arguments"):
            for arg in target.arguments:
                if arg.required and arg.name not in self._arguments:
                    return False

        # Check required options
        if target and hasattr(target, "options"):
            for opt in target.options:
                if opt.required and opt.name not in self._options:
                    return False

        return True

    def get_missing_required(self) -> list[str]:
        """Get list of missing required fields."""
        missing = []

        if not self._command:
            missing.append("command")
            return missing

        target = self._subcommand or self._command

        # Check required arguments
        if target and hasattr(target, "arguments"):
            for arg in target.arguments:
                if arg.required and arg.name not in self._arguments:
                    missing.append(arg.name)

        # Check required options
        if target and hasattr(target, "options"):
            for opt in target.options:
                if opt.required and opt.name not in self._options:
                    missing.append(opt.cli_flag)

        return missing

    def copy(self) -> CommandBuilder:
        """Create a copy of this builder."""
        new_builder = CommandBuilder()
        new_builder._command = self._command
        new_builder._subcommand = self._subcommand
        new_builder._options = dict(self._options)
        new_builder._arguments = dict(self._arguments)
        return new_builder
