"""Length formatting tests using only in-memory unit options."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets import units


@pytest.mark.parametrize(("ft", "flags", "expected"), [
    (4, {}, "4' - 0\""),
    (5 / 12, {}, "0' - 5\""),
    (5 / 12, {"m_bSuppressLeadingZeros": True}, '5"'),
    (4 + 0.5 / 12, {}, "4' - 0 1/2\""),
    (4 + 0.5 / 12, {"m_bSuppressTrailingZeros": True}, "4' - 1/2\""),
    (4, {"m_bSuppressTrailingZeros": True}, "4'"),
    (4.5, {"m_bSuppressSpaces": True}, "4'-6\""),
    (0, {}, "0' - 0\""),
    (0, {"m_bSuppressTrailingZeros": True}, "0' - 0\""),
    (0, {"m_bSuppressLeadingZeros": True}, '0"'),
    (-4.5, {}, "-4' - 6\""),
    (-0.5 / 12, {"m_bSuppressLeadingZeros": True}, '-1/2"'),
    (1e-12, {}, "0' - 0\""),
    (-1e-9, {}, "0' - 0\""),
    (-1.1e-9, {}, "-0' - 0\""),
    (1_000_000.5, {}, "1000000' - 6\""),
])
def test_feet_and_fractional_inches(ft, flags, expected):
    opt = {"m_displayUnits": 4, "m_accuracy": 1 / 24, **flags}
    assert units.fmt_length(ft, opt) == expected


@pytest.mark.parametrize(("inches", "expected"), [
    (0.25 - 1e-6, "0' - 0\""),
    (0.25, "0' - 1/2\""),
    (0.25 + 1e-6, "0' - 1/2\""),
    (0.75 - 1e-6, "0' - 1/2\""),
    (0.75, "0' - 1\""),
    (0.75 + 1e-6, "0' - 1\""),
    (11.75 - 1e-6, "0' - 11 1/2\""),
    (11.75, "1' - 0\""),
    (-0.25, "-0' - 1/2\""),
])
def test_half_inch_rounding_boundaries(inches, expected):
    assert units.fmt_length(
        inches / 12, {"m_displayUnits": 4, "m_accuracy": 1 / 24}
    ) == expected


def test_quarter_inch_half_rounds_up():
    assert units.fmt_length(
        195.625 / 12, {"m_displayUnits": 4, "m_accuracy": 1 / 48}
    ) == "16' - 3 3/4\""


@pytest.mark.parametrize(("du", "acc", "ft", "expected"), [
    (0, 0.001, 1, "0.305"),
    (1, 0.01, 1, "30.48"),
    (2, 1, 1, "305"),
    (2, 0.1, -1, "-304.8"),
    (99, 1, 1, "305"),
    (3, 0.01, 1.125, "1.13"),
    (3, 0.01, -1.125, "-1.13"),
    (3, 0.01, 0, "0.00"),
    (3, 0.01, 1e-12, "0.00"),
    (3, 0.01, 1_000_000.25, "1000000.25"),
    (3, 0.25, 1.25, "1.2"),  # _fix chooses one decimal place from accuracy.
    (5, 1 / 48, 0.125 / 12, '0 1/4"'),
    (5, 1 / 48, -1.5 / 12, '-1 1/2"'),
    (5, 1 / 48, 0, '0"'),
    (6, 0.01, 1, '12.00"'),
    (6, 0.01, -0.125, '-1.50"'),
])
def test_other_length_formats(du, acc, ft, expected):
    assert units.fmt_length(
        ft, {"m_displayUnits": du, "m_accuracy": acc}
    ) == expected


def test_fractional_inches_modern_accuracy_is_in_inches():
    opt = {
        "m_unitTypeId": {"m_typeId": "vendor.unit:fractionalInches-1.0.0"},
        "m_accuracy": 0.25,
    }
    assert units.fmt_length(1.125 / 12, opt) == '1 1/4"'
    assert units.fmt_length(
        1.125 / 12, {"m_displayUnits": 5, "m_accuracy": 0.25}
    ) == '0"'


@pytest.mark.parametrize(("symbol", "expected"), [
    ({"m_typeId": ""}, "6.000"),
    ({"m_typeId": "inches"}, '6.000"'),
    (None, '6.000"'),
    ("", '6.000"'),
])
def test_decimal_inches_symbol(symbol, expected):
    assert units.fmt_length(0.5, {
        "m_displayUnits": 6, "m_accuracy": 0.001, "m_symbolTypeId": symbol,
    }) == expected


@pytest.mark.parametrize("accuracy", [None, 0])
def test_missing_or_zero_accuracy_defaults_to_one(accuracy):
    opt = {"m_displayUnits": 4}
    if accuracy is not None:
        opt["m_accuracy"] = accuracy
    assert units.fmt_length(0.5, opt) == "1' - 0\""


def test_project_default_options():
    opt = {"m_displayUnits": 3, "m_accuracy": 0.01, "m_bUseDefault": True}
    project = {"m_displayUnits": 6, "m_accuracy": 0.1}
    assert units.fmt_length(1, opt, project) == '12.0"'
    assert units.fmt_length(1, opt) == "1.00"
    assert units.fmt_length(1, {**opt, "m_bUseDefault": False}, project) == "1.00"


@pytest.mark.parametrize(("name", "code"), [
    ("meters", 0), ("centimeters", 1), ("millimeters", 2),
    ("feet", 3), ("feetFractionalInches", 4),
    ("fractionalInches", 5), ("inches", 6), ("unknown", 2),
])
def test_unit_id_codes(name, code):
    opt = {"m_unitTypeId": {"m_typeId": f"vendor.unit:{name}-1.0.0"}}
    assert units.du_of(opt) == code
    assert units.du_of({**opt, "m_displayUnits": 0}) == 0
    assert units.du_of({**opt, "m_displayUnits": None}) == code


@pytest.mark.parametrize("opt", [{}, {"m_unitTypeId": None}, {"m_unitTypeId": {}}])
def test_missing_unit_code_defaults_to_millimeters(opt):
    assert units.du_of(opt) == 2
    assert units.fmt_length(1, opt) == "305"


class MemoryProject:
    def __init__(self, *unit_records):
        self.records = [{"fields": {"m_units": u}} for u in unit_records]

    def recs(self, kind):
        assert kind == "UnitsElem"
        return self.records


def test_length_format_default_and_empty_records():
    for project in (MemoryProject(), MemoryProject(None, {}, {"m_formatOptionsArr": []})):
        assert units.length_format(project) == {"m_displayUnits": 2, "m_accuracy": 1.0}
        assert units.is_imperial(project) is False
        assert units.is_2022_plus(project) is False


@pytest.mark.parametrize("code", range(7))
def test_legacy_length_options_and_imperial_detection(code):
    opt = {"m_displayUnits": code, "m_accuracy": 0.01}
    project = MemoryProject({}, {"m_formatOptionsArr": [opt, {"m_displayUnits": 2}]})
    assert units.length_format(project) == opt
    assert units.is_imperial(project) is (code in (3, 4, 5, 6))
    assert units.is_2022_plus(project) is False


def test_modern_length_options_skip_other_specs_and_copy_options():
    opt = {"m_unitTypeId": {"m_typeId": "vendor.unit:feet-1.0.0"}, "m_accuracy": 0.01}
    project = MemoryProject({"m_formatOptionsMap": [
        {"first": {"m_typeId": "autodesk.spec.aec:area-1.0.0"}, "second": {}},
        {"first": {"m_typeId": "autodesk.spec.aec:length-1.0.0"}, "second": opt},
    ]})
    assert units.length_format(project) == {**opt, "m_displayUnits": 3}
    assert "m_displayUnits" not in opt
    assert units.is_imperial(project) is True
    assert units.is_2022_plus(project) is True


def test_legacy_array_takes_precedence_over_map():
    opt = {"m_displayUnits": 2, "m_accuracy": 1}
    project = MemoryProject({
        "m_formatOptionsArr": [opt],
        "m_formatOptionsMap": [{"first": {"m_typeId": "autodesk.spec.aec:length-1.0.0"},
                                "second": {"m_displayUnits": 3}}],
    })
    assert units.length_format(project) == opt
    assert units.is_2022_plus(project) is False


@pytest.mark.parametrize(("value", "accuracy", "expected"), [
    (0.25, 0.5, 0.5), (0.75, 0.5, 1), (-0.25, 0.5, 0),
    (1.234, 0, 1.234),
])
def test_round_helper(value, accuracy, expected):
    assert units._round(value, accuracy) == expected


@pytest.mark.parametrize(("value", "accuracy", "expected"), [
    (1, 0.001, "1.000"), (1.25, 0.25, "1.2"),
    (12, 10, "12"), (1.25, 0, "1"),
])
def test_decimal_precision_helper(value, accuracy, expected):
    assert units._fix(value, accuracy) == expected
