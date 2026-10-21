"""Elevation formatting characterisation using synthetic values only."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets import datums, units


@pytest.mark.parametrize(("ft", "expected"), [
    (0, "0"),
    (-0.0, "0"),
    (1, "305"),
    (-1, "-305"),
    (1.234, "376"),
    (-1.234, "-376"),
    (0.49 / 304.8, "0"),
    (-0.49 / 304.8, "0"),
    # The metric branch uses Python's round: ties go to even.
    (0.5 / 304.8, "0"),
    (1.5 / 304.8, "2"),
    (2.5 / 304.8, "2"),
    (-0.5 / 304.8, "0"),
    (-1.5 / 304.8, "-2"),
    (-2.5 / 304.8, "-2"),
])
def test_metric_rounds_to_millimetres(ft, expected):
    assert datums.fmt_elev(ft, False) == expected


@pytest.mark.parametrize(("ft", "expected"), [
    (0, "0' - 0\""),
    (-0.0, "0' - 0\""),
    (4, "4' - 0\""),
    (-4, "-4' - 0\""),
    (4.5, "4' - 6\""),
    (-4.5, "-4' - 6\""),
    (0.5 / 12, "0' - 0.5\""),
    (-0.5 / 12, "-0' - 0.5\""),
    # Subtracting whole feet leaves inches slightly above the halfway value.
    (4 + 0.125 / 12, "4' - 0.13\""),
    (1.234 / 12, "0' - 1.23\""),
    (1.236 / 12, "0' - 1.24\""),
    (-1.236 / 12, "-0' - 1.24\""),
    (11.994 / 12, "0' - 11.99\""),
    (11.996 / 12, "1' - 0\""),
    (-11.996 / 12, "-1' - 0\""),
    (4 + 11.996 / 12, "5' - 0\""),
    (1e-12, "0' - 0\""),
    (-1e-12, "-0' - 0\""),
])
def test_imperial_without_project(ft, expected):
    assert datums.fmt_elev(ft, True) == expected


@pytest.mark.parametrize("setting", [None, "1", "0"])
@pytest.mark.parametrize(("ft", "fallback", "fractional"), [
    (0, "0' - 0\"", False),
    (4, "4' - 0\"", False),
    (-4.5, "-4' - 6\"", False),
    (-0.5 / 12, "-0' - 0.5\"", True),
    ((6 + 0.5e-6) / 12, "0' - 6\"", False),
    ((6 - 0.5e-6) / 12, "0' - 6\"", False),
    ((6 + 2e-6) / 12, "0' - 6\"", True),
    ((6 - 2e-6) / 12, "0' - 6\"", True),
])
def test_project_delegation(monkeypatch, setting, ft, fallback, fractional):
    if setting is None:
        monkeypatch.delenv("RVT_ELEVFMT", raising=False)
    else:
        monkeypatch.setenv("RVT_ELEVFMT", setting)
    project = object()
    options = {"m_displayUnits": 4, "m_accuracy": 1 / 48}
    calls = []

    def length_format(f):
        assert f is project
        calls.append("length_format")
        return options

    def fmt_length(value, opt, defaults):
        calls.append("fmt_length")
        assert value == ft
        assert opt == {"m_bUseDefault": 1}
        assert defaults is options
        return "project-formatted elevation"

    monkeypatch.setattr(units, "length_format", length_format)
    monkeypatch.setattr(units, "fmt_length", fmt_length)
    delegates = setting != "0" or fractional
    assert datums.fmt_elev(ft, True, project) == (
        "project-formatted elevation" if delegates else fallback
    )
    assert calls == (["length_format", "fmt_length"] if delegates else [])


@pytest.mark.parametrize("setting", ["0", "1"])
@pytest.mark.parametrize("failure", ["length_format", "fmt_length"])
def test_project_errors_fall_back(monkeypatch, setting, failure):
    monkeypatch.setenv("RVT_ELEVFMT", setting)
    project = object()
    options = object()
    calls = []

    def length_format(f):
        assert f is project
        calls.append("length_format")
        if failure == "length_format":
            raise ValueError("synthetic format lookup failure")
        return options

    def fmt_length(ft, opt, defaults):
        calls.append("fmt_length")
        assert ft == -11.996 / 12
        assert opt == {"m_bUseDefault": 1}
        assert defaults is options
        raise RuntimeError("synthetic formatting failure")

    monkeypatch.setattr(units, "length_format", length_format)
    monkeypatch.setattr(units, "fmt_length", fmt_length)
    assert datums.fmt_elev(-11.996 / 12, True, project) == "-1' - 0\""
    assert calls == (
        ["length_format"] if failure == "length_format"
        else ["length_format", "fmt_length"]
    )


@pytest.mark.parametrize("setting", ["0", "1"])
def test_metric_ignores_project_format(monkeypatch, setting):
    monkeypatch.setenv("RVT_ELEVFMT", setting)

    def unexpected(*args):
        pytest.fail("metric elevations must not use project formatting")

    monkeypatch.setattr(units, "length_format", unexpected)
    monkeypatch.setattr(units, "fmt_length", unexpected)
    assert datums.fmt_elev(-1, False, object()) == "-305"
