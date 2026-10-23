from rvtsheets.pdf import flatten_scaled_text

SVG = '<svg><text xml:space="preserve" transform="translate(10 20) rotate(-90.000) scale(2.0000 1)" font-family="Arial" font-size="10" text-anchor="start" fill="#000"><tspan x="0.000" dy="-3.0">Hi &amp; Lo</tspan></text></svg>'


def test_wide_text_becomes_outline():
    out = flatten_scaled_text(SVG)
    assert '<text' not in out and '<path' in out and 'scale(2.0000 1)' in out and 'rotate(-90.000)' in out


def test_mild_width_factor_untouched():
    s = SVG.replace('2.0000', '0.8500')
    assert flatten_scaled_text(s) == s


def test_plain_text_untouched():
    s = '<svg><text transform="translate(1 2)" font-size="4">x</text></svg>'
    assert flatten_scaled_text(s) == s
