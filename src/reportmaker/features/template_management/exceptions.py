"""Custom exceptions for template management."""

class TemplateError(Exception):
    """Base exception for template management errors."""
    pass

class TemplateNotFoundError(TemplateError):
    """Raised when a template does not exist."""
    pass

class TemplateAlreadyExistsError(TemplateError):
    """Raised when attempting to import a template with an existing name."""
    pass

class TemplateImportError(TemplateError):
    """Raised when the spreadsheet cannot be parsed."""
    pass

class TemplateValidationError(TemplateError):
    """Raised when the spreadsheet contents fail schema validation."""
    pass
