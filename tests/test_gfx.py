"""Characterisation of graphics helpers using only synthetic in-memory inputs."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets import gfx


@pytest.mark.parametrize(('raw', 'expected'), [
    (None, ''), ('', ''), (b'', ''),
    ('plain text', 'plain text'),
    ('  text \n\r\x00 ', '  text'),
    (b'caf\xe9', 'café'), (bytearray(b'caf\xe9'), 'café'),
    (repr(b'caf\xe9'), 'café'),
    (r'a\par b\line c\tab d', 'a\nb\nc\td'),
    (r"\'80\'e9\u945?\u-1?", '€éα\uffff'),
    (r'\{a\}\\b', '{a}\\b'),
    (r'{\rtf1\ansi A{\b B}\i C\i0\ul D\ulnone}', 'ABCD'),
    (r'A\unknown123 B\~C', 'ABC'),
    (r'a\par \par ', 'a'),
])
def test_rtf_text(raw, expected):
    assert gfx.rtf_text(raw) == expected


@pytest.mark.parametrize('destination', ['fonttbl', 'colortbl', 'stylesheet', 'info', '*'])
def test_rtf_drops_destination_groups(destination):
    raw = r'{\b A{' + '\\' + destination + r' hidden{nested}}B}'
    assert gfx.rtf_text(raw) == 'AB'
    # Closing the skipped group flushes the preceding buffer.
    assert gfx.rtf_styled(raw) == [[('A', True, False), ('B', True, False)]]


@pytest.mark.parametrize('raw', [None, '', b'', 'plain text', r'\ul underlined\ulnone', r'\b0\i0 plain'])
def test_rtf_styled_without_bold_or_italic(raw):
    assert gfx.rtf_styled(raw) is None


def test_rtf_styled_toggles_and_group_scope():
    assert gfx.rtf_styled(r'A{\b B{\i C}D}\i E\i0 F') == [[
        ('A', False, False), ('B', True, False), ('C', True, True),
        ('D', True, False), ('E', False, True), ('F', False, False),
    ]]


@pytest.mark.parametrize('convert', [str, lambda s: s.encode('latin1'),
                                     lambda s: bytearray(s, 'latin1'),
                                     lambda s: repr(s.encode('latin1'))])
def test_rtf_styled_escapes_and_lines(convert):
    raw = "{\\b A\\tab \\'80\\u945?\\u-1?\\{\\}\\\\\r\n\x00\\par \\line Z\\par }"
    assert gfx.rtf_styled(convert(raw)) == [
        [('A\t€α\uffff{}\\', True, False)], [], [('Z', True, False)],
    ]


def test_rtf_styled_ignores_underline_and_other_controls():
    assert gfx.rtf_styled(r'\b A\ul B\ul0 C\fs24 D\b0 E') == [
        [('ABCD', True, False), ('E', False, False)],
    ]


def test_rtf_styled_enabled_without_text_returns_empty_lines():
    assert gfx.rtf_styled(r'\b\i0') == []


@pytest.mark.parametrize(('raw', 'fs', 'bold', 'italic'), [
    (None, None, False, False), ('', None, False, False),
    ('plain', None, False, False),
    (r'\fs24 A\fs48 B', 24, False, False),
    (b'\\fs20\\b bold\\i italic', 20, True, True),
    (bytearray(b'\\fs18'), 18, False, False),
    (r'\b\i text', None, True, True),
    (r'\b1 bold\i1 italic', None, False, False),
    (r'\b0 normal\i0 normal\ul text', None, False, False),
    (r'{\b}', None, False, False),
    (r'\i\par', None, False, False),
    # This helper searches even inside destinations and does not track toggles.
    (r'{\fonttbl\fs30\b hidden}\b0 text', 30, True, False),
    (r"\par\tab\u945?\'e9", None, False, False),
])
def test_rtf_runs_literal_matching(raw, fs, bold, italic):
    assert gfx.rtf_runs(raw) == {'fs': fs, 'bold': bold, 'italic': italic}


def test_arc_full_circle():
    pts = gfx.arc_pts([1, 2, 3], 2, [1, 0, 0], [0, 1, 0], 0, 2 * math.pi)
    assert len(pts) == 73
    for index, expected in [(0, [3, 2, 3]), (18, [1, 4, 3]),
                            (36, [-1, 2, 3]), (54, [1, 0, 3]), (72, [3, 2, 3])]:
        assert pts[index] == pytest.approx(expected)
    for x, y, z in pts:
        assert (x - 1) ** 2 + (y - 2) ** 2 == pytest.approx(4)
        assert z == 3


@pytest.mark.parametrize('direction', [1, -1])
def test_arc_quarter_direction_and_endpoints(direction):
    pts = gfx.arc_pts([0, 0, 0], 1, [1, 0, 0], [0, 1, 0], 0, direction * math.pi / 2)
    assert len(pts) == 19
    assert pts[0] == pytest.approx([1, 0, 0])
    assert pts[9] == pytest.approx([math.sqrt(0.5), direction * math.sqrt(0.5), 0])
    assert pts[-1] == pytest.approx([0, direction, 0])


def test_arc_ellipse_in_rotated_plane():
    pts = gfx.arc_pts([1, 2, 3], 2, [0, 0, 1], [0, 1, 0], 0, math.pi / 2, rx=4)
    assert pts[0] == pytest.approx([1, 2, 7])
    assert pts[9] == pytest.approx([1, 2 + math.sqrt(2), 3 + 2 * math.sqrt(2)])
    assert pts[-1] == pytest.approx([1, 4, 3])


def test_arc_equal_parameters_produce_two_identical_points():
    assert gfx.arc_pts([0, 0, 0], 2, [1, 0, 0], [0, 1, 0], 0, 0) == [
        [2, 0, 0], [2, 0, 0],
    ]


@pytest.mark.parametrize(('obj', 'expected'), [
    ({}, []),
    ({'m_ctrlPoints': [{'m_Point': [1, 2, 3]}]}, []),
    ({'m_ctrlPoints': [{'m_Point': [1, 2, 3]}, {'m_Point': [4, 5, 6]},
                       {'m_Point': [7, 8, 9]}], 'm_Knots': [0, 1]},
     [[1, 2, 3], [7, 8, 9]]),
])
def test_nurbs_missing_points_or_invalid_knots(obj, expected):
    assert gfx.nurbs_points(obj) == expected


@pytest.mark.parametrize(('weight', 'middle'), [(1, 1), (3, 1.5)])
def test_nurbs_linear_rational_weights(weight, middle):
    obj = {'m_Degree': 1, 'm_ctrlPoints': [
        {'m_Point': [0, 0, 0]}, {'m_Point': [2, 0, 0], 'm_w': weight},
    ], 'm_Knots': [0, 0, 1, 1]}
    assert gfx.nurbs_points(obj, n=3) == [[0, 0, 0], [middle, 0, 0], [2, 0, 0]]
    assert len(gfx.nurbs_points(obj)) == 8


def test_nurbs_quadratic_with_trimmed_parameters():
    obj = {'m_Degree': 2, 'm_ctrlPoints': [
        {'m_Point': [0, 0, 0]}, {'m_Point': [1, 2, 0]}, {'m_Point': [2, 0, 0]},
    ], 'm_Knots': [0, 0, 0, 1, 1, 1], 'm_endParams': [0.25, 0.75]}
    assert gfx.nurbs_points(obj, n=3) == [[0.5, 0.75, 0], [1, 1, 0], [1.5, 0.75, 0]]


@pytest.mark.parametrize(('matrix', 'origin', 'expected'), [
    ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0], [[1, 2, 3], [-2, 0, 1]]),
    ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [4, -5, 6], [[5, -3, 9], [2, -5, 7]]),
    ([[0, -1, 0], [1, 0, 0], [0, 0, 1]], [0, 0, 0], [[-2, 1, 3], [0, -2, 1]]),
    ([[0, -1, 0], [1, 0, 0], [0, 0, 1]], [4, -5, 6], [[2, -4, 9], [4, -7, 7]]),
])
def test_transform_pts(matrix, origin, expected):
    assert gfx.transform_pts([[1, 2, 3], [-2, 0, 1]], matrix, origin) == expected


@pytest.mark.parametrize('pts', [[], [[1, 2, 3]]])
def test_transform_without_matrix_returns_original_and_ignores_origin(pts):
    assert gfx.transform_pts(pts, None, [10, 20, 30]) is pts


def test_transform_empty_list_with_matrix_raises():
    with pytest.raises(ValueError):
        gfx.transform_pts([], [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0])
