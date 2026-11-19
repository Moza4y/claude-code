using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;
using Microsoft.Win32;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using SolidWorks.Interop.swpublished;
using SolidWorks.Interop.SWRoutingLib;

namespace SmartRoute
{
    /// <summary>
    /// SOLIDWORKS add-in: a "Smart Route" tab next to the Routing commands.
    ///  - Smart Auto Route : plans a path around the REAL geometry (engine) and builds it as a Routing route
    ///  - Scan Routes      : reads every route in the assembly (diagnostic report)
    ///  - Review Routes    : re-plans the existing routes and suggests shorter / cleaner ones
    ///  - Accuracy         : grid-cell size (speed vs exactness)
    ///  - Auto Watch       : after the assembly changes, re-read only what changed and re-review
    /// </summary>
    [ComVisible(true)]
    [Guid("8E2C6F4A-3B1D-4C5E-9A7F-2D6B1E4C7A90")]
    [ProgId("SmartRoute.Addin")]
    public class SmartRouteAddin : ISwAddin
    {
        const int GroupId = 4201;
        const string TabTitle = "Smart Route";

        ISldWorks swApp;
        ICommandManager cmdMgr;
        int cookie;
        Settings cfg;
        EngineClient engine;
        System.Windows.Forms.Timer timer;
        bool engineReady, busy, dirty;
        int lastStamp = int.MinValue;
        DateTime dirtyAt = DateTime.MinValue;

        class Job
        {
            public object Model, Comp0, Comp1, Sk0, Sk1;
            public string Name;
            public double[] P0, P1;
            public double DiaMm, BendMm;
        }

        // update check state (set from a worker thread, handled on the UI thread in OnTick)
        volatile bool updateReady, updateMsgReady, checkingUpdates, startupChecked, updateManual;
        Updater.Info pendingUpdate;
        string updateError, updateMsg;
        readonly DateTime started = DateTime.Now;

        // ------------------------------------------------------------ COM registration
        [ComRegisterFunction]
        public static void RegisterFunction(Type t)
        {
            try
            {
                string key = "SOFTWARE\\SolidWorks\\Addins\\{" + t.GUID.ToString() + "}";
                using (RegistryKey k = Registry.LocalMachine.CreateSubKey(key))
                {
                    k.SetValue(null, 0);
                    k.SetValue("Description", "Smart cable routing around real geometry");
                    k.SetValue("Title", "Smart Route");
                }
                key = "Software\\SolidWorks\\AddInsStartup\\{" + t.GUID.ToString() + "}";
                using (RegistryKey k = Registry.CurrentUser.CreateSubKey(key))
                    k.SetValue(null, 1, RegistryValueKind.DWord);
            }
            catch (Exception e) { Console.WriteLine("Registration failed: " + e.Message); }
        }

        [ComUnregisterFunction]
        public static void UnregisterFunction(Type t)
        {
            try
            {
                Registry.LocalMachine.DeleteSubKey("SOFTWARE\\SolidWorks\\Addins\\{" + t.GUID.ToString() + "}", false);
                Registry.CurrentUser.DeleteSubKey("Software\\SolidWorks\\AddInsStartup\\{" + t.GUID.ToString() + "}", false);
            }
            catch (Exception e) { Console.WriteLine("Unregistration failed: " + e.Message); }
        }

        // ------------------------------------------------------------ connect / disconnect
        public bool ConnectToSW(object ThisSW, int Cookie)
        {
            try
            {
                swApp = (ISldWorks)ThisSW;
                cookie = Cookie;
                swApp.SetAddinCallbackInfo2(0, this, cookie);
                cfg = Settings.Load();
                cmdMgr = swApp.GetCommandManager(cookie);
                AddCommands();
                string home = Path.GetDirectoryName(typeof(SmartRouteAddin).Assembly.Location);
                engine = new EngineClient
                {
                    PythonExe = cfg.PythonExe,
                    ScriptPath = Path.Combine(home, "auto_cable_route.py"),
                    ExePath = Path.Combine(home, "engine", "SmartRouteEngine.exe")
                };
                timer = new System.Windows.Forms.Timer { Interval = 250 };
                timer.Tick += OnTick;
                timer.Start();
                Log.W("Smart Route connected");
                return true;
            }
            catch (Exception e)
            {
                Log.W("ConnectToSW failed: " + e);
                return false;
            }
        }

