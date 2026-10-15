# viewdump.cs output (`<tag>.views`, TSV, first column = row type). Units: feet, radians; XYZ `x,y,z`, UV `u,v`; doubles "R".
| row | columns |
|---|---|
| FILE / END | path, Revit version / count, ms |
| CAT | catId, parentCatId(-1 top), name, type, projW, cutW (line weight pen 1-16), color r,g,b, pattern projId,cutId, material, cuttable, gsProj, gsCut (GraphicsStyle ids) |
| LPAT | id, name, segments `Dash:len;Space:len;Dot:0` |
| FPAT | id, name, target (Drafting/Model), solid, host orientation, grids `a= o= off= shift= seg=` separated by `|` |
| GSTYLE | id, name, Projection/Cut, cat, parent cat |
| PHASE / PHASEFILTER / DOPT / LEVEL | id, name, (presentation per ElementOnPhaseStatus: ByCategory/Overridden/DontShow) / (primary) / (elevation) |
| FILTER | id, name, cats=; followed by FRULE rows: path, depth, rule/filter class, inverse, param id, evaluator class, RuleString/RuleValue/Precision/Epsilon |
| SELFILTER | id, name, ids |
| VIEW | id, API class, ViewType, name, template=, Scale, DetailLevel, Discipline, DisplayStyle, ViewTemplateId, CropBoxActive/Visible, PartsVisibility, Are*Hidden, origin/dir/up/right, outline (sheet-space UV of the view on paper, placed views), phase, phaseFilter, sheetNumber, detailNumber, titleOnSheet, underlay, farClip*, dependency, primary |
| VPARAM | viewId, paramId, BuiltInParameter name, display name, storage, raw value, value string |
| CROP / CROPSHAPE / ANNOCROP | viewId, min, max, transform (origin;bx;by;bz), enabled / loop, k, curve / curve |
| RANGE | viewId, PlanViewPlane, level id, offset (ViewPlan.GetViewRange) |
| TPLCTL | templateId, controlled param ids, non-controlled param ids |
| CATVIS | viewId, catId, hidden, canHide, non-default OverrideGraphicSettings members `Name=value;...` |
| VFILTER | viewId, filterId, visible, enabled (2021+), overrides |
| VIEWELEMS | viewId, n=, ids (FilteredElementCollector(doc, viewId) non-type elements = what Revit shows) |
| EOVR | viewId, elemId, element overrides |
| OWNED | viewId, elemId, class, cat, bbox(view), class-specific: TextNote text/coord/width/type, CurveElement curve/style, Dimension value/curve/segs/type, IndependentTag head/text/leader/type, FilledRegion type/loops, FamilyInstance symbol/family/loc/tr |
| SHEET | sheetId, number, name, placeholder, outline |
| VIEWPORT | vpId, sheet, view, center (box centre, sheet feet), box min:max, rotation, type, label outline, label offset/len (2022+) |
| SCHEDINST | id, sheet, schedule view, point, rotation, bbox, titleblock revision schedule |
| TITLEBLOCK / TBPARAM / TBTPARAM | id, sheet, symbol, family:type, bbox, transform / instance params / type params |
| SHEETREV / REVISION | sheet, revision ids / id, seq, number, date, desc, issued, visibility |
| SCHEDROW / SCHEDCOLW | viewId, Header/Body, row, cells separated by U+001F / column widths |
| VPTYPE / TEXTTYPE | type id, name, params |
