// viewdump.cs - views / sheets / viewports / filters / overrides / per-view element lists (Revit API ground truth for rvt-sheets).
// Same conventions as write-lab/jobs/matdump.cs. Placeholders: __FILE__ __TAG__ __MAXIDS__ (max ids per VIEWELEMS row, 0 = all).
// Output: C:\wl\out\__TAG__.views (TSV, format in rvt-sheets/oracle/VIEWDUMP_FORMAT.md). Every section is guarded: failures become ERR rows.
using Autodesk.Revit.DB; using System.Linq; using System.Text; using System.Collections.Generic; using System.Globalization; using System.Diagnostics;
var app = UIApp.Application; var file = @"__FILE__".Replace("/", "\\"); var outp = @"C:\wl\out\__TAG__.views"; int maxIds = __MAXIDS__;
var sw = new StreamWriter(outp, false, new UTF8Encoding(false)); Action<string> W = (s) => sw.WriteLine(s);
var inv = CultureInfo.InvariantCulture;
Func<double, string> N = (x) => x.ToString("R", inv);
Func<XYZ, string> P = (p) => p == null ? "null" : N(p.X) + "," + N(p.Y) + "," + N(p.Z);
Func<UV, string> PU = (p) => p == null ? "null" : N(p.U) + "," + N(p.V);
Func<Transform, string> TR = (t) => t == null ? "null" : P(t.Origin) + ";" + P(t.BasisX) + ";" + P(t.BasisY) + ";" + P(t.BasisZ);
Func<string, string> S = (s) => s == null ? "" : s.Replace("\t", " ").Replace("\r", "").Replace("\n", "\\n");
Func<Color, string> CS = (c) => { try { if (c == null || !c.IsValid) return "none"; return c.Red + "," + c.Green + "," + c.Blue; } catch { return "none"; } };
Func<object, string, object> Prop = (o, n) => { try { var pi = o.GetType().GetProperty(n); return pi == null ? null : pi.GetValue(o, null); } catch { return null; } };
Func<object, string> PS = (o) => o == null ? "" : S(o.ToString());
Action<string, Exception> ERR = (where, ex) => W("ERR\t" + where + "\t" + S(ex.Message.Split((char)10)[0]));
Func<Curve, string> CV = c => {
  if (c == null) return "null";
  try {
    var l = c as Line; if (l != null) return l.IsBound ? "Line " + P(c.GetEndPoint(0)) + " " + P(c.GetEndPoint(1)) : "Line unbound o=" + P(l.Origin) + " d=" + P(l.Direction);
    var a = c as Arc; if (a != null) return "Arc c=" + P(a.Center) + " r=" + N(a.Radius) + " n=" + P(a.Normal) + " x=" + P(a.XDirection) + " y=" + P(a.YDirection) + (a.IsBound ? " p0=" + P(c.GetEndPoint(0)) + " p1=" + P(c.GetEndPoint(1)) + " t=" + N(c.GetEndParameter(0)) + ":" + N(c.GetEndParameter(1)) : " full");
    var e = c as Ellipse; if (e != null) return "Ellipse c=" + P(e.Center) + " rx=" + N(e.RadiusX) + " ry=" + N(e.RadiusY) + " n=" + P(e.Normal) + " x=" + P(e.XDirection) + (e.IsBound ? " t=" + N(c.GetEndParameter(0)) + ":" + N(c.GetEndParameter(1)) : " full");
    var pts = c.Tessellate(); return c.GetType().Name + " pts=" + string.Join(";", pts.Select(p => P(p)));
  } catch (Exception ex) { return "CVERR " + S(ex.Message); }
};
// OverrideGraphicSettings -> compact "k=v" list of NON-default members only
var dflt = new OverrideGraphicSettings();
Func<OverrideGraphicSettings, string> OGS = (o) => {
  if (o == null) return "";
  var parts = new List<string>();
  foreach (var pi in typeof(OverrideGraphicSettings).GetProperties()) {
    try {
      var v = pi.GetValue(o, null); var d0 = pi.GetValue(dflt, null);
      string vs = v is Color ? CS((Color)v) : (v == null ? "null" : v.ToString());
      string ds = d0 is Color ? CS((Color)d0) : (d0 == null ? "null" : d0.ToString());
      if (vs != ds) parts.Add(pi.Name + "=" + S(vs));
    } catch { }
  }
  return string.Join(";", parts);
};
Document d = null;
try { d = app.OpenDocumentFile(ModelPathUtils.ConvertUserVisiblePathToModelPath(file), new OpenOptions()); } catch (Exception ex) { Console.WriteLine("OPENFAIL " + ex.Message); sw.Close(); return; }
var swt = Stopwatch.StartNew();
W("FILE\t" + file + "\t" + app.VersionNumber);
// ---------------- categories (object styles): line weights, colours, patterns, material
try {
  Action<Category, string> Cat = null;
  Cat = (c, parent) => {
    string pw = "", cw = "", col = "", lp = "", mat = "";
    try { pw = PS(c.GetLineWeight(GraphicsStyleType.Projection)); } catch { }
    try { cw = PS(c.GetLineWeight(GraphicsStyleType.Cut)); } catch { }
    try { col = CS(c.LineColor); } catch { }
    try { lp = PS(c.GetLinePatternId(GraphicsStyleType.Projection)) + "," + PS(c.GetLinePatternId(GraphicsStyleType.Cut)); } catch { }
    try { mat = c.Material == null ? "-1" : c.Material.Id.ToString(); } catch { }
    W("CAT\t" + c.Id + "\t" + parent + "\t" + S(c.Name) + "\ttype=" + PS(c.CategoryType) + "\tprojW=" + pw + "\tcutW=" + cw + "\tcolor=" + col + "\tpattern=" + lp + "\tmaterial=" + mat + "\tcuttable=" + PS(Prop(c, "IsCuttable")) + "\tgsProj=" + PS(Prop(c.GetGraphicsStyle(GraphicsStyleType.Projection), "Id")) + "\tgsCut=" + PS(Prop(c.GetGraphicsStyle(GraphicsStyleType.Cut), "Id")));
    foreach (Category sc in c.SubCategories) { try { Cat(sc, c.Id.ToString()); } catch (Exception ex) { ERR("CAT " + sc.Id, ex); } }
  };
  foreach (Category c in d.Settings.Categories) { try { Cat(c, "-1"); } catch (Exception ex) { ERR("CAT " + c.Id, ex); } }
} catch (Exception ex) { ERR("CATS", ex); }
// ---------------- line patterns, fill patterns, line styles
try { foreach (LinePatternElement lpe in new FilteredElementCollector(d).OfClass(typeof(LinePatternElement))) { try { var lp = lpe.GetLinePattern(); W("LPAT\t" + lpe.Id + "\t" + S(lpe.Name) + "\t" + string.Join(";", lp.GetSegments().Select(s => s.Type + ":" + N(s.Length)))); } catch (Exception ex) { ERR("LPAT " + lpe.Id, ex); } } } catch (Exception ex) { ERR("LPATS", ex); }
try { foreach (FillPatternElement fpe in new FilteredElementCollector(d).OfClass(typeof(FillPatternElement))) { try { var fp = fpe.GetFillPattern(); var gs = fp.GetFillGrids().Select(g => "a=" + N(g.Angle) + " o=" + PU(g.Origin) + " off=" + N(g.Offset) + " shift=" + N(g.Shift) + " seg=" + string.Join(",", g.GetSegments().Select(x => N(x)))); W("FPAT\t" + fpe.Id + "\t" + S(fpe.Name) + "\ttarget=" + fp.Target + "\tsolid=" + fp.IsSolidFill + "\thost=" + PS(Prop(fp, "HostOrientation")) + "\t" + string.Join("|", gs)); } catch (Exception ex) { ERR("FPAT " + fpe.Id, ex); } } } catch (Exception ex) { ERR("FPATS", ex); }
try { foreach (GraphicsStyle gs in new FilteredElementCollector(d).OfClass(typeof(GraphicsStyle))) { try { var c = gs.GraphicsStyleCategory; W("GSTYLE\t" + gs.Id + "\t" + S(gs.Name) + "\t" + gs.GraphicsStyleType + "\tcat=" + (c == null ? "-1" : c.Id.ToString()) + "\tparent=" + (c != null && c.Parent != null ? c.Parent.Id.ToString() : "-1")); } catch (Exception ex) { ERR("GSTYLE " + gs.Id, ex); } } } catch (Exception ex) { ERR("GSTYLES", ex); }
// ---------------- phases, phase filters, design options, levels
try { foreach (Phase ph in d.Phases) W("PHASE\t" + ph.Id + "\t" + S(ph.Name)); } catch (Exception ex) { ERR("PHASES", ex); }
try { foreach (PhaseFilter pf in new FilteredElementCollector(d).OfClass(typeof(PhaseFilter))) { var st = new List<string>(); foreach (ElementOnPhaseStatus s in Enum.GetValues(typeof(ElementOnPhaseStatus))) { try { st.Add(s + "=" + pf.GetPhaseStatusPresentation(s)); } catch { } } W("PHASEFILTER\t" + pf.Id + "\t" + S(pf.Name) + "\t" + string.Join(";", st)); } } catch (Exception ex) { ERR("PHASEFILTERS", ex); }
try { foreach (DesignOption o in new FilteredElementCollector(d).OfClass(typeof(DesignOption))) W("DOPT\t" + o.Id + "\t" + S(o.Name) + "\tprimary=" + o.IsPrimary); } catch (Exception ex) { ERR("DOPTS", ex); }
try { foreach (Level l in new FilteredElementCollector(d).OfClass(typeof(Level))) W("LEVEL\t" + l.Id + "\t" + S(l.Name) + "\telev=" + N(l.Elevation)); } catch (Exception ex) { ERR("LEVELS", ex); }
// ---------------- filters
Action<ElementFilter, int, string> FDump = null;
FDump = (f, depth, path) => {
  if (f == null) return;
  string extra = "";
  try {
    var lf = f as ElementLogicalFilter; if (lf != null) { W("FRULE\t" + path + "\t" + depth + "\t" + f.GetType().Name + "\tinverted=" + f.Inverted); int i = 0; foreach (var sub in lf.GetFilters()) FDump(sub, depth + 1, path + "." + (i++)); return; }
    var pf = f as ElementParameterFilter; if (pf != null) {
      W("FRULE\t" + path + "\t" + depth + "\tElementParameterFilter\tinverted=" + f.Inverted); int i = 0;
      foreach (FilterRule r in pf.GetRules()) {
        FilterRule rr = r; bool inv2 = false; var ir = r as FilterInverseRule; if (ir != null) { inv2 = true; rr = ir.GetInnerRule(); }
        string pid = ""; try { pid = rr.GetRuleParameter().ToString(); } catch { }
        string ev = ""; try { var m = rr.GetType().GetMethod("GetEvaluator"); if (m != null) ev = m.Invoke(rr, null).GetType().Name; } catch { }
        string val = ""; foreach (var nm in new[] { "RuleString", "RuleValue", "Precision", "Epsilon", "CaseSensitive" }) { var v = Prop(rr, nm); if (v != null) val += nm + "=" + S(v is double ? N((double)v) : v.ToString()) + ";"; }
        W("FRULE\t" + path + "." + (i++) + "\t" + (depth + 1) + "\t" + rr.GetType().Name + "\tinverse=" + inv2 + "\tparam=" + pid + "\teval=" + ev + "\t" + val);
      }
      return;
    }
    W("FRULE\t" + path + "\t" + depth + "\t" + f.GetType().Name + "\tinverted=" + f.Inverted + "\t" + extra);
  } catch (Exception ex) { ERR("FRULE " + path, ex); }
};
try { foreach (ParameterFilterElement fe in new FilteredElementCollector(d).OfClass(typeof(ParameterFilterElement))) { try { W("FILTER\t" + fe.Id + "\t" + S(fe.Name) + "\tcats=" + string.Join(",", fe.GetCategories().Select(x => x.ToString()))); FDump(fe.GetElementFilter(), 0, fe.Id.ToString()); } catch (Exception ex) { ERR("FILTER " + fe.Id, ex); } } } catch (Exception ex) { ERR("FILTERS", ex); }
try { foreach (SelectionFilterElement fe in new FilteredElementCollector(d).OfClass(typeof(SelectionFilterElement))) W("SELFILTER\t" + fe.Id + "\t" + S(fe.Name) + "\tids=" + string.Join(",", fe.GetElementIds().Select(x => x.ToString()))); } catch (Exception ex) { ERR("SELFILTERS", ex); }
// ---------------- views
var allCats = new List<Category>(); foreach (Category c in d.Settings.Categories) { allCats.Add(c); foreach (Category sc in c.SubCategories) allCats.Add(sc); }
var views = new FilteredElementCollector(d).OfClass(typeof(View)).Cast<View>().ToList();
foreach (View v in views) {
  string vid = v.Id.ToString();
  Func<string, Parameter> BP = (n) => { try { return v.get_Parameter((BuiltInParameter)Enum.Parse(typeof(BuiltInParameter), n)); } catch { return null; } };
  try {
    var sb = new StringBuilder("VIEW\t" + vid + "\t" + v.GetType().Name + "\t" + v.ViewType + "\t" + S(v.Name));
    sb.Append("\ttemplate=" + v.IsTemplate);
    foreach (var nm in new[] { "Scale", "DetailLevel", "Discipline", "DisplayStyle", "ViewTemplateId", "CropBoxActive", "CropBoxVisible", "PartsVisibility", "AreAnnotationCategoriesHidden", "AreModelCategoriesHidden", "AreAnalyticalModelCategoriesHidden", "AreImportCategoriesHidden", "ArePointCloudsHidden", "CanBePrinted", "IsAssemblyView", "SketchPlane", "GenLevel", "ShadowIntensity", "SunlightIntensity", "Title" }) { try { var o = Prop(v, nm); if (nm == "SketchPlane" || nm == "GenLevel") o = o == null ? null : Prop(o, "Id"); sb.Append("\t" + nm + "=" + PS(o)); } catch { } }
    try { sb.Append("\torigin=" + P(v.Origin) + "\tdir=" + P(v.ViewDirection) + "\tup=" + P(v.UpDirection) + "\tright=" + P(v.RightDirection)); } catch { }
    try { var o = v.Outline; if (o != null) sb.Append("\toutline=" + PU(o.Min) + ":" + PU(o.Max)); } catch { }
    try { var p = BP("VIEW_PHASE"); if (p != null) sb.Append("\tphase=" + p.AsElementId()); } catch { }
    try { var p = BP("VIEW_PHASE_FILTER"); if (p != null) sb.Append("\tphaseFilter=" + p.AsElementId()); } catch { }
    try { var p = BP("VIEWER_SHEET_NUMBER"); if (p != null) sb.Append("\tsheetNumber=" + S(p.AsString())); } catch { }
    try { var p = BP("VIEWER_DETAIL_NUMBER"); if (p != null) sb.Append("\tdetailNumber=" + S(p.AsString())); } catch { }
    try { var p = BP("VIEW_DESCRIPTION"); if (p != null) sb.Append("\ttitleOnSheet=" + S(p.AsString())); } catch { }
    try { var p = BP("VIEW_UNDERLAY_BOTTOM_ID"); if (p != null) sb.Append("\tunderlay=" + p.AsElementId()); } catch { }
    try { var p = BP("VIEWER_BOUND_FAR_CLIPPING"); if (p != null) sb.Append("\tfarClipMode=" + p.AsInteger()); } catch { }
    try { var p = BP("VIEWER_BOUND_OFFSET_FAR"); if (p != null) sb.Append("\tfarClipOffset=" + N(p.AsDouble())); } catch { }
    try { var p = BP("VIEW_DEPENDENCY"); if (p != null) sb.Append("\tdependency=" + S(p.AsString())); } catch { }
    try { sb.Append("\tprimary=" + v.GetPrimaryViewId()); } catch { }
    W(sb.ToString());
  } catch (Exception ex) { ERR("VIEW " + vid, ex); continue; }
  // all parameters of the view (names + values: covers properties the API does not expose directly)
  try { foreach (Parameter p in v.Parameters) { try { string val = p.StorageType == StorageType.Double ? N(p.AsDouble()) : p.StorageType == StorageType.Integer ? p.AsInteger().ToString() : p.StorageType == StorageType.ElementId ? p.AsElementId().ToString() : S(p.AsString()); var bip = (p.Definition as InternalDefinition) != null ? ((InternalDefinition)p.Definition).BuiltInParameter.ToString() : "shared"; W("VPARAM\t" + vid + "\t" + p.Id + "\t" + bip + "\t" + S(p.Definition.Name) + "\t" + p.StorageType + "\t" + val + "\t" + S(p.AsValueString())); } catch { } } } catch (Exception ex) { ERR("VPARAM " + vid, ex); }
  try { var cb = v.CropBox; if (cb != null) W("CROP\t" + vid + "\tmin=" + P(cb.Min) + "\tmax=" + P(cb.Max) + "\ttr=" + TR(cb.Transform) + "\tenabled=" + cb.Enabled); } catch (Exception ex) { ERR("CROP " + vid, ex); }
  try { var m = v.GetCropRegionShapeManager(); if (m != null) { int k = 0; foreach (var loop in m.GetCropShape()) { int j = 0; foreach (Curve c in loop) W("CROPSHAPE\t" + vid + "\t" + k + "\t" + (j++) + "\t" + CV(c)); k++; } try { var am = m.GetType().GetMethod("GetAnnotationCropShape"); if (am != null) foreach (Curve c in (System.Collections.IEnumerable)am.Invoke(m, null)) W("ANNOCROP\t" + vid + "\t" + CV(c)); } catch { } } } catch { }
  var vp = v as ViewPlan; if (vp != null) { try { var vr = vp.GetViewRange(); foreach (PlanViewPlane pl in Enum.GetValues(typeof(PlanViewPlane))) { try { W("RANGE\t" + vid + "\t" + pl + "\tlevel=" + vr.GetLevelId(pl) + "\toffset=" + N(vr.GetOffset(pl))); } catch { } } } catch (Exception ex) { ERR("RANGE " + vid, ex); } }
  // view template control
  try { if (v.IsTemplate) { var ctl = v.GetTemplateParameterIds(); var non = new HashSet<string>(v.GetNonControlledTemplateParameterIds().Select(x => x.ToString())); W("TPLCTL\t" + vid + "\tcontrolled=" + string.Join(",", ctl.Where(x => !non.Contains(x.ToString())).Select(x => x.ToString())) + "\tnoncontrolled=" + string.Join(",", non)); } } catch (Exception ex) { ERR("TPLCTL " + vid, ex); }
  // category visibility + overrides (only non-default)
  foreach (Category c in allCats) {
    try {
      bool canHide = true; try { canHide = v.CanCategoryBeHidden(c.Id); } catch { }
      bool hid = false; try { hid = v.GetCategoryHidden(c.Id); } catch { }
      string o = ""; try { o = OGS(v.GetCategoryOverrides(c.Id)); } catch { }
      if (hid || o.Length > 0) W("CATVIS\t" + vid + "\t" + c.Id + "\thidden=" + hid + "\tcanHide=" + canHide + "\t" + o);
    } catch { }
  }
  // filters applied to the view
  try { foreach (ElementId fid in v.GetFilters()) { string en = ""; try { en = PS(v.GetType().GetMethod("GetIsFilterEnabled").Invoke(v, new object[] { fid })); } catch { } W("VFILTER\t" + vid + "\t" + fid + "\tvisible=" + v.GetFilterVisibility(fid) + "\tenabled=" + en + "\t" + OGS(v.GetFilterOverrides(fid))); } } catch (Exception ex) { ERR("VFILTER " + vid, ex); }
  if (v.IsTemplate) continue;
  // visible elements (what Revit draws in this view) + element overrides + owned (view-specific) elements
  if (v.ViewType == ViewType.Internal || v.ViewType == ViewType.ProjectBrowser || v.ViewType == ViewType.SystemBrowser || v.ViewType == ViewType.Undefined) continue;
  try {
    var eids = new FilteredElementCollector(d, v.Id).WhereElementIsNotElementType().ToElementIds().ToList(); var ids = eids.Select(x => x.ToString()).ToList();
    W("VIEWELEMS\t" + vid + "\tn=" + ids.Count + "\t" + string.Join(",", maxIds > 0 ? ids.Take(maxIds) : ids));
    foreach (var eid in eids) {
      try {
        var e = d.GetElement(eid); string sid = eid.ToString();
        string o = OGS(v.GetElementOverrides(e.Id)); if (o.Length > 0) W("EOVR\t" + vid + "\t" + sid + "\t" + o);
        if (e.OwnerViewId == v.Id) {
          string bb = ""; try { var b = e.get_BoundingBox(v); if (b != null) bb = P(b.Min) + ":" + P(b.Max); } catch { }
          string extra = "";
          try { var tn = e as TextNote; if (tn != null) extra = "text=" + S(tn.Text) + "\tcoord=" + P(tn.Coord) + "\twidth=" + N(tn.Width) + "\ttype=" + tn.GetTypeId(); } catch { }
          try { var dc = e as CurveElement; if (dc != null) extra = "curve=" + CV(dc.GeometryCurve) + "\tstyle=" + PS(Prop(dc.LineStyle, "Id")); } catch { }
          try { var dm = e as Dimension; if (dm != null) extra = "value=" + PS(dm.ValueString) + "\tcurve=" + CV(dm.Curve) + "\tsegs=" + dm.NumberOfSegments + "\ttype=" + dm.GetTypeId(); } catch { }
          try { var tg = e as IndependentTag; if (tg != null) extra = "head=" + P(tg.TagHeadPosition) + "\ttext=" + S(tg.TagText) + "\tleader=" + tg.HasLeader + "\ttype=" + tg.GetTypeId(); } catch { }
          try { var fr = e as FilledRegion; if (fr != null) extra = "type=" + fr.GetTypeId() + "\tloops=" + string.Join("|", fr.GetBoundaries().Select(lp => string.Join(";", lp.Select(c => CV(c))))); } catch { }
          try { var fi = e as FamilyInstance; if (fi != null) extra = "symbol=" + fi.Symbol.Id + "\tfamily=" + S(fi.Symbol.FamilyName) + ":" + S(fi.Symbol.Name) + "\tloc=" + (fi.Location is LocationPoint ? P(((LocationPoint)fi.Location).Point) + " rot=" + N(((LocationPoint)fi.Location).Rotation) : "") + "\ttr=" + TR(fi.GetTransform()); } catch { }
          W("OWNED\t" + vid + "\t" + sid + "\t" + e.GetType().Name + "\tcat=" + (e.Category == null ? "-1" : e.Category.Id.ToString()) + "\tbbox=" + bb + "\t" + extra);
        }
      } catch { }
    }
  } catch (Exception ex) { ERR("VIEWELEMS " + vid, ex); }
  // sheets: title blocks, viewports, schedule instances, revisions
  var sh = v as ViewSheet; if (sh != null) {
    try {
      W("SHEET\t" + vid + "\tnumber=" + S(sh.SheetNumber) + "\tname=" + S(sh.Name) + "\tplaceholder=" + sh.IsPlaceholder + "\toutline=" + PU(sh.Outline.Min) + ":" + PU(sh.Outline.Max));
      foreach (ElementId vpid in sh.GetAllViewports()) {
        try {
          var vpo = d.GetElement(vpid) as Viewport; var ol = vpo.GetBoxOutline(); string lab = ""; try { var lo = vpo.GetLabelOutline(); lab = P(lo.MinimumPoint) + ":" + P(lo.MaximumPoint); } catch { }
          string loff = ""; try { loff = P((XYZ)Prop(vpo, "LabelOffset")) + "\tlabelLen=" + N((double)Prop(vpo, "LabelLineLength")); } catch { }
          W("VIEWPORT\t" + vpid + "\tsheet=" + vid + "\tview=" + vpo.ViewId + "\tcenter=" + P(vpo.GetBoxCenter()) + "\tbox=" + P(ol.MinimumPoint) + ":" + P(ol.MaximumPoint) + "\trot=" + vpo.Rotation + "\ttype=" + vpo.GetTypeId() + "\tlabel=" + lab + "\tlabelOffset=" + loff);
        } catch (Exception ex) { ERR("VIEWPORT " + vpid, ex); }
      }
      foreach (ScheduleSheetInstance si in new FilteredElementCollector(d, sh.Id).OfClass(typeof(ScheduleSheetInstance))) { try { var b = si.get_BoundingBox(sh); W("SCHEDINST\t" + si.Id + "\tsheet=" + vid + "\tschedule=" + si.ScheduleId + "\tpoint=" + P(si.Point) + "\trot=" + si.Rotation + "\tbbox=" + (b == null ? "" : P(b.Min) + ":" + P(b.Max)) + "\ttitleblockRevSched=" + si.IsTitleblockRevisionSchedule); } catch (Exception ex) { ERR("SCHEDINST " + si.Id, ex); } }
      foreach (FamilyInstance tb in new FilteredElementCollector(d, sh.Id).OfCategory(BuiltInCategory.OST_TitleBlocks).OfClass(typeof(FamilyInstance))) {
        try {
          var b = tb.get_BoundingBox(sh); W("TITLEBLOCK\t" + tb.Id + "\tsheet=" + vid + "\tsymbol=" + tb.Symbol.Id + "\tfamily=" + S(tb.Symbol.FamilyName) + ":" + S(tb.Symbol.Name) + "\tbbox=" + (b == null ? "" : P(b.Min) + ":" + P(b.Max)) + "\ttr=" + TR(tb.GetTransform()));
          foreach (Parameter p in tb.Parameters) { try { W("TBPARAM\t" + tb.Id + "\t" + S(p.Definition.Name) + "\t" + p.StorageType + "\t" + S(p.StorageType == StorageType.String ? p.AsString() : p.AsValueString())); } catch { } }
          foreach (Parameter p in tb.Symbol.Parameters) { try { W("TBTPARAM\t" + tb.Symbol.Id + "\t" + S(p.Definition.Name) + "\t" + p.StorageType + "\t" + S(p.StorageType == StorageType.String ? p.AsString() : p.AsValueString())); } catch { } }
        } catch (Exception ex) { ERR("TITLEBLOCK " + tb.Id, ex); }
      }
      try { W("SHEETREV\t" + vid + "\t" + string.Join(",", sh.GetAllRevisionIds().Select(x => x.ToString()))); } catch { }
    } catch (Exception ex) { ERR("SHEET " + vid, ex); }
  }
  // schedules: visible table text (header + body) so schedule rendering can be checked cell by cell
  var vs = v as ViewSchedule; if (vs != null && !vs.IsTemplate) {
    try {
      foreach (SectionType st in new[] { SectionType.Header, SectionType.Body }) {
        var td = vs.GetTableData().GetSectionData(st); if (td == null) continue;
        for (int r = td.FirstRowNumber; r <= td.LastRowNumber; r++) { var cells = new List<string>(); for (int c = td.FirstColumnNumber; c <= td.LastColumnNumber; c++) { try { cells.Add(S(vs.GetCellText(st, r, c))); } catch { cells.Add("?"); } } W("SCHEDROW\t" + vid + "\t" + st + "\t" + r + "\t" + string.Join("\u001f", cells)); }
        try { var ws = new List<string>(); for (int c = td.FirstColumnNumber; c <= td.LastColumnNumber; c++) ws.Add(N(td.GetColumnWidth(c))); W("SCHEDCOLW\t" + vid + "\t" + st + "\t" + string.Join(",", ws)); } catch { }
      }
    } catch (Exception ex) { ERR("SCHED " + vid, ex); }
  }
}
// revisions
try { foreach (Element r in new FilteredElementCollector(d).OfCategory(BuiltInCategory.OST_Revisions).WhereElementIsNotElementType()) { var rv = r as Revision; if (rv == null) continue; W("REVISION\t" + rv.Id + "\tseq=" + rv.SequenceNumber + "\tnum=" + S(rv.RevisionNumber) + "\tdate=" + S(rv.RevisionDate) + "\tdesc=" + S(rv.Description) + "\tissued=" + rv.Issued + "\tvis=" + rv.Visibility); } } catch (Exception ex) { ERR("REVISIONS", ex); }
// viewport types / text types (for titles and annotations)
try { foreach (ElementType t in new FilteredElementCollector(d).OfCategory(BuiltInCategory.OST_Viewports).WhereElementIsElementType()) { var ps = new List<string>(); foreach (Parameter p in t.Parameters) { try { ps.Add(S(p.Definition.Name) + "=" + S(p.StorageType == StorageType.String ? p.AsString() : p.StorageType == StorageType.ElementId ? p.AsElementId().ToString() : p.AsValueString())); } catch { } } W("VPTYPE\t" + t.Id + "\t" + S(t.Name) + "\t" + string.Join(";", ps)); } } catch (Exception ex) { ERR("VPTYPES", ex); }
try { foreach (TextNoteType t in new FilteredElementCollector(d).OfClass(typeof(TextNoteType))) { var ps = new List<string>(); foreach (Parameter p in t.Parameters) { try { ps.Add(S(p.Definition.Name) + "=" + S(p.StorageType == StorageType.String ? p.AsString() : p.StorageType == StorageType.Double ? N(p.AsDouble()) : p.StorageType == StorageType.ElementId ? p.AsElementId().ToString() : p.AsInteger().ToString())); } catch { } } W("TEXTTYPE\t" + t.Id + "\t" + S(t.Name) + "\t" + string.Join(";", ps)); } } catch (Exception ex) { ERR("TEXTTYPES", ex); }
W("END\t" + views.Count + " views\t" + swt.ElapsedMilliseconds + " ms");
sw.Close();
try { d.Close(false); } catch { }