        public bool DisconnectFromSW()
        {
            try
            {
                if (timer != null) { timer.Stop(); timer.Dispose(); timer = null; }
                if (engine != null) engine.Stop();
                RemoveCommands();
            }
            catch (Exception e) { Log.W("Disconnect: " + e.Message); }
            cmdMgr = null;
            swApp = null;
            GC.Collect();
            GC.WaitForPendingFinalizers();
            return true;
        }

        // ------------------------------------------------------------ command tab
        void AddCommands()
        {
            string iconDir = Path.Combine(Settings.Dir, "icons");
            string[] letters = { "S", "R", "V", "A", "W", "U" };
            Color[] colors = { Color.FromArgb(0, 120, 215), Color.FromArgb(90, 90, 90), Color.FromArgb(16, 137, 62),
                               Color.FromArgb(200, 120, 0), Color.FromArgb(142, 68, 173), Color.FromArgb(0, 150, 160) };
            string[] strips = Icons.Strips(iconDir, letters, colors);
            string[] mains = Icons.Mains(iconDir, "S", colors[0]);

            int err = 0;
            ICommandGroup grp = cmdMgr.CreateCommandGroup2(GroupId, TabTitle, "Smart Route", "Smart cable routing", -1, true, ref err);
            grp.IconList = strips;
            grp.MainIconList = mains;
            int opt = (int)(swCommandItemType_e.swMenuItem | swCommandItemType_e.swToolbarItem);

            var idx = new int[6];
            idx[0] = grp.AddCommandItem2("Smart Auto Route", -1, "Route around the real geometry", "Smart Auto Route", 0, "SmartAutoRoute", "EnableAsm", 1, opt);
            idx[1] = grp.AddCommandItem2("Scan Routes", -1, "Read all routes in the assembly", "Scan Routes", 1, "ScanRoutes", "EnableAsm", 2, opt);
            idx[2] = grp.AddCommandItem2("Review Routes", -1, "Suggest better routes", "Review Routes", 2, "ReviewRoutes", "EnableAsm", 3, opt);
            idx[3] = grp.AddCommandItem2("Accuracy", -1, "Speed / accuracy of the planner", "Accuracy", 3, "ChooseAccuracy", "EnableAlways", 4, opt);
            idx[4] = grp.AddCommandItem2("Auto Watch", -1, "Re-review automatically after changes", "Auto Watch", 4, "ToggleWatch", "EnableAsm", 5, opt);
            idx[5] = grp.AddCommandItem2("Updates", -1, "Check for a newer version", "Updates", 5, "CheckUpdates", "EnableAlways", 6, opt);
            grp.HasToolbar = true;
            grp.HasMenu = true;
            grp.Activate();

            int docType = (int)swDocumentTypes_e.swDocASSEMBLY;
            var tab = cmdMgr.GetCommandTab(docType, TabTitle);
            if (tab != null) { cmdMgr.RemoveCommandTab(tab); tab = null; }
            tab = cmdMgr.AddCommandTab(docType, TabTitle);
            var box = tab.AddCommandTabBox();
            var ids = new int[idx.Length];
            var txt = new int[idx.Length];
            for (int i = 0; i < idx.Length; i++)
            {
                ids[i] = grp.get_CommandID(idx[i]);
                txt[i] = (int)swCommandTabButtonTextDisplay_e.swCommandTabButton_TextBelow;
            }
            box.AddCommands(ids, txt);
        }

        void RemoveCommands()
        {
            if (cmdMgr == null) return;
            int docType = (int)swDocumentTypes_e.swDocASSEMBLY;
            var tab = cmdMgr.GetCommandTab(docType, TabTitle);
            if (tab != null) cmdMgr.RemoveCommandTab(tab);
            cmdMgr.RemoveCommandGroup2(GroupId, true);
        }

        public int EnableAsm()
        {
            try
            {
                dynamic m = ((dynamic)swApp).ActiveDoc;
                return (m != null && (int)m.GetType() == 2) ? 1 : 0;
            }
            catch { return 0; }
        }

        public int EnableAlways() { return 1; }

