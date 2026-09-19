"""Unit and property tests for turning form input into report parameters."""

from datetime import date, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from reportmaker.features.gui.exceptions import ParameterInputError
from reportmaker.features.gui.parameters import (
    build_parameters,
    coerce_parameter_input,
    field_label,
)
from reportmaker.features.report_generation.models import ParameterSchema, ParameterType


def make_schema(kind, required=True, default=None, name="p"):
    return ParameterSchema(name=name, type=kind, required=required, default=default)


# ---------- Properties ----------
@given(st.integers())
def test_integer_text_round_trips(number):
    schema = make_schema(ParameterType.INTEGER)
    assert build_parameters([schema], {"p": str(number)}) == {"p": number}


@given(st.integers(min_value=-(10**12), max_value=10**12))
def test_whole_floats_from_number_widgets_become_ints(number):
    schema = make_schema(ParameterType.INTEGER)
    assert build_parameters([schema], {"p": float(number)}) == {"p": number}


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_float_text_round_trips(number):
    schema = make_schema(ParameterType.FLOAT)
    assert build_parameters([schema], {"p": repr(number)}) == {"p": number}


@given(st.dates())
def test_iso_dates_pass_through_unchanged(day):
    schema = make_schema(ParameterType.DATE)
    assert build_parameters([schema], {"p": day.isoformat()}) == {"p": day.isoformat()}


@given(
    st.sampled_from(list(ParameterType)),
    st.one_of(st.none(), st.text(), st.integers(), st.floats(), st.booleans()),
)
def test_arbitrary_input_yields_a_dict_or_a_parameter_error(kind, raw):
    schema = make_schema(kind, required=False)
    try:
        result = build_parameters([schema], {"p": raw})
    except ParameterInputError as error:
        assert set(error.errors) == {"p"}
    else:
        assert set(result) <= {"p"}


@given(st.sampled_from(list(ParameterType)), st.text(alphabet=" \t\n"))
def test_blank_optional_fields_are_left_out(kind, blank):
    assert build_parameters([make_schema(kind, required=False)], {"p": blank}) == {}


@given(st.sampled_from(list(ParameterType)), st.text(alphabet=" \t\n"))
def test_blank_required_field_without_default_is_rejected(kind, blank):
    with pytest.raises(ParameterInputError) as raised:
        build_parameters([make_schema(kind)], {"p": blank})
    assert raised.value.errors == {"p": "is required"}


# ---------- Examples ----------
def test_blank_required_field_with_default_lets_the_default_apply():
    schema = make_schema(ParameterType.STRING, default="Widget")
    assert build_parameters([schema], {"p": ""}) == {}


def test_every_problem_is_reported_at_once():
    schemas = [
        make_schema(ParameterType.INTEGER, name="count"),
        make_schema(ParameterType.DATE, name="start"),
        make_schema(ParameterType.STRING, name="fine"),
    ]
    with pytest.raises(ParameterInputError) as raised:
        build_parameters(schemas, {"count": "abc", "start": "tomorrow", "fine": "ok"})
    assert set(raised.value.errors) == {"count", "start"}


def test_unknown_form_values_are_ignored():
    schema = make_schema(ParameterType.STRING)
    assert build_parameters([schema], {"p": "x", "other": "y"}) == {"p": "x"}


@pytest.mark.parametrize("raw", ["3.5", 3.5, True, "1e3"])
def test_integer_rejects_non_whole_numbers(raw):
    with pytest.raises(ValueError):
        coerce_parameter_input(make_schema(ParameterType.INTEGER), raw)


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "1e999", "twelve", True])
def test_float_rejects_non_finite_and_non_numeric(raw):
    with pytest.raises(ValueError):
        coerce_parameter_input(make_schema(ParameterType.FLOAT), raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(True, True), (False, False), ("Yes", True), ("off", False), (" TRUE ", True)],
)
def test_boolean_accepts_switches_and_common_words(raw, expected):
    assert coerce_parameter_input(make_schema(ParameterType.BOOLEAN), raw) is expected


def test_boolean_rejects_unknown_words():
    with pytest.raises(ValueError):
        coerce_parameter_input(make_schema(ParameterType.BOOLEAN), "maybe")


def test_date_accepts_date_objects_and_trims_text():
    schema = make_schema(ParameterType.DATE)
    assert coerce_parameter_input(schema, date(2026, 9, 5)) == "2026-09-05"
    assert (
        coerce_parameter_input(schema, datetime(2026, 9, 5, 8, 30))
        == "2026-09-05T08:30:00"
    )
    assert coerce_parameter_input(schema, " 2026-09-05 ") == "2026-09-05"


@pytest.mark.parametrize("raw", ["05/09/2026", "2026-13-40", 20260905])
def test_date_rejects_other_formats(raw):
    with pytest.raises(ValueError):
        coerce_parameter_input(make_schema(ParameterType.DATE), raw)


def test_string_is_trimmed():
    assert (
        coerce_parameter_input(make_schema(ParameterType.STRING), "  Widget ")
        == "Widget"
    )


def test_field_label_is_human_readable():
    assert field_label("start_date") == "Start date"
