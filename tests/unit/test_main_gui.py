"""Unit tests for the `reportmaker gui` command."""

import sys

from click.testing import CliRunner

from reportmaker.main import cli


def test_gui_command_explains_how_to_install_the_missing_extra(monkeypatch):
    # A None entry makes "import nicegui" raise ModuleNotFoundError(name="nicegui"),
    # exactly what a missing package does. Drop the cached pages module so it re-imports.
    monkeypatch.setitem(sys.modules, "nicegui", None)
    monkeypatch.delitem(sys.modules, "reportmaker.features.gui.pages", raising=False)

    result = CliRunner().invoke(cli, ["gui", "--no-browser"])

    assert result.exit_code == 1
    assert "reportmaker[gui]" in result.output


def test_gui_command_rejects_out_of_range_ports():
    result = CliRunner().invoke(cli, ["gui", "--port", "70000"])
    assert result.exit_code == 2
