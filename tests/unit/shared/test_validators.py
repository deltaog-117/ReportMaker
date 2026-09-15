"""Unit tests for semantic validation helpers."""

import pytest

from reportmaker.shared.validators import (
    collect_errors,
    validate_cron_expression,
    validate_database_url,
    validate_email_address,
    validate_jinja2_syntax,
)


def test_validate_cron_expression_accepts_valid():
    validate_cron_expression("0 9 * * *")


def test_validate_cron_expression_rejects_invalid():
    with pytest.raises(ValueError, match="invalid cron expression"):
        validate_cron_expression("not a cron")


def test_validate_jinja2_syntax_accepts_valid():
    validate_jinja2_syntax("SELECT * FROM t WHERE d = '{{ date }}'")


def test_validate_jinja2_syntax_rejects_invalid():
    with pytest.raises(ValueError, match="invalid Jinja2 syntax"):
        validate_jinja2_syntax("{% if %}")


def test_validate_database_url_accepts_valid():
    validate_database_url("sqlite:///sales.db")


def test_validate_database_url_rejects_invalid():
    with pytest.raises(ValueError, match="invalid database URL"):
        validate_database_url("not-a-url")


def test_validate_email_address_accepts_valid():
    validate_email_address("user@example.com")


def test_validate_email_address_rejects_invalid():
    with pytest.raises(ValueError, match="invalid email address"):
        validate_email_address("not-an-email")


def test_collect_errors_returns_only_failures():
    errors = collect_errors(
        lambda: validate_email_address("user@example.com"),
        lambda: validate_email_address("bad"),
        lambda: validate_cron_expression("bad cron"),
    )
    assert len(errors) == 2
