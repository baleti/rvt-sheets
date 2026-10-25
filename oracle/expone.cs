// expone.cs - export ONE view (DXF + PNG) of FILE, optionally after forcing the plan views to regenerate (detail level toggle + Regenerate, as oracle_run REGEN=1).
// Placeholders: __FILE__ __TAG__ __VIEW__ __REGEN__ (0/1) __MOD__ (hide with __IDS__ element ids | none|coarse|structural|medium|bottom4|depth2|top2: temporary view change, never saved). Output C:\wl\out\__TAG__\<view>.dxf / .png
using Autodesk.Revit.DB; using System.Linq; using System.Text; using System.Collections.Generic; using System.IO;
var app = UIApp.Application; var d = app.OpenDocumentFile(@"__FILE__".Replace("/", "\\")); var outd = @"C:\wl\out\__TAG__"; Directory.CreateDirectory(outd);
var v = d.GetElement(new ElementId(__VIEW__L)) as View; var sb = new StringBuilder();
if (__REGEN__ == 1) using (var rt = new Transaction(d, "regen")) { rt.Start(); foreach (ViewPlan vp_ in new FilteredElementCollector(d).OfClass(typeof(ViewPlan)).Cast<ViewPlan>().ToList()) { if (vp_.IsTemplate) continue; try { var dl = vp_.DetailLevel; vp_.DetailLevel = dl == ViewDetailLevel.Fine ? ViewDetailLevel.Medium : ViewDetailLevel.Fine; vp_.DetailLevel = dl; } catch { } } d.Regenerate(); rt.Commit(); }
if ("__MOD__" != "none") using (var mt = new Transaction(d, "mod")) { mt.Start(); try { var vp = v as ViewPlan; var r = vp.GetViewRange();
  switch ("__MOD__") {
    case "hide": v.HideElements(new List<ElementId>("__IDS__".Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries).Select(x => new ElementId(long.Parse(x))))); break;
    case "coarse": v.DetailLevel = ViewDetailLevel.Coarse; break;
    case "structural": v.Discipline = ViewDiscipline.Structural; break;
    case "medium": v.DetailLevel = ViewDetailLevel.Medium; break;
    case "bottom4": r.SetOffset(PlanViewPlane.BottomClipPlane, -4); vp.SetViewRange(r); break;
    case "depth2": r.SetOffset(PlanViewPlane.ViewDepthPlane, -2); vp.SetViewRange(r); break;
    case "top2": r.SetOffset(PlanViewPlane.CutPlane, 1); r.SetOffset(PlanViewPlane.TopClipPlane, 2); vp.SetViewRange(r); break;
  } d.Regenerate(); sb.AppendLine("MOD " + "__MOD__"); } catch (Exception ex) { sb.AppendLine("MODERR " + ex.Message); } mt.Commit(); }
try { var o = new DXFExportOptions(); d.Export(outd, "__VIEW__.dxf", new List<ElementId> { v.Id }, o); sb.AppendLine("DXF " + File.Exists(Path.Combine(outd, "__VIEW__.dxf"))); } catch (Exception ex) { sb.AppendLine("DXFERR " + ex.Message); }
try { var o = new ImageExportOptions(); o.ExportRange = ExportRange.SetOfViews; o.SetViewsAndSheets(new List<ElementId> { v.Id }); o.FilePath = Path.Combine(outd, "__VIEW__"); o.FitDirection = FitDirectionType.Horizontal; o.ZoomType = ZoomFitType.FitToPage; o.PixelSize = 2400; o.HLRandWFViewsFileType = ImageFileType.PNG; o.ImageResolution = ImageResolution.DPI_150; d.ExportImage(o); sb.AppendLine("PNG ok"); } catch (Exception ex) { sb.AppendLine("PNGERR " + ex.Message); }
File.WriteAllText(@"C:\wl\out\__TAG__.txt", sb.ToString(), new UTF8Encoding(false)); Console.WriteLine("DONE"); d.Close(false);
