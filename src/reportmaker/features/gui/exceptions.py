"""Custom exceptions for the GUI feature."""

from typing import Dict


class GuiError(Exception):
    """Base exception for GUI errors; the message is safe to show a user."""


class ParameterInputError(GuiError):
    """One or more report parameters typed into a form are unusable.

    Carries every problem at once (field name -> message) so the user can
    fix the whole form in one pass instead of one error per click.
    """

    def __init__(self, errors: Dict[str, str]):
        """Store the per-field messages and join them into one readable summary."""
        self.errors = errors
        super().__init__(
            "; ".join(f"{name}: {message}" for name, message in errors.items())
        )
