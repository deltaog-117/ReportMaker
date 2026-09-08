"""Jinja2 templating utilities for dynamic parameters."""

import json
from datetime import datetime
from typing import Any, Dict, Optional

import jinja2

from reportmaker.features.report_generation.models import ParameterSchema, ParameterType
from reportmaker.features.report_generation.exceptions import ConfigError


def validate_and_cast_parameter(value: Any, schema: ParameterSchema) -> Any:
    """Validate and cast a parameter value according to its schema."""
    if value is None:
        if schema.required:
            raise ValueError(f"Parameter '{schema.name}' is required")
        return None

    try:
        if schema.type == ParameterType.STRING:
            return str(value)
        elif schema.type == ParameterType.INTEGER:
            return int(value)
        elif schema.type == ParameterType.FLOAT:
            return float(value)
        elif schema.type == ParameterType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                if value.lower() in ("true", "1", "yes", "on"):
                    return True
                if value.lower() in ("false", "0", "no", "off"):
                    return False
            return bool(value)
        elif schema.type == ParameterType.DATE:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                # Try ISO format
                try:
                    return datetime.fromisoformat(value)
                except ValueError:
                    # Could also support other formats; fallback to ISO
                    pass
            raise ValueError(f"Expected a date string in ISO format for '{schema.name}'")
        else:
            raise ValueError(f"Unsupported parameter type: {schema.type}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid value for parameter '{schema.name}' (expected {schema.type}): {e}")


def render_template(template_str: str, context: Dict[str, Any]) -> str:
    """Render a Jinja2 template string with the given context."""
    env = jinja2.Environment()
    template = env.from_string(template_str)
    return template.render(**context)


def process_parameters(
    config_parameters: Optional[list[ParameterSchema]],
    provided_params: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Validate and merge provided parameters with defaults."""
    result: Dict[str, Any] = {}
    if not config_parameters:
        return result

    # Map parameter names to schemas
    schema_map = {p.name: p for p in config_parameters}

    # Start with defaults
    for param in config_parameters:
        if param.default is not None:
            result[param.name] = param.default

    # Override with provided values
    if provided_params:
        for key, value in provided_params.items():
            if key in schema_map:
                validated = validate_and_cast_parameter(value, schema_map[key])
                result[key] = validated
            else:
                # If not defined in schema, treat as string (or maybe warn)
                # We'll just pass through as string.
                result[key] = value

    # Check for required parameters that are still missing
    for param in config_parameters:
        if param.required and param.name not in result:
            raise ValueError(f"Required parameter '{param.name}' not provided and has no default")

    return result


def render_sql_query(query: str, context: Dict[str, Any]) -> str:
    """Render the SQL query with parameters."""
    return render_template(query, context)
