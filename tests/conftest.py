"""Shared pytest configuration."""

import importlib.util

# The GUI's browser-simulation fixture only exists when the optional gui extra
# is installed; without it the GUI page tests skip themselves.
pytest_plugins = (
    ["nicegui.testing.user_plugin"] if importlib.util.find_spec("nicegui") else []
)
