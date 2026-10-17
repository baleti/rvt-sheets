"""JSON form of the graphics resolution report for the viewer / control panel (see CONTROL-API.md 'Graphics resolution')."""
import json
from .resolve import resolve_view


def report_text(dec, doc, vid, vis=None, compact=True):
    """-> JSON text of resolve_view(); element ids become strings (JSON keys); rows with nothing but the object style are kept (the renderer needs the
    final style of every element), 'overrides' / 'source' are empty for them"""
    rep = resolve_view(dec, doc, vid, vis=vis, explain=True)
    return json.dumps(rep, default=int, separators=(',', ':') if compact else None)


def compact_text(dec, doc, vid, vis=None, full=False):
    """compact form (styles table + element indexes), see resolve.compact_view; this is what the /vg.json route serves"""
    from .resolve import compact_view
    return json.dumps(compact_view(dec, doc, vid, vis=vis, full=full), default=int, separators=(',', ':'))
