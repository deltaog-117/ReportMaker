"""Custom exceptions for scheduling."""

class SchedulingError(Exception):
    """Base exception for scheduling errors."""
    pass

class ScheduleNotFoundError(SchedulingError):
    """Raised when a schedule is not found."""
    pass

class ScheduleAlreadyExistsError(SchedulingError):
    """Raised when adding a schedule with an existing name."""
    pass
