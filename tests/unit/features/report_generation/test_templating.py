"""Unit tests for dynamic parameter processing and templating."""

import pytest
from datetime import datetime
from reportmaker.features.report_generation.models import ParameterSchema, ParameterType
from reportmaker.shared.templating import process_parameters, render_sql_query, validate_and_cast_parameter


def test_process_parameters_defaults():
    schema = [
        ParameterSchema(name="start_date", type=ParameterType.DATE, required=True),
        ParameterSchema(name="product", type=ParameterType.STRING, required=False, default="Widget"),
    ]
    result = process_parameters(schema, {})
    assert "product" in result
    assert result["product"] == "Widget"
    # start_date is required and missing -> should raise
    with pytest.raises(ValueError, match="Required parameter 'start_date' not provided"):
        process_parameters(schema, {})


def test_process_parameters_override():
    schema = [
        ParameterSchema(name="start_date", type=ParameterType.DATE, required=True),
        ParameterSchema(name="product", type=ParameterType.STRING, required=False, default="Widget"),
    ]
    result = process_parameters(schema, {"start_date": "2026-09-01", "product": "Gadget"})
    assert result["start_date"] == datetime(2026, 9, 1).date()  # cast to date
    assert result["product"] == "Gadget"


def test_validate_and_cast_date():
    schema = ParameterSchema(name="date", type=ParameterType.DATE, required=True)
    # String ISO
    val = validate_and_cast_parameter("2026-09-01", schema)
    assert isinstance(val, datetime)
    # Datetime object
    dt = datetime(2026, 9, 1)
    val2 = validate_and_cast_parameter(dt, schema)
    assert val2 == dt
    # Invalid
    with pytest.raises(ValueError, match="Expected a date string"):
        validate_and_cast_parameter("not-a-date", schema)


def test_render_sql_query():
    context = {"start_date": "2026-09-01", "end_date": "2026-09-07", "product": "Widget"}
    query = """
    SELECT product, revenue
    FROM sales
    WHERE date BETWEEN '{{ start_date }}' AND '{{ end_date }}'
    {% if product %} AND product = '{{ product }}' {% endif %}
    """
    rendered = render_sql_query(query, context)
    expected = """
    SELECT product, revenue
    FROM sales
    WHERE date BETWEEN '2026-09-01' AND '2026-09-07'
     AND product = 'Widget' 
    """
    assert rendered.strip() == expected.strip()

    # Without product
    context_no_product = {"start_date": "2026-09-01", "end_date": "2026-09-07"}
    rendered2 = render_sql_query(query, context_no_product)
    expected2 = """
    SELECT product, revenue
    FROM sales
    WHERE date BETWEEN '2026-09-01' AND '2026-09-07'
     
    """
    assert rendered2.strip() == expected2.strip()
