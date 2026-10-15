// viewexport.cs - Revit's own drawings of sheets and views, for pixel/vector comparison by rvt-sheets.
// Placeholders: __FILE__ __TAG__ __MAXVIEWS__ (cap on non-sheet views, sheets are always all) __PIXELS__ (PNG width, e.g. 3000)
// Output folder C:\wl\out\__TAG__\ : <viewId>.png (ImageExport, FitToPage), <viewId>.dxf (DXF export of the single view/sheet),
// <viewId>.pdf (Revit 2022+ only, one PDF per view/sheet, paper = sheet size; views on 'fit' paper), index.tsv (viewId, class, type, name, files, errors).
using Autodesk.Revit.DB; using System.Linq; using System.Text; using System.Collections.Generic; using System.IO;
var app = UIApp.Application; var file = @"__FILE__".Replace("/", "\\"); var outd = @"C:\wl\out\__TAG__"; int maxViews = __MAXVIEWS__; int pixels = __PIXELS__;
Directory.CreateDirectory(outd);
var idx = new StreamWriter(Path.Combine(outd, "index.tsv"), false, new UTF8Encoding(false));
Func<string, string> S = (s) => s == null ? "" : s.Replace("\t", " ").Replace("\r", "").Replace("\n", "\\n");
Document d = null;
try { d = app.OpenDocumentFile(ModelPathUtils.ConvertUserVisiblePathToModelPath(file), new OpenOptions()); } catch (Exception ex) { Console.WriteLine("OPENFAIL " + ex.Message); idx.Close(); return; }
idx.WriteLine("FILE\t" + file + "\t" + app.VersionNumber);
var all = new FilteredElementCollector(d).OfClass(typeof(View)).Cast<View>().Where(v => !v.IsTemplate && v.CanBePrinted).ToList();
var sheets = all.Where(v => v is ViewSheet).ToList();
var placed = new HashSet<string>(); foreach (ViewSheet s in sheets) foreach (var vpid in s.GetAllViewports()) { var vp = d.GetElement(vpid) as Viewport; if (vp != null) placed.Add(vp.ViewId.ToString()); }
// placed views first (they are what the sheets show), then the rest up to the cap
var others = all.Where(v => !(v is ViewSheet)).OrderBy(v => placed.Contains(v.Id.ToString()) ? 0 : 1).ThenBy(v => v.Id.ToString().Length).ThenBy(v => v.Id.ToString()).Take(maxViews).ToList();
Type pdfT = null; try { pdfT = typeof(View).Assembly.GetType("Autodesk.Revit.DB.PDFExportOptions"); } catch { }
foreach (View v in sheets.Concat(others)) {
  string vid = v.Id.ToString(); var files = new List<string>(); var errs = new List<string>();
  try {
    var o = new ImageExportOptions(); o.ExportRange = ExportRange.SetOfViews; o.SetViewsAndSheets(new List<ElementId> { v.Id });
    o.FilePath = Path.Combine(outd, vid); o.FitDirection = FitDirectionType.Horizontal; o.ZoomType = ZoomFitType.FitToPage; o.PixelSize = pixels;
    o.HLRandWFViewsFileType = ImageFileType.PNG; o.ShadowViewsFileType = ImageFileType.PNG; o.ImageResolution = ImageResolution.DPI_150;
    d.ExportImage(o);
    // Revit appends " - <view type> - <name>" to FilePath: rename to <vid>.png
    foreach (var f in Directory.GetFiles(outd, vid + "*.png")) { var dst = Path.Combine(outd, vid + ".png"); if (f != dst) { if (File.Exists(dst)) File.Delete(dst); File.Move(f, dst); } files.Add(vid + ".png"); break; }
  } catch (Exception ex) { errs.Add("png:" + S(ex.Message.Split((char)10)[0])); }
  try {
    var o = new DXFExportOptions(); d.Export(outd, vid + ".dxf", new List<ElementId> { v.Id }, o);
    if (File.Exists(Path.Combine(outd, vid + ".dxf"))) files.Add(vid + ".dxf");
  } catch (Exception ex) { errs.Add("dxf:" + S(ex.Message.Split((char)10)[0])); }
  if (pdfT != null) {
    try {
      var o = Activator.CreateInstance(pdfT);
      pdfT.GetProperty("FileName").SetValue(o, vid, null);
      try { pdfT.GetProperty("Combine").SetValue(o, true, null); } catch { }
      try { pdfT.GetProperty("HideCropBoundaries").SetValue(o, true, null); } catch { }
      try { pdfT.GetProperty("HideScopeBoxes").SetValue(o, true, null); } catch { }
      try { pdfT.GetProperty("HideReferencePlane").SetValue(o, true, null); } catch { }
      try { pdfT.GetProperty("HideUnreferencedViewTags").SetValue(o, false, null); } catch { }
      try { pdfT.GetProperty("ZoomType").SetValue(o, Enum.Parse(pdfT.GetProperty("ZoomType").PropertyType, "Zoom"), null); pdfT.GetProperty("ZoomPercentage").SetValue(o, 100, null); } catch { }
      try { var pt = pdfT.GetProperty("PaperFormat"); pt.SetValue(o, Enum.Parse(pt.PropertyType, "Default"), null); } catch { }
      try { var rt = pdfT.GetProperty("RasterQuality"); rt.SetValue(o, Enum.Parse(rt.PropertyType, "High"), null); } catch { }
      try { var ct = pdfT.GetProperty("ColorDepth"); ct.SetValue(o, Enum.Parse(ct.PropertyType, "Color"), null); } catch { }
      var m = typeof(Document).GetMethods().First(mm => mm.Name == "Export" && mm.GetParameters().Length == 3 && mm.GetParameters()[2].ParameterType == pdfT);
      m.Invoke(d, new object[] { outd, new List<ElementId> { v.Id }, o });
      if (File.Exists(Path.Combine(outd, vid + ".pdf"))) files.Add(vid + ".pdf");
    } catch (Exception ex) { var e2 = ex.InnerException ?? ex; errs.Add("pdf:" + S(e2.Message.Split((char)10)[0])); }
  }
  idx.WriteLine("VIEW\t" + vid + "\t" + v.GetType().Name + "\t" + v.ViewType + "\t" + S(v.Name) + "\tscale=" + v.Scale + "\tplaced=" + placed.Contains(vid) + "\t" + string.Join(",", files) + "\t" + string.Join(";", errs));
  idx.Flush();
}
idx.WriteLine("END");
idx.Close();
try { d.Close(false); } catch { }
