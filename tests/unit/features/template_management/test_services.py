"""Unit tests for template management."""

import pytest

from reportmaker.features.report_generation.models import ReportConfig
from reportmaker.features.template_management.exceptions import (
    TemplateAlreadyExistsError,
    TemplateValidationError,
)
from reportmaker.features.template_management.services import TemplateManager


class TestSaveConfig:
    """Storing a validated config directly, without a spreadsheet."""

    @staticmethod
    def _config(name: str = "Quarterly Sales") -> ReportConfig:
        return ReportConfig(
            name=name,
            data_source={"url": "sqlite:///demo.db", "query": "SELECT 1"},
        )

    def test_saves_under_the_sanitised_report_name(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        path = manager.save_config(self._config())
        assert path == tmp_path / "quarterly_sales.yaml"
        assert manager.validate_template("quarterly_sales") == self._config()

    def test_refuses_to_replace_without_force(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        manager.save_config(self._config())
        with pytest.raises(TemplateAlreadyExistsError):
            manager.save_config(self._config())

    def test_force_replaces_and_keeps_unknown_sections(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        path = manager.save_config(self._config())
        path.write_text(path.read_text() + "delivery:\n  channels: []\n")
        manager.save_config(self._config("Quarterly Sales"), force=True)
        assert "delivery" in path.read_text()

    def test_explicit_name_pins_the_file(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        path = manager.save_config(self._config("Anything"), name="fixed")
        assert path.name == "fixed.yaml"

    @pytest.mark.parametrize("name", ["", "...", "///", "  "])
    def test_rejects_names_with_no_usable_characters(self, tmp_path, name):
        with pytest.raises(TemplateValidationError):
            TemplateManager(str(tmp_path)).save_config(self._config("x"), name=name)


class TestMultiFormatTemplates:
    """The Excel template's Output Format cell accepts several formats."""

    @staticmethod
    def _config(output) -> ReportConfig:
        return ReportConfig(
            name="Multi",
            data_source={"url": "sqlite:///demo.db", "query": "SELECT 1"},
            output=output,
        )

    def test_export_then_import_keeps_every_format(self, tmp_path):
        manager = TemplateManager(str(tmp_path / "templates"))
        manager.save_config(self._config(["pdf", "excel"]))
        xlsx = tmp_path / "multi.xlsx"
        manager.export_to_xlsx("multi", str(xlsx))

        other = TemplateManager(str(tmp_path / "other"))
        assert other.import_from_xlsx(str(xlsx)).success
        assert [f.value for f in other.validate_template("multi").output] == ["pdf", "excel"]
