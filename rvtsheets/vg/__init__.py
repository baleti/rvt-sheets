"""Revit's visibility/graphics (V/G) override pipeline as typed stages (see ../../VG-PIPELINE.md). Pure functions on the decoded Doc dicts; no reader access here
(decode.py supplies the raw settings), so every stage is unit-testable on small fixtures."""