        // ------------------------------------------------------------ helpers
        IWin32Window Owner()
        {
            try
            {
                dynamic fr = ((dynamic)swApp).Frame();
                return new Win32Window((IntPtr)(int)fr.GetHWnd());
            }
            catch { return null; }
        }

        void Msg(string text)
        {
            MessageBox.Show(Owner(), text, "Smart Route", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        void Fail(string what, Exception e)
        {
            Log.W(what + " failed: " + e);
            MessageBox.Show(Owner(), what + " failed:\n" + e.Message + "\n\nDetails: " + Log.FilePath, "Smart Route",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        void Status(string text)
        {
            Log.W(text);
            try { ((dynamic)swApp).SetStatusBarText(text); } catch { }
        }

        void WithEngine(Action<bool> next)
        {
            if (engine.Running && engineReady) { next(true); return; }
            engineReady = false;
            string err = engine.Start();
            if (err != null)
            {
                Msg("Could not start the planning engine (Python):\n" + err +
                    "\n\nInstall Python 64-bit + 'pip install pywin32 numpy scipy', or set PythonExe in\n" +
                    System.IO.Path.Combine(Settings.Dir, "settings.json"));
                next(false);
                return;
            }
            busy = true;
            Status("Smart Route: reading the assembly geometry (first time only)...");
            var req = new Dictionary<string, object> { { "cmd", "init" }, { "clearance_mm", cfg.ClearanceMm } };
            if (cfg.CustomMm > 0) req["custom_mm"] = cfg.CustomMm; else req["level"] = cfg.Level;
            engine.Send(req, r =>
            {
                busy = false;
                engineReady = J.Ok(r);
                if (!engineReady) Msg("Engine error: " + J.Err(r));
                else Status("Smart Route ready: " + J.Get(r, "components") + " components, accuracy " + J.Get(r, "accuracy"));
                next(engineReady);
            });
        }

        // ------------------------------------------------------------ Scan
        public void ScanRoutes()
        {
            try
            {
                var rep = new StringBuilder();
                var routes = RoutingReader.ReadRoutes(swApp, rep);
                string path = Path.Combine(Settings.Dir, "scan.txt");
                File.WriteAllText(path, rep.ToString());
                int simple = routes.Count(r => r.Simple);
                Msg("Routes found: " + routes.Count + " (" + simple + " single-chain).\n\nFull report:\n" + path);
            }
            catch (Exception e) { Fail("Scan Routes", e); }
        }

        // ------------------------------------------------------------ Accuracy / watch
        public void ChooseAccuracy()
        {
            try
            {
                using (var dlg = new AccuracyDialog(cfg.Level, cfg.CustomMm))
                {
                    if (dlg.ShowDialog(Owner()) != DialogResult.OK) return;
                    cfg.Level = dlg.Level;
                    cfg.CustomMm = dlg.CustomMm;
                    cfg.Save();
                }
                if (!engine.Running || !engineReady) { Msg("Accuracy saved. It is used when the engine starts."); return; }
                busy = true;
                Status("Smart Route: re-processing stored geometry at the new accuracy...");
                var req = new Dictionary<string, object> { { "cmd", "accuracy" } };
                if (cfg.CustomMm > 0) req["custom_mm"] = cfg.CustomMm; else req["level"] = cfg.Level;
                engine.Send(req, r =>
                {
                    busy = false;
                    if (J.Ok(r)) Msg("Accuracy: " + J.Get(r, "accuracy") + " (cell " + J.D(J.Get(r, "cell_mm")).ToString("0.0") + " mm)");
                    else Msg("Engine error: " + J.Err(r));
                });
            }
            catch (Exception e) { Fail("Accuracy", e); }
        }

        public void ToggleWatch()
        {
            cfg.Watch = !cfg.Watch;
            cfg.Save();
            lastStamp = int.MinValue;
            Msg("Auto Watch is now " + (cfg.Watch ? "ON: after you change the assembly the tool re-reads only what changed and tells you if a better route exists."
                                                   : "OFF."));
        }

        void OnTick(object s, EventArgs e)
        {
            if (engine == null) return;
            engine.Pump();
            if (updateReady) { updateReady = false; checkingUpdates = false; HandleUpdate(); }
            if (updateMsgReady) { updateMsgReady = false; Msg(updateMsg); }
            if (cfg.AutoUpdate && !startupChecked && (DateTime.Now - started).TotalSeconds > 20)
            {
                startupChecked = true;
                if (DateTime.UtcNow.Ticks - cfg.LastUpdateCheck > TimeSpan.FromHours(24).Ticks) UpdateCheck(true);
            }
            if (!cfg.Watch || !engineReady || busy) return;
            try
            {
                dynamic m = ((dynamic)swApp).ActiveDoc;
                if (m == null || (int)m.GetType() != 2) return;
                int st = Convert.ToInt32(m.GetUpdateStamp());
                if (lastStamp == int.MinValue) { lastStamp = st; return; }
                if (st != lastStamp) { lastStamp = st; dirty = true; dirtyAt = DateTime.Now; return; }
                if (dirty && (DateTime.Now - dirtyAt).TotalSeconds > 5)
                {
                    dirty = false;
                    RunReview(true);
                }
            }
            catch (Exception ex) { Log.W("watch: " + ex.Message); }
        }

        // ------------------------------------------------------------ Smart Auto Route
        public void SmartAutoRoute()
        {
            try { DoRoute(); }
            catch (Exception e) { busy = false; Fail("Smart Auto Route", e); }
        }

        double[] ReadSel(object appObj, object smObj, int index, out object comp, out object sk)
        {
            dynamic sm = smObj;
            comp = null;
            sk = null;
            try { comp = sm.GetSelectedObjectsComponent4(index, -1); } catch { }
            try
            {
                dynamic o = sm.GetSelectedObject6(index, -1);
                double x = (double)o.X, y = (double)o.Y, z = (double)o.Z;   // only sketch points have X/Y/Z
                sk = o;
                return RoutingReader.ToAsm(appObj, comp, new[] { x, y, z });
            }
            catch { }
            double[] a = (double[])sm.GetSelectionPoint2(index, -1);
            return new[] { a[0], a[1], a[2] };
        }

        static double D3(double[] a, double[] b)
        {
            double dx = a[0] - b[0], dy = a[1] - b[1], dz = a[2] - b[2];
            return Math.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        void DoRoute()
        {
            if (busy) { Msg("Smart Route is still working on the previous request."); return; }
            dynamic app = swApp;
            dynamic model = app.ActiveDoc;
            if (model == null || (int)model.GetType() != 2)
            {
                Msg("Open the assembly, start/edit the route as usual, select its two end points, then click Smart Auto Route.");
                return;
            }
            dynamic sm = model.SelectionManager;
            if ((int)sm.GetSelectedObjectCount2(-1) < 2)
            {
                Msg("Select the two end points of the route (the connector points, in the route's 3D sketch) first.");
                return;
            }

            var job = new Job { Model = model };
            double[] p0 = ReadSel(swApp, sm, 1, out job.Comp0, out job.Sk0);
            double[] p1 = ReadSel(swApp, sm, 2, out job.Comp1, out job.Sk1);
            job.P0 = p0; job.P1 = p1;

            double mb = RoutingReader.TryReadMinBendRadius(model);
            using (var dlg = new RouteDialog("W" + DateTime.Now.ToString("HHmmss"), cfg.DiaMm,
                       mb > 0 ? mb * 1000 : cfg.BendMm, cfg.ClearanceMm, mb > 0))
            {
                if (dlg.ShowDialog(Owner()) != DialogResult.OK) return;
                cfg.DiaMm = dlg.DiaMm; cfg.BendMm = dlg.BendMm; cfg.ClearanceMm = dlg.ClearanceMm;
                cfg.Save();
                job.Name = dlg.WireName;
                job.DiaMm = dlg.DiaMm; job.BendMm = dlg.BendMm;

                // existing routes are rigid obstacles (except the one being edited)
                var rep = new StringBuilder();
                var rigid = new List<object>();
                foreach (var r in RoutingReader.ReadRoutes(swApp, rep))
                {
                    bool mine = r.Chain.Any(q => D3(q, p0) < 0.003 || D3(q, p1) < 0.003);
                    if (mine) continue;
                    rigid.Add(new Dictionary<string, object> { { "poly", r.Chain }, { "dia", cfg.DiaMm / 1000.0 } });
                }

                double? targetMm = dlg.TargetMm;
                var req = new Dictionary<string, object>
                {
                    { "cmd", "plan" },
                    { "p0", p0 }, { "p1", p1 },
                    { "dia", dlg.DiaMm / 1000.0 },
                    { "k", dlg.BendMm / dlg.DiaMm },
                    { "target", targetMm.HasValue ? (object)(targetMm.Value / 1000.0) : null },
                    { "rigid", rigid },
                    { "clearance_mm", dlg.ClearanceMm }
                };
                WithEngine(ok =>
                {
                    if (!ok) return;
                    busy = true;
                    Status("Smart Route: planning (SOLIDWORKS stays usable)...");
                    engine.Send(req, r => { busy = false; OnPlan(job, r); });
                });
            }
        }

        void OnPlan(Job job, Dictionary<string, object> r)
        {
            try
            {
                if (!J.Ok(r)) { Msg("No route could be planned: " + J.Err(r)); return; }
                var alts = Alt.Parse(r);
                if (alts.Count == 0) { Msg("The engine returned no alternatives."); return; }
                var scene = J.Get(r, "scene") as Dictionary<string, object>;
                var cloud = scene == null ? new List<double[]>() : J.PL(J.Get(scene, "cloud"));
                var boxes = scene == null ? new List<double[]>() : J.PL(J.Get(scene, "boxes"));
                var rigid = new List<List<double[]>>();
                if (scene != null && J.Get(scene, "rigid") != null)
                    foreach (object w in (System.Collections.IEnumerable)J.Get(scene, "rigid")) rigid.Add(J.PL(w));
                string note = J.Get(r, "note") as string;
                Status("Smart Route: " + alts.Count + " alternative(s) ready.");
                using (var dlg = new PreviewForm("Smart Route - " + job.Name + " (" + J.Get(r, "level") + ", cell " +
                                                 J.D(J.Get(r, "cell_mm")).ToString("0.0") + " mm)" +
                                                 (string.IsNullOrEmpty(note) ? "" : "  -  " + note), alts, cloud, boxes, rigid))
                {
                    if (dlg.ShowDialog(Owner()) != DialogResult.OK || dlg.Chosen == null) { Status("Smart Route: cancelled, nothing was changed."); return; }
                    string created = CreateInRouting(job, dlg.Chosen.Pts, dlg.Chosen.Mode == "flexible");
                    VerifyAfter(job, dlg.Chosen, created);
                }
            }
            catch (Exception e) { Fail("Smart Auto Route (apply)", e); }
        }

        static int PointId(object sp)
        {
            dynamic p = sp;
            object o = p.GetID();
            Array arr = o as Array;
            if (arr != null && arr.Length > 0) return Convert.ToInt32(arr.GetValue(arr.GetLowerBound(0)));
            return Convert.ToInt32(o);
        }

        /// <summary>Flexible (smooth curve) mode is looked up by name at run time; falls back to orthogonal.</summary>
        static int ConversionMode(bool flexible, out bool usedFlexible)
        {
            Type t = typeof(swAutoRouteConversionMode_e);
            usedFlexible = false;
            if (flexible)
                foreach (string n in Enum.GetNames(t))
                    if (n.IndexOf("Flexible", StringComparison.OrdinalIgnoreCase) >= 0 ||
                        n.IndexOf("Smooth", StringComparison.OrdinalIgnoreCase) >= 0)
                    { usedFlexible = true; return (int)Enum.Parse(t, n); }
            return (int)swAutoRouteConversionMode_e.swOrthogonalAutoRouteMode;
        }

        /// <summary>
        /// Documented Routing flow: points in the route's 3D sketch -> IAutoRoute.CreateRouteThroughSketchEntities.
        /// If anything fails the points stay in the sketch, so the normal Auto Route can be run through them.
        /// </summary>
        string CreateInRouting(Job job, List<double[]> pts, bool flexible)
        {
            dynamic model = job.Model;
            var ids = new List<int>();
            var types = new List<int>();
            try
            {
                dynamic skm = model.SketchManager;
                object comp = job.Comp0 ?? job.Comp1;
                for (int i = 0; i < pts.Count; i++)
                {
                    int id;
                    if (i == 0 && job.Sk0 != null) id = PointId(job.Sk0);
                    else if (i == pts.Count - 1 && job.Sk1 != null) id = PointId(job.Sk1);
                    else
                    {
                        double[] q = RoutingReader.FromAsm(swApp, comp, pts[i]);
                        dynamic sp = skm.CreatePoint(q[0], q[1], q[2]);
                        if (sp == null)
                            return "Could not add sketch points. Edit the route's 3D sketch (Edit Route) and run Smart Auto Route again.";
                        id = PointId(sp);
                    }
                    ids.Add(id);
                    types.Add((int)swAutoRouteSketchEntitiesTypes_e.swAutoRouteSketchEntitiesType_Point);
                }
            }
            catch (Exception e)
            {
                Log.W("sketch points: " + e);
                return "Could not add sketch points: " + e.Message;
            }

            try
            {
                bool usedFlex;
                int mode = ConversionMode(flexible, out usedFlex);
                dynamic rm = model.GetRouteManager();
                dynamic ar = rm.GetAutoRoute();
                int status = (int)ar.CreateRouteThroughSketchEntities(mode,
                    (int)swAutoRouteAutoTangencyMode_e.swAutoTangencyMode_ON, types.ToArray(), ids.ToArray());
                return "Route created through " + pts.Count + " points, " + (usedFlex ? "flexible (smooth)" : "orthogonal") +
                       " mode" + (flexible && !usedFlex ? " (flexible mode not found in this version)" : "") +
                       " (Routing status code " + status + "). Ctrl+Z undoes it.";
            }
            catch (Exception e)
            {
                Log.W("CreateRouteThroughSketchEntities: " + e);
                return "The " + pts.Count + " path points are now in the route's 3D sketch, but the automatic route call failed (" +
                       e.Message + "). Run the normal Auto Route through these points.";
            }
        }

        // ------------------------------------------------------------ verification after creation
        static string Mm(double v) { return (v * 1000).ToString("0.0"); }

        void VerifyAfter(Job job, Alt alt, string createMsg)
        {
            var sb = new StringBuilder(createMsg);
            sb.AppendLine();
            sb.AppendLine();
            try
            {
                var rep = new StringBuilder();
                RouteInfo mine = null;
                var others = new List<object>();
                foreach (var r in RoutingReader.ReadRoutes(swApp, rep))
                {
                    if (r.Chain.Count < 2) continue;
                    double[] a = r.Chain[0], b = r.Chain[r.Chain.Count - 1];
                    bool m = (D3(a, job.P0) < 0.003 && D3(b, job.P1) < 0.003) || (D3(a, job.P1) < 0.003 && D3(b, job.P0) < 0.003);
                    if (m && mine == null) mine = r;
                    else if (!m) others.Add(new Dictionary<string, object> { { "poly", r.Chain }, { "dia", cfg.DiaMm / 1000.0 } });
                }
                string owner = mine == null ? null : mine.Name.Split('/')[0];
                if (mine == null)
                {
                    sb.AppendLine("Verification: the new route could not be read back (run Scan Routes). Planned path: " + alt.Summary().Replace("\n", " "));
                    if (cfg.SwInterference) sb.AppendLine(SwInterference(job.Model, null));
                    Msg(sb.ToString());
                    return;
                }
                var req = new Dictionary<string, object>
                {
                    { "cmd", "verify" }, { "poly", mine.Chain }, { "dia", job.DiaMm / 1000.0 }, { "k", job.BendMm / job.DiaMm },
                    { "rigid", others }, { "clearance_mm", cfg.ClearanceMm }
                };
                busy = true;
                Status("Smart Route: verifying the created route...");
                engine.Send(req, r =>
                {
                    busy = false;
                    try
                    {
                        if (!J.Ok(r)) sb.AppendLine("Verification failed: " + J.Err(r));
                        else
                        {
                            var c = J.Get(r, "check") as Dictionary<string, object>;
                            double need = J.D(J.Get(c, "radius_required"));
                            object mr = J.Get(c, "min_radius"), mc = J.Get(c, "min_clearance");
                            var bad = J.Objs(J.Get(c, "bend_violations"));
                            var col = J.Objs(J.Get(c, "collisions"));
                            var tight = J.Objs(J.Get(c, "tight"));
                            sb.AppendLine("VERIFICATION of the created route (" + mine.Name + "):");
                            sb.AppendLine("  length " + Mm(J.D(J.Get(c, "length"))) + " mm");
                            sb.AppendLine("  min bend radius " + (mr == null ? "n/a" : Mm(J.D(mr)) + " mm") + " (need " + Mm(need) + ") -> " +
                                          (bad.Count == 0 ? "OK" : bad.Count + " problem spot(s)"));
                            sb.AppendLine("  min clearance to real geometry " + (mc == null ? "n/a" : Mm(J.D(mc)) + " mm") + " -> " +
                                          (col.Count == 0 ? (tight.Count == 0 ? "OK" : tight.Count + " tight spot(s)") : col.Count + " COLLISION(S)"));
                            foreach (var b in bad)
                            {
                                double[] at = J.P(J.Get(b, "at"));
                                sb.AppendLine("    bend at (" + Mm(at[0]) + ", " + Mm(at[1]) + ", " + Mm(at[2]) + ") mm: radius " + Mm(J.D(J.Get(b, "radius"))) + " mm");
                            }
                            foreach (var b in col)
                            {
                                double[] at = J.P(J.Get(b, "at"));
                                sb.AppendLine("    collision at (" + Mm(at[0]) + ", " + Mm(at[1]) + ", " + Mm(at[2]) + ") mm");
                            }
                        }
                        if (cfg.SwInterference) sb.AppendLine(SwInterference(job.Model, owner));
                    }
                    catch (Exception ex) { sb.AppendLine("Verification error: " + ex.Message); }
                    Msg(sb.ToString());
                });
            }
            catch (Exception e)
            {
                Log.W("VerifyAfter: " + e);
                Msg(sb + "Verification could not run: " + e.Message);
            }
        }

        string SwInterference(object modelObj, string owner)
        {
            try
            {
                dynamic asm = modelObj;
                dynamic mgr = asm.InterferenceDetectionManager;
                if (mgr == null) return "SOLIDWORKS interference check: not available.";
                try { mgr.TreatCoincidenceAsInterference = false; } catch { }
                try { mgr.IncludeMultibodyPartInterferences = true; } catch { }
                try { mgr.TreatSubAssembliesAsComponents = false; } catch { }
                object[] arr = mgr.GetInterferences() as object[];
                int total = arr == null ? 0 : arr.Length, mine = 0;
                if (arr != null)
                    foreach (object it in arr)
                    {
                        try
                        {
                            dynamic itf = it;
                            object[] cs = itf.Components as object[];
                            if (cs == null) continue;
                            foreach (object c in cs)
                            {
                                string n = (string)((dynamic)c).Name2;
                                if (owner == null || n.Contains(owner)) { mine++; break; }
                            }
                        }
                        catch { }
                    }
                try { mgr.Done(); } catch { }
                return "SOLIDWORKS interference check: " + total + " interference(s) in the assembly" +
                       (owner == null ? "." : ", " + mine + " involving the new route.");
            }
            catch (Exception e)
            {
                Log.W("SwInterference: " + e.Message);
                return "SOLIDWORKS interference check could not run (" + e.Message + ").";
            }
        }

        // ------------------------------------------------------------ updates
        public void CheckUpdates()
        {
            try { UpdateCheck(false); }
            catch (Exception e) { Fail("Updates", e); }
        }

        void UpdateCheck(bool silent)
        {
            if (checkingUpdates) return;
            checkingUpdates = true;
            updateManual = !silent;
            Status("Smart Route: checking for updates...");
            Updater.Check((info, err) => { pendingUpdate = info; updateError = err; updateReady = true; });
        }

        void HandleUpdate()
        {
            cfg.LastUpdateCheck = DateTime.UtcNow.Ticks;
            cfg.Save();
            if (pendingUpdate != null)
            {
                string notes = pendingUpdate.Notes ?? "";
                if (notes.Length > 600) notes = notes.Substring(0, 600) + "...";
                var res = MessageBox.Show(Owner(),
                    "Smart Route " + pendingUpdate.Version + " is available (installed: " + AppInfo.Version + ").\n\n" + notes +
                    "\n\nDownload it now and install it automatically when SOLIDWORKS is closed?",
                    "Smart Route update", MessageBoxButtons.YesNo, MessageBoxIcon.Information);
                if (res == DialogResult.Yes)
                    Updater.DownloadAndInstallOnExit(pendingUpdate, err =>
                    {
                        updateMsg = err == null ? "Update downloaded. It will be installed when you close SOLIDWORKS."
                                                : "Update download failed: " + err;
                        updateMsgReady = true;
                    });
            }
            else if (updateManual)
                Msg(updateError != null ? "Could not check for updates: " + updateError
                                        : "You have the latest version (" + AppInfo.Version + ").");
        }

        // ------------------------------------------------------------ Review
        public void ReviewRoutes()
        {
            try { RunReview(false); }
            catch (Exception e) { busy = false; Fail("Review Routes", e); }
        }

        void RunReview(bool quiet)
        {
            if (busy) return;
            var rep = new StringBuilder();
            var routes = RoutingReader.ReadRoutes(swApp, rep).Where(r => r.Simple && r.Chain.Count >= 2).ToList();
            if (routes.Count == 0)
            {
                if (!quiet) Msg("No single-chain routes found to review (see Scan Routes).");
                return;
            }
            var list = new List<object>();
            foreach (var r in routes)
                list.Add(new Dictionary<string, object>
                {
                    { "name", r.Name },
                    { "p0", r.Chain[0] }, { "p1", r.Chain[r.Chain.Count - 1] },
                    { "poly", r.Chain },
                    { "dia", cfg.DiaMm / 1000.0 },
                    { "k", cfg.BendMm / cfg.DiaMm }
                });
            var req = new Dictionary<string, object> { { "cmd", "review" }, { "routes", list }, { "clearance_mm", cfg.ClearanceMm } };
            WithEngine(ok =>
            {
                if (!ok) return;
                busy = true;
                Status("Smart Route: reviewing " + routes.Count + " route(s)...");
                engine.Send(req, r => { busy = false; OnReview(r, quiet); });
            });
        }

        void OnReview(Dictionary<string, object> r, bool quiet)
        {
            try
            {
                if (!J.Ok(r)) { if (!quiet) Msg("Review failed: " + J.Err(r)); return; }
                var sugg = new List<Suggestion>();
                foreach (var x in J.Objs(J.Get(r, "results")))
                {
                    object flag = J.Get(x, "suggest");
                    if (!(flag is bool) || !(bool)flag) continue;
                    sugg.Add(new Suggestion
                    {
                        Name = (string)J.Get(x, "name"),
                        Current = J.D(J.Get(x, "current")),
                        Best = J.D(J.Get(x, "best")),
                        Poly = J.PL(J.Get(x, "poly"))
                    });
                }
                if (sugg.Count == 0)
                {
                    Status("Smart Route: no better route found.");
                    if (!quiet) Msg("No better route found - the existing routes look good.");
                    return;
                }
                Status("Smart Route: " + sugg.Count + " better route(s) found.");
                new SuggestForm(sugg, DrawSuggestion).Show(Owner());
            }
            catch (Exception e) { Fail("Review (result)", e); }
        }

        void DrawSuggestion(Suggestion s)
        {
            try
            {
                dynamic model = ((dynamic)swApp).ActiveDoc;
                dynamic skm = model.SketchManager;
                skm.Insert3DSketch(true);
                for (int i = 1; i < s.Poly.Count; i++)
                {
                    double[] a = s.Poly[i - 1], b = s.Poly[i];
                    skm.CreateLine(a[0], a[1], a[2], b[0], b[1], b[2]);
                }
                skm.Insert3DSketch(true);
                try
                {
                    string nm = new string(s.Name.Select(c => char.IsLetterOrDigit(c) ? c : '_').ToArray());
                    model.FeatureByPositionReverse(0).Name = "SmartRoute_Suggest_" + nm;
                }
                catch { }
                Msg("Suggested path drawn as a 3D sketch in the assembly. Compare it with the current route, then re-route if you like it.");
            }
            catch (Exception e) { Fail("Draw suggestion", e); }
        }
    }
}
