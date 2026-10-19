<p align="center"><img src="assets/logo.png" alt="rvt-sheets logo" width="140"></p>

<h1 align="center">rvt-sheets</h1>
<p align="center">Draw Revit sheets and views from the <code>.rvt</code> file alone.</p>

<p align="center"><a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-0f766e"></a> <img alt="Status: experimental" src="https://img.shields.io/badge/status-experimental-1e293b"></p>

## What it does

Renders sheets and the views placed on them as SVG/PDF, without Revit: title blocks, viewports, plans, sections and elevations, drafting views, legends, schedules, orthographic 3D, annotations, view filters and overrides, phases, line weights, line and fill patterns. Built on [rvt-reader](https://github.com/baleti/rvt-reader) (read-only), and mounted as a sub-app of [rvt-viewer](https://github.com/baleti/rvt-viewer).

## Quick start

```bash
export RVT_READER_DIR=/path/to/rvt-reader
python -m rvtsheets.server model.rvt     # prints a local URL with the sheet list
```

## Documentation

| File | Contents |
|---|---|
| [`DESIGN.md`](DESIGN.md) | Architecture and file-format findings used for drawing |
| [`COVERAGE.md`](COVERAGE.md) / [`FEATURE-AUDIT.md`](FEATURE-AUDIT.md) | What is and is not rendered |
| [`CONTROL-API.md`](CONTROL-API.md) | HTTP control API |
| [`VG-PIPELINE.md`](VG-PIPELINE.md) | Visibility/graphics resolution pipeline |
| [`oracle/`](oracle) | C# scripts that run inside Revit to export reference views for comparison |

Output is checked against Revit's own PDF/DXF exports with [rvt-qa](https://github.com/baleti/rvt-qa).

## Coverage

Status from the latest feature audit ([`FEATURE-AUDIT.md`](FEATURE-AUDIT.md), 2026-10-15), checked against Revit exports:

| Status | Areas |
|---|---|
| **Done** | Category visibility and overrides, view filters (rules and overrides), view range and crop, scale-dependent line weights and patterns, detail level, underlay, phases and phase filters, worksets, sheets and viewports, sections and elevations, drafting views, detail lines and filled regions, SVG export |
| **Partial** | View templates, subcategory overrides, discipline, linked models (display settings decoded, linked content not drawn), design options, levels/grids, tags, dimensions, spot elevations, text notes, schedules and legends, 3D views |
| **Missing** | Projection surface patterns, graphical column schedules, revision clouds and revision schedules |

Measured against Revit: element sets per view reach precision 0.82-0.97 and recall 0.95-0.98 on sample projects; line weights and patterns are decoded exactly. Sheet-level image agreement from [rvt-qa](https://github.com/baleti/rvt-qa) averages 78/100 over 16 ranked sheets (range 55-90).

## Pending

- Close the gaps listed under *Partial* and *Missing*, starting with schedules, tags and dimension styling, which dominate the remaining visual differences.
- Draw linked-model content (needs multi-file loading).
- Native PDF export (SVG is converted with an external tool).

## The rvt toolkit

| Repo | Role |
|---|---|
| [rvt-reader](https://github.com/baleti/rvt-reader) | Pure-Python reader: file container, schema, elements, parameters, geometry |
| [rvt-core](https://github.com/baleti/rvt-core) | Optional Rust acceleration for the reader (PyO3) |
| [rvt-viewer](https://github.com/baleti/rvt-viewer) | Browser 3D viewer built on the reader |
| [rvt-sheets](https://github.com/baleti/rvt-sheets) | Sheet and view renderer (2D drawings) built on the reader |
| [rvt-qa](https://github.com/baleti/rvt-qa) | Visual-diff QA tooling for rvt-sheets output |
| [rvt-writer](https://github.com/baleti/rvt-writer) | Experimental generator of `.rvt` / `.rte` scenes |

## Status and scope

Research-grade software developed by reverse-engineering the file format through black-box analysis of sample files and comparison with the output of the official Revit API. It is accurate on the files it has been tested against but makes no guarantees for arbitrary files. Test models (Autodesk sample files) and Revit-derived ground-truth data are **not** included in this repository.

## License

MIT, see [LICENSE](LICENSE). Autodesk and Revit are trademarks of Autodesk, Inc. This project is independent and is not affiliated with, endorsed by or sponsored by Autodesk.
