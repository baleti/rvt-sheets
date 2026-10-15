"""Project units (UnitsElem.m_units.m_formatOptionsArr[0] = length) and length formatting like Revit.
displayUnits codes (DisplayUnitType order, own observation: 4 = feet + fractional inches in imperial samples, 2 = millimetres in metric):
0 m, 1 cm, 2 mm, 3 decimal feet, 4 feet-fractional inches, 5 fractional inches, 6 decimal inches (?)."""
from fractions import Fraction
from .reader import ob


def length_format(f):
    for r in f.recs('UnitsElem'):
        arr = (ob(r['fields'].get('m_units')) or {}).get('m_formatOptionsArr') or []
        if arr: return ob(arr[0])
    return {'m_displayUnits': 2, 'm_accuracy': 1.0}


def is_imperial(f):
    return length_format(f).get('m_displayUnits') in (3, 4, 5, 6)


def _round(x, acc):
    return round(x / acc) * acc if acc else x


def fmt_length(ft, opt, project=None):
    if opt.get('m_bUseDefault') and project is not None: opt = project
    du = opt.get('m_displayUnits', 2); acc = opt.get('m_accuracy') or 1.0
    neg = ft < 0; ft = abs(ft)
    if du == 4:                                          # feet and fractional inches; accuracy in feet
        inches = _round(ft * 12, acc * 12)
        f_ = int(inches // 12 + 1e-9); i = inches - f_ * 12
        fr = Fraction(i).limit_denominator(256); whole = int(fr); rem = fr - whole
        istr = ('%d' % whole) if rem == 0 else ('%d %s' % (whole, rem) if whole else '%s' % rem)
        # Revit: 'suppress 0 feet' = m_bSuppressLeadingZeros, 'suppress 0 inches' = m_bSuppressTrailingZeros, 'suppress spaces'
        sep = '-' if opt.get('m_bSuppressSpaces') else ' - '
        if f_ == 0 and opt.get('m_bSuppressLeadingZeros'): s = '%s"' % istr
        elif i == 0 and opt.get('m_bSuppressTrailingZeros') and f_ > 0: s = "%d'" % f_
        else: s = '%d\'%s%s"' % (f_, sep, istr)
    elif du == 5:
        inches = _round(ft * 12, acc * 12); fr = Fraction(inches).limit_denominator(256); whole = int(fr); rem = fr - whole
        s = ('%d' % whole if rem == 0 else '%d %s' % (whole, rem)) + '"'
    elif du == 3: s = _fix(_round(ft, acc), acc)
    elif du == 6: s = _fix(_round(ft * 12, acc), acc) + '"'
    else:
        k = {0: 0.3048, 1: 30.48, 2: 304.8}.get(du, 304.8)
        s = _fix(_round(ft * k, acc), acc)
    return ('-' if neg else '') + s


def _fix(v, acc):
    import math
    nd = max(0, -int(math.floor(math.log10(acc)))) if acc and acc < 1 else 0
    return ('%.' + str(nd) + 'f') % v
