"""Semantic validation helpers shared across features.

These check things Pydantic's structural validation cannot see: that a
string is syntactically valid *as a particular kind of thing* it claims to
be (a cron expression, a Jinja2 template, a database URL, an email
address). Each raises ``ValueError`` with a message safe to show a user.
"""

import re
from typing import Callable, List

from apscheduler.triggers.cron import CronTrigger
from jinja2 import Environment, TemplateSyntaxError
from sqlalchemy.engine import make_url

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_cron_expression(expression: str) -> None:
    """Raise ValueError if expression is not a valid 5-field cron string."""
    try:
        CronTrigger.from_crontab(expression)
    except Exception as e:
        raise ValueError(f"invalid cron expression '{expression}': {e}") from e


def validate_jinja2_syntax(template: str, field_name: str = "template") -> None:
    """Raise ValueError if template is not syntactically valid Jinja2."""
    try:
        Environment().parse(template)  # noqa: S701 -- parses only, never renders, so autoescape is moot
    except TemplateSyntaxError as e:
        raise ValueError(f"invalid Jinja2 syntax in {field_name}: {e}") from e


def validate_database_url(url: str) -> None:
    """Raise ValueError if url is not a parseable SQLAlchemy database URL."""
    try:
        make_url(url)
    except Exception as e:
        raise ValueError(f"invalid database URL '{url}': {e}") from e


def validate_email_address(address: str) -> None:
    """Raise ValueError if address is not a syntactically valid email address."""
    if not _EMAIL_RE.match(address):
        raise ValueError(f"invalid email address '{address}'")


def collect_errors(*checks: Callable[[], None]) -> List[str]:
    """Run zero-arg validation callables, collecting messages instead of raising."""
    errors: List[str] = []
    for check in checks:
        try:
            check()
        except ValueError as e:
            errors.append(str(e))
    return errors
