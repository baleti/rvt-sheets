// elemprobe.cs - read-only per (view, element) probe: IsHidden, element overrides, category hidden, collector membership, rebar / joist details, plus schedule exports.
// Placeholders: __FILE__ __TAG__ __VIEWS__ (comma ids) __ELEMS__ (comma ids) __SCHEDS__ (comma ids, may be empty). Output C:\wl\out\__TAG__.txt and C:\wl\out\__TAG___sched_<id>.csv
using Autodesk.Revit.DB; using System.Linq; using System.Text; using System.Collections.Generic; using System.IO;
var app = UIApp.Application; var d = app.OpenDocumentFile(@"__FILE__".Replace("/", "\\")); var sb = new StringBuilder();
Func<Func<object>, string> T = f => { try { var o = f(); return o == null ? "null" : o.ToString(); } catch (Exception ex) { return "ERR(" + ex.Message.Split('\n')[0] + ")"; } };
long[] views = "__VIEWS__".Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries).Select(long.Parse).ToArray();
long[] elems = "__ELEMS__".Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries).Select(long.Parse).ToArray();
long[] scheds = "__SCHEDS__".Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries).Select(long.Parse).ToArray();
foreach (var vid in views) {
  var v = d.GetElement(new ElementId(vid)) as View; if (v == null) { sb.AppendLine("NOVIEW " + vid); continue; }
  sb.AppendLine("VIEW " + vid + " " + v.Name + " type=" + v.ViewType + " detail=" + T(() => v.DetailLevel) + " discipline=" + T(() => v.Discipline) + " display=" + T(() => v.DisplayStyle) + " template=" + T(() => v.ViewTemplateId));
  try { var vp = v as ViewPlan; if (vp != null) { var r = vp.GetViewRange(); foreach (PlanViewPlane pl in Enum.GetValues(typeof(PlanViewPlane))) sb.AppendLine("  RANGE " + pl + " level=" + r.GetLevelId(pl) + " offset=" + T(() => r.GetOffset(pl))); } } catch (Exception ex) { sb.AppendLine("  RANGEERR " + ex.Message); }
  try { foreach (var fid in v.GetOrderedFilters()) { var f = d.GetElement(fid); sb.AppendLine("  FILTER " + fid + " " + f?.Name + " visible=" + T(() => v.GetFilterVisibility(fid)) + " enabled=" + T(() => v.GetIsFilterEnabled(fid))); } } catch (Exception ex) { sb.AppendLine("  FILTERERR " + ex.Message); }
  try { foreach (Category c in d.Settings.Categories) { try { bool h = v.GetCategoryHidden(c.Id); if (h) sb.AppendLine("  CATHIDDEN " + c.Id + " " + c.Name); } catch { } try { foreach (Category sc in c.SubCategories) { try { if (v.GetCategoryHidden(sc.Id)) sb.AppendLine("  SUBCATHIDDEN " + sc.Id + " " + c.Name + " / " + sc.Name); } catch { } } } catch { } } } catch (Exception ex) { sb.AppendLine("  CATERR " + ex.Message); }
  var coll = new HashSet<long>(); try { foreach (var x in new FilteredElementCollector(d, v.Id).WhereElementIsNotElementType()) coll.Add(x.Id.Value); } catch (Exception ex) { sb.AppendLine("  COLLERR " + ex.Message); }
  foreach (var eid in elems) {
    var e = d.GetElement(new ElementId(eid)); if (e == null) { sb.AppendLine("  NOELEM " + eid); continue; }
    string ov = ""; try { var o = v.GetElementOverrides(e.Id); ov = "proj=" + o.ProjectionLineColor?.IsValid + " halftone=" + o.Halftone + " transp=" + o.Transparency + " lineweight=" + o.ProjectionLineWeight + " cutlw=" + o.CutLineWeight + " surfvis=" + T(() => o.IsSurfaceForegroundPatternVisible); } catch (Exception ex) { ov = "ERR " + ex.Message; }
    sb.AppendLine("  ELEM " + eid + " " + e.GetType().Name + " cat=" + e.Category?.Name + " name=" + e.Name + " inCollector=" + coll.Contains(eid) + " isHidden=" + T(() => e.IsHidden(v)) + " catHidden=" + T(() => e.Category != null && v.GetCategoryHidden(e.Category.Id)) + " canBeHidden=" + T(() => e.CanBeHidden(v)) + " overrides{" + ov + "} level=" + e.LevelId + " workset=" + e.WorksetId + " phase=" + e.CreatedPhaseId + " designOption=" + e.DesignOption?.Name + " phaseStatus=" + T(() => e.GetPhaseStatus(v.get_Parameter(BuiltInParameter.VIEW_PHASE).AsElementId())));
    try { var bb = e.get_BoundingBox(null); sb.AppendLine("    BBOX " + (bb == null ? "null" : bb.Min + " .. " + bb.Max)); var bv = e.get_BoundingBox(v); sb.AppendLine("    BBOXVIEW " + (bv == null ? "null" : bv.Min + " .. " + bv.Max)); } catch (Exception ex) { sb.AppendLine("    BBOXERR " + ex.Message); }
    try { var lc = e.Location as LocationCurve; if (lc != null) sb.AppendLine("    LOCCURVE " + lc.Curve.GetEndPoint(0) + " -> " + lc.Curve.GetEndPoint(1)); } catch { }
    var rb = e as Autodesk.Revit.DB.Structure.Rebar; if (rb != null) sb.AppendLine("    REBAR unobscured=" + T(() => rb.IsUnobscuredInView(v)) + " presentation=" + T(() => rb.GetPresentationMode(v)) + " visibleInView=" + T(() => rb.IsRebarInSection(v)) + " layout=" + T(() => rb.LayoutRule) + " quantity=" + T(() => rb.Quantity) + " host=" + T(() => rb.GetHostId()));
    var fi = e as FamilyInstance; if (fi != null) sb.AppendLine("    FAMILYINSTANCE symbol=" + fi.Symbol?.FamilyName + ":" + fi.Symbol?.Name + " host=" + fi.Host?.Id + " structType=" + fi.StructuralType + " viewSpecific=" + T(() => fi.ViewSpecific));
    foreach (var p in e.Parameters.Cast<Parameter>()) { try { sb.AppendLine("    PARAM " + p.Definition.Name + " = " + p.AsValueString() + " / " + p.AsString()); } catch { } }
    if (fi != null) foreach (var p in fi.Symbol.Parameters.Cast<Parameter>()) { try { sb.AppendLine("    SYMPARAM " + p.Definition.Name + " = " + p.AsValueString() + " / " + p.AsString()); } catch { } }
  }
}
foreach (var sid in scheds) {
  var s = d.GetElement(new ElementId(sid)) as ViewSchedule; if (s == null) { sb.AppendLine("NOSCHED " + sid); continue; }
  var df = s.Definition;
  sb.AppendLine("SCHED " + sid + " " + s.Name + " itemized=" + T(() => df.IsItemized) + " grandTotal=" + T(() => df.ShowGrandTotal) + " grandTotalTitle=" + T(() => df.ShowGrandTotalTitle) + " grandTotalCount=" + T(() => df.ShowGrandTotalCount) + " grandTotalTitleText=" + T(() => df.GrandTotalTitle) + " showTitle=" + T(() => df.ShowTitle) + " showHeaders=" + T(() => df.ShowHeaders) + " filterBySheet=" + T(() => df.IsFilteredBySheet));
  for (int i = 0; i < df.GetFieldCount(); i++) { var f = df.GetField(i); sb.AppendLine("  FIELD " + i + " id=" + T(() => f.FieldId.IntegerValue) + " name=" + f.GetName() + " heading=" + f.ColumnHeading + " hidden=" + f.IsHidden + " display=" + T(() => f.DisplayType) + " width=" + T(() => f.SheetColumnWidth) + " hasTotals=" + T(() => f.GetSpecTypeId())); }
  for (int i = 0; i < df.GetFilterCount(); i++) { var f = df.GetFilter(i); sb.AppendLine("  FILTER " + i + " fieldId=" + T(() => f.FieldId.IntegerValue) + " type=" + f.FilterType + " (" + (int)f.FilterType + ") value=" + T(() => f.IsStringValue ? f.GetStringValue() : f.IsDoubleValue ? f.GetDoubleValue().ToString() : f.IsElementIdValue ? f.GetElementIdValue().ToString() : "?")); }
  for (int i = 0; i < df.GetSortGroupFieldCount(); i++) { var g = df.GetSortGroupField(i); sb.AppendLine("  SORT " + i + " fieldId=" + T(() => g.FieldId.IntegerValue) + " order=" + g.SortOrder + " header=" + g.ShowHeader + " footer=" + g.ShowFooter + " blank=" + g.ShowBlankLine); }
  try { var o = new ViewScheduleExportOptions(); o.FieldDelimiter = "\t"; o.Title = true; o.HeadersFootersBlanks = true; s.Export(@"C:\wl\out", "__TAG___sched_" + sid + ".csv", o); sb.AppendLine("  EXPORTED"); } catch (Exception ex) { sb.AppendLine("  EXPORTERR " + ex.Message); }
}
File.WriteAllText(@"C:\wl\out\__TAG__.txt", sb.ToString(), new UTF8Encoding(false)); Console.WriteLine("DONE"); d.Close(false);
