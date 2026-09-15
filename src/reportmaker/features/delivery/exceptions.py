"""Custom exceptions for report delivery."""

class DeliveryError(Exception):
    """Base exception for delivery errors."""
    pass

class EmailDeliveryError(DeliveryError):
    """Raised when sending a report by email fails."""
    pass
