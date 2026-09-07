"""Integration tests for report generation (requires database)."""

import pytest
from pathlib import Path
from reportmaker.features.report_generation.services import generate_report


@pytest.mark.skip(reason="Requires actual database and config file")
def test_full_generation(tmp_path):
    config_path = Path(__file__).parent / "fixtures" / "sample_report.yaml"
    if not config_path.exists():
        pytest.skip("Sample config not found")
    result = generate_report(str(config_path), output_dir=str(tmp_path))
    assert result.success
    assert Path(result.output_path).exists()
