"""Project units (UnitsElem.m_units.m_formatOptionsArr[0] = length) and length formatting like Revit.
displayUnits codes (DisplayUnitType order, own observation: 4 = feet + fractional inches in imperial samples, 2 = millimetres in metric):
0 m, 1 cm, 2 mm, 3 decimal feet, 4 feet-fractional inches, 5 fractional inches, 6 decimal inches (?)."""
from fractions import Fraction
from .reader import ob


# Revit 2022+ stores unit ids instead of DisplayUnitType codes
UNIT_DU = {'meters': 0, 'centimeters': 1, 'millimeters': 2, 'feet': 3, 'feetFractionalInches': 4, 'fractionalInches': 5, 'inches': 6}


def du_of(opt):
    """display unit code of a format-options dict (old m_displayUnits, or 2022+ m_unitTypeId)"""
    if opt.get('m_displayUnits') is not None: return opt['m_displayUnits']
    u = (opt.get('m_unitTypeId') or {}).get('m_typeId') or ''
    return UNIT_DU.get(u.split(':')[-1].rsplit('-', 1)[0], 2)


def length_format(f):
    for r in f.recs('UnitsElem'):
        u = ob(r['fields'].get('m_units')) or {}
        arr = u.get('m_formatOptionsArr') or []
        if arr: return ob(arr[0])
        for e in u.get('m_formatOptionsMap') or []:
            if (ob(e).get('first') or {}).get('m_typeId', '').startswith('autodesk.spec.aec:length-'):
                d = dict(ob(ob(e).get('second'))); d['m_displayUnits'] = du_of(d); return d
    return {'m_displayUnits': 2, 'm_accuracy': 1.0}


def is_2022_plus(f):
    """file written by Revit 2022 or later (unit options in m_formatOptionsMap)"""
    for r in f.recs('UnitsElem'):
        u = ob(r['fields'].get('m_units')) or {}
        if u.get('m_formatOptionsMap') and not u.get('m_formatOptionsArr'): return True
    return False


def is_imperial(f):
    return length_format(f).get('m_displayUnits') in (3, 4, 5, 6)


def _round(x, acc):
    import math
    return math.floor(x / acc + 0.5 + 1e-9) * acc if acc else x          # Revit rounds halves up (195.625 in at 1/4" -> 195.75); Python's round() goes to even


def fmt_length(ft, opt, project=None):
    if opt.get('m_bUseDefault') and project is not None: opt = project
    du = du_of(opt); acc = opt.get('m_accuracy') or 1.0
    neg = ft < -1e-9; ft = abs(ft)
    if du == 4:                                          # feet and fractional inches; accuracy in feet
        inches = _round(ft * 12, acc * 12)
        f_ = int(inches // 12 + 1e-9); i = inches - f_ * 12
        fr = Fraction(i).limit_denominator(256); whole = int(fr); rem = fr - whole
        istr = ('%d' % whole) if rem == 0 else ('%d %s' % (whole, rem) if (whole or (f_ > 0 and not opt.get('m_bSuppressTrailingZeros'))) else '%s' % rem)       # '4' - 0 1/2"' keeps the zero inches
        # Revit: 'suppress 0 feet' = m_bSuppressLeadingZeros, 'suppress 0 inches' = m_bSuppressTrailingZeros, 'suppress spaces'
        sep = '-' if opt.get('m_bSuppressSpaces') else ' - '
        if f_ == 0 and opt.get('m_bSuppressLeadingZeros'): s = '%s"' % istr
        elif i == 0 and opt.get('m_bSuppressTrailingZeros') and f_ > 0: s = "%d'" % f_
        else: s = '%d\'%s%s"' % (f_, sep, istr)
    elif du == 5:
        inches = _round(ft * 12, acc if opt.get('m_unitTypeId') else acc * 12); fr = Fraction(inches).limit_denominator(256); whole = int(fr); rem = fr - whole       # 2022+ unit ids: accuracy in inches
        s = ('%d' % whole if rem == 0 else '%d %s' % (whole, rem)) + '"'
    elif du == 3: s = _fix(_round(ft, acc), acc)
    elif du == 6:
        sy_ = opt.get('m_symbolTypeId')
        s = _fix(_round(ft * 12, acc), acc) + ('' if (isinstance(sy_, dict) and sy_.get('m_typeId') == '') else '"')      # decimal inches: the symbol is an option (Facades dimension style: '6.0000000000' without the quote)
    else:
        k = {0: 0.3048, 1: 30.48, 2: 304.8}.get(du, 304.8)
        s = _fix(_round(ft * k, acc), acc)
    return ('-' if neg else '') + s


def _fix(v, acc):
    import math
    nd = max(0, -int(math.floor(math.log10(acc)))) if acc and acc < 1 else 0
    return ('%.' + str(nd) + 'f') % v
