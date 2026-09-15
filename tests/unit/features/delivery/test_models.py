"""Unit tests for delivery configuration models."""

import pytest
from pydantic import ValidationError

from reportmaker.features.delivery.models import DeliveryChannel, DeliveryConfig, EmailDeliveryConfig


def test_delivery_config_defaults_to_none_channel():
    config = DeliveryConfig()
    assert config.channel == DeliveryChannel.NONE


def test_local_channel_requires_local_dir():
    with pytest.raises(ValidationError, match="local_dir"):
        DeliveryConfig(channel=DeliveryChannel.LOCAL)


def test_local_channel_accepts_local_dir():
    config = DeliveryConfig(channel=DeliveryChannel.LOCAL, local_dir="./archive")
    assert config.local_dir == "./archive"


def test_email_channel_requires_email_config():
    with pytest.raises(ValidationError, match="delivery.email"):
        DeliveryConfig(channel=DeliveryChannel.EMAIL)


def test_email_channel_accepts_email_config():
    config = DeliveryConfig(
        channel=DeliveryChannel.EMAIL,
        email=EmailDeliveryConfig(to=["user@example.com"]),
    )
    assert config.email.to == ["user@example.com"]


def test_email_delivery_config_rejects_invalid_address():
    with pytest.raises(ValidationError, match="invalid email address"):
        EmailDeliveryConfig(to=["not-an-email"])
