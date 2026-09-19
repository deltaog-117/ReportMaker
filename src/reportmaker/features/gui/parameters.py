"""Turn raw form input into typed report parameters."""

import math
from datetime import date, datetime
from typing import Any, Dict, Mapping, Optional, Sequence

from reportmaker.features.gui.exceptions import ParameterInputError
from reportmaker.features.report_generation.models import ParameterSchema, ParameterType

_TRUE_WORDS = frozenset({"true", "1", "yes", "on"})
_FALSE_WORDS = frozenset({"false", "0", "no", "off"})


def field_label(name: str) -> str:
    """Turn a parameter name like 'start_date' into 'Start date'."""
    return name.replace("_", " ").strip().capitalize()


def _is_blank(raw: Any) -> bool:
    return raw is None or (isinstance(raw, str) and not raw.strip())


def _to_int(raw: Any) -> int:
    if isinstance(raw, bool):
        raise ValueError("must be a whole number")
    if isinstance(raw, float):
        # ui.number hands back floats, so 5.0 is a legitimate whole number.
        if raw.is_integer():
            return int(raw)
        raise ValueError("must be a whole number")
    try:
        return int(str(raw).strip())
    except ValueError:
        raise ValueError("must be a whole number") from None


def _to_float(raw: Any) -> float:
    if isinstance(raw, bool):
        raise ValueError("must be a number")
    try:
        value = float(str(raw).strip())
    except ValueError:
        raise ValueError("must be a number") from None
    if not math.isfinite(value):
        raise ValueError("must be a number")
    return value


def _to_date(raw: Any) -> str:
    if isinstance(raw, (date, datetime)):
        return raw.isoformat()
    if isinstance(raw, str):
        text = raw.strip()
        try:
            # Same parser the pipeline applies later, so anything accepted
            # here cannot fail downstream.
            datetime.fromisoformat(text)
        except ValueError:
            raise ValueError("must be a date like 2026-09-05") from None
        return text
    raise ValueError("must be a date like 2026-09-05")


def _to_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        word = raw.strip().lower()
        if word in _TRUE_WORDS:
            return True
        if word in _FALSE_WORDS:
            return False
    raise ValueError("must be yes or no")


_CONVERTERS = {
    ParameterType.STRING: lambda raw: str(raw).strip(),
    ParameterType.INTEGER: _to_int,
    ParameterType.FLOAT: _to_float,
    ParameterType.DATE: _to_date,
    ParameterType.BOOLEAN: _to_bool,
}


def coerce_parameter_input(schema: ParameterSchema, raw: Any) -> Optional[Any]:
    """Convert one form value to the type the schema declares.

    Returns None for a blank field, meaning "not provided" so the report's
    own default applies. Raises ValueError with a user-facing message when
    the value cannot be converted.
    """
    if _is_blank(raw):
        return None
    return _CONVERTERS[schema.type](raw)


def build_parameters(
    schemas: Sequence[ParameterSchema], raw_values: Mapping[str, Any]
) -> Dict[str, Any]:
    """Validate a whole form and return the parameters to run the report with.

    Blank optional fields are left out so defaults apply. Every problem is
    collected before raising.

    Raises:
        ParameterInputError: if any field is invalid or a required field is
            blank and has no default.

    """
    parameters: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    for schema in schemas:
        try:
            value = coerce_parameter_input(schema, raw_values.get(schema.name))
        except ValueError as e:
            errors[schema.name] = str(e)
            continue
        if value is not None:
            parameters[schema.name] = value
        elif schema.required and schema.default is None:
            errors[schema.name] = "is required"
    if errors:
        raise ParameterInputError(errors)
    return parameters
