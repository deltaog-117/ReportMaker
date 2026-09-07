"""Custom exceptions for report generation."""

class ReportError(Exception):
    """Base exception for report generation errors."""
    pass

class ConfigError(ReportError):
    """Invalid configuration."""
    pass

class DataExtractionError(ReportError):
    """Failed to extract data from the database."""
    pass

class DataTransformationError(ReportError):
    """Failed to transform data."""
    pass

class RenderingError(ReportError):
    """Failed to render output."""
    pass
