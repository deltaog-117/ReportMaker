"""Pydantic models for report delivery."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from reportmaker.shared.validators import validate_email_address


class DeliveryChannel(str, Enum):
    NONE = "none"
    LOCAL = "local"
    EMAIL = "email"


class EmailDeliveryConfig(BaseModel):
    """SMTP email delivery settings for a report."""
    to: List[str] = Field(..., description="Recipient email addresses")
    cc: Optional[List[str]] = Field(None, description="CC email addresses")
    subject: Optional[str] = Field(None, description="Email subject (defaults to the report filename)")
    body: Optional[str] = Field(None, description="Email body text (defaults to a generic message)")

    @model_validator(mode="after")
    def validate_addresses(self):
        for address in [*self.to, *(self.cc or [])]:
            validate_email_address(address)
        return self


class DeliveryConfig(BaseModel):
    """Configuration for delivering a generated report."""
    channel: DeliveryChannel = DeliveryChannel.NONE
    local_dir: Optional[str] = Field(None, description="Directory to copy the report into (local channel)")
    email: Optional[EmailDeliveryConfig] = Field(None, description="Email settings (email channel)")

    @model_validator(mode="after")
    def validate_channel_fields(self):
        if self.channel == DeliveryChannel.EMAIL and self.email is None:
            raise ValueError("delivery.email must be set when channel is 'email'")
        if self.channel == DeliveryChannel.LOCAL and not self.local_dir:
            raise ValueError("delivery.local_dir must be set when channel is 'local'")
        return self


class DeliveryResult(BaseModel):
    """Result of a delivery attempt."""
    success: bool
    channel: DeliveryChannel
    destination: Optional[str] = None
    error: Optional[str] = None
