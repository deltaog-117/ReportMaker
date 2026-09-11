"""Abstract interfaces for the report generation pipeline stages."""

from abc import ABC, abstractmethod
from typing import Any, Dict

import pandas as pd

from reportmaker.features.report_generation.models import ReportConfig


class Extractor(ABC):
    """Extract raw data from a data source."""
    @abstractmethod
    def extract(self, config: ReportConfig, parameters: Dict[str, Any]) -> pd.DataFrame:
        """Execute query with rendered parameters and return DataFrame."""
        pass


class Transformer(ABC):
    """Transform raw data into the final dataset for rendering."""
    @abstractmethod
    def transform(self, df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
        """Apply transformations (groupby, pivot, aggregations)."""
        pass


class Renderer(ABC):
    """Render the processed data into an output file."""
    @abstractmethod
    def render(self, df: pd.DataFrame, config: ReportConfig, output_path: str) -> str:
        """Generate the report file and return its path."""
        pass
