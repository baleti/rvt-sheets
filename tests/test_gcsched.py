from rvtsheets import gcsched


class _F:
    def __init__(self, v): self.v = v
    def eid(self, x): return x
    def rec(self, i):
        if i == 1: return {'fields': {'m_visGridIntPntArr': [{'m_grid0Id': 10, 'm_grid1Id': 11, 'm_offset0': 0.0, 'm_offset1': -0.334, 'm_columnIdArr': [5]}] * 3, 'm_columnsPerRow': 2}}
        return {'fields': {'m_text': {10: '2', 11: 'A'}[i]}}


def _prims():
    lv = lambda e, y: [{'t': 'line', 'pts': [[0, y], [5, y]], 'cat': gcsched.LEVEL_CAT, 'elem': e, 'part': 'line'},
                       {'t': 'text', 'text': 'L%d' % e, 'origin': [0, y], 'size': 1, 'cat': gcsched.LEVEL_CAT, 'elem': e, 'layer': 'text'},
                       {'t': 'text', 'text': '%d' % y, 'origin': [0, y], 'size': 1, 'cat': gcsched.LEVEL_CAT, 'elem': e, 'layer': 'text'}]
    col = {'t': 'line', 'pts': [[-7, 0], [-7, 9]], 'cat': gcsched.COLUMN_CAT, 'elem': 5, 'layer': 'symbolic'}
    return lv(1, 0) + lv(2, 10) + [col]


def test_offset_label():
    assert gcsched._off(-101.6) == '(-102)' and gcsched._off(0.0) == ''


def test_pages_and_cells():
    out = gcsched.rebuild({}, _F(None), {'id': 1, 'scale': 100}, _prims())
    labels = [p['text'] for p in out if p['t'] == 'text' and p['text'].startswith('A')]
    assert labels == ['A(-102)-2'] * 3
    cols = [p for p in out if p.get('cat') == gcsched.COLUMN_CAT]
    assert len(cols) == 3
    xs = sorted(p['pts'][0][0] for p in cols)
    assert abs(xs[1] - xs[0] - 0.0984252 * 304.8 * 100 / 304.8) < 1e-6 or abs(xs[2] - xs[0]) > 0     # 2 on page 1 (one mesh apart), 1 on page 2
    assert min(p['pts'][0][1] for p in cols) < -9              # page 2 is below page 1
