using System;
using System.Collections.Generic;
using System.Text;

namespace SmartRoute
{
    public class RouteInfo
    {
        public string Name = "";                       // "<route sub-assembly>/<3D sketch>"
        public List<List<double[]>> Segments = new List<List<double[]>>();
        public List<double[]> Chain = new List<double[]>();   // joined centre-line (assembly coords, metres)
        public bool Simple;                            // true = one unbranched chain
        public double Length;
    }

    /// <summary>Reads the routes that already exist in the active assembly (everything via late binding).</summary>
    public static class RoutingReader
    {
        public static double[] ToAsm(object app, object comp, double[] p)
        {
            if (comp == null) return p;
            try
            {
                dynamic a = app;
                dynamic c = comp;
                dynamic tf = c.Transform2;
                if (tf == null) return p;
                dynamic mu = a.GetMathUtility();
                dynamic mp = mu.CreatePoint(p);
                dynamic r = mp.MultiplyTransform(tf);
                double[] arr = (double[])r.ArrayData;
                return new[] { arr[0], arr[1], arr[2] };
            }
            catch (Exception e) { Log.W("ToAsm: " + e.Message); return p; }
        }

        public static double[] FromAsm(object app, object comp, double[] p)
        {
            if (comp == null) return p;
            try
            {
                dynamic a = app;
                dynamic c = comp;
                dynamic tf = c.Transform2;
                if (tf == null) return p;
                dynamic inv = tf.Inverse();
                dynamic mu = a.GetMathUtility();
                dynamic mp = mu.CreatePoint(p);
                dynamic r = mp.MultiplyTransform(inv);
                double[] arr = (double[])r.ArrayData;
                return new[] { arr[0], arr[1], arr[2] };
            }
            catch (Exception e) { Log.W("FromAsm: " + e.Message); return p; }
        }

        public static List<RouteInfo> ReadRoutes(object appObj, StringBuilder rep)
        {
            dynamic app = appObj;
            var result = new List<RouteInfo>();
            dynamic model = app.ActiveDoc;
            if (model == null || (int)model.GetType() != 2)
            {
                rep.AppendLine("No active assembly.");
                return result;
            }

            object compsObj = null;
            try { compsObj = model.GetComponents(false); } catch (Exception e) { rep.AppendLine("GetComponents failed: " + e.Message); }
            object[] comps = compsObj as object[];
            if (comps == null) { rep.AppendLine("No components."); return result; }

            int asmCount = 0;
            foreach (object co in comps)
            {
                dynamic comp = co;
                dynamic cdoc = null;
                try { cdoc = comp.GetModelDoc2(); } catch { }
                if (cdoc == null) continue;
                int dt = 0;
                try { dt = (int)cdoc.GetType(); } catch { }
                if (dt != 2) continue;                       // route sub-assemblies are assemblies
                asmCount++;

                string compName = "";
                try { compName = (string)comp.Name2; } catch { }

                bool hasRoute = false;
                var sketches = new List<object>();
                dynamic f = null;
                try { f = cdoc.FirstFeature(); } catch { }
                while (f != null)
                {
                    string tn = "", fn = "";
                    try { tn = (string)f.GetTypeName2(); fn = (string)f.Name; } catch { }
                    if (tn.IndexOf("route", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        hasRoute = true;
                        rep.AppendLine("  [" + compName + "] route feature '" + fn + "' type '" + tn + "'");
                    }
                    if (tn.IndexOf("3DProfile", StringComparison.OrdinalIgnoreCase) >= 0 ||
                        tn.IndexOf("3DSketch", StringComparison.OrdinalIgnoreCase) >= 0)
                        sketches.Add((object)f);
                    try { f = f.GetNextFeature(); } catch { f = null; }
                }
                if (!hasRoute) continue;

                foreach (object so in sketches)
                {
                    dynamic sf = so;
                    string sname = "";
                    try { sname = (string)sf.Name; } catch { }
                    var ri = new RouteInfo { Name = compName + "/" + sname };
                    try { ReadSketch(app, comp, sf, ri, rep); }
                    catch (Exception e) { rep.AppendLine("  sketch read failed: " + e.Message); }
                    if (ri.Segments.Count == 0) continue;
                    BuildChain(ri);
                    rep.AppendLine("  -> " + ri.Name + ": " + ri.Segments.Count + " segment(s), " +
                                   (ri.Simple ? "single chain" : "branched/other") + ", length " +
                                   (ri.Length * 1000).ToString("0.0") + " mm");
                    result.Add(ri);
                }
            }
            rep.AppendLine("Assemblies scanned: " + asmCount + ", routes found: " + result.Count);
            return result;
        }

        static void ReadSketch(object app, object comp, dynamic feat, RouteInfo ri, StringBuilder rep)
        {
            dynamic sk = feat.GetSpecificFeature2();
            if (sk == null) return;
            object so = sk.GetSketchSegments();
            object[] segs = so as object[];
            if (segs == null) return;
            foreach (object s in segs)
            {
                List<double[]> pl = null;
                try { pl = SampleSegment((dynamic)s); }
                catch (Exception e) { rep.AppendLine("  segment skipped: " + e.Message); }
                if (pl == null || pl.Count < 2) continue;
                for (int i = 0; i < pl.Count; i++) pl[i] = ToAsm(app, comp, pl[i]);
                ri.Segments.Add(pl);
            }
        }

        static List<double[]> SampleSegment(dynamic seg)
        {
            int t = (int)seg.GetType();                      // 0 line, 1 arc, 2 ellipse, 3 spline
            dynamic curve = null;
            try { curve = seg.GetCurve(); } catch { }
            if (curve != null)
            {
                double s0, s1;
                bool closed, periodic;
                curve.GetEndParams(out s0, out s1, out closed, out periodic);
                int n = (t == 0) ? 1 : 24;
                var pts = new List<double[]>();
                for (int i = 0; i <= n; i++)
                {
                    double u = s0 + (s1 - s0) * i / n;
                    double[] a = (double[])curve.Evaluate2(u, 0);
                    pts.Add(new[] { a[0], a[1], a[2] });
                }
                return pts;
            }
            dynamic sp = seg.GetStartPoint2();
            dynamic ep = seg.GetEndPoint2();
            return new List<double[]>
            {
                new[] { (double)sp.X, (double)sp.Y, (double)sp.Z },
                new[] { (double)ep.X, (double)ep.Y, (double)ep.Z }
            };
        }

        static double Dist(double[] a, double[] b)
        {
            double dx = a[0] - b[0], dy = a[1] - b[1], dz = a[2] - b[2];
            return Math.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        static void BuildChain(RouteInfo ri)
        {
            const double tol = 1e-4;
            var left = new List<List<double[]>>();
            foreach (var s in ri.Segments) left.Add(new List<double[]>(s));
            var chain = new List<double[]>(left[0]);
            left.RemoveAt(0);
            bool grew = true;
            while (grew && left.Count > 0)
            {
                grew = false;
                for (int i = 0; i < left.Count; i++)
                {
                    var s = left[i];
                    double[] head = chain[0], tail = chain[chain.Count - 1];
                    if (Dist(tail, s[0]) < tol) { chain.AddRange(s.GetRange(1, s.Count - 1)); }
                    else if (Dist(tail, s[s.Count - 1]) < tol) { s.Reverse(); chain.AddRange(s.GetRange(1, s.Count - 1)); }
                    else if (Dist(head, s[s.Count - 1]) < tol) { chain.InsertRange(0, s.GetRange(0, s.Count - 1)); }
                    else if (Dist(head, s[0]) < tol) { s.Reverse(); chain.InsertRange(0, s.GetRange(0, s.Count - 1)); }
                    else continue;
                    left.RemoveAt(i);
                    grew = true;
                    break;
                }
            }
            ri.Chain = chain;
            ri.Simple = left.Count == 0;
            double len = 0;
            for (int i = 1; i < chain.Count; i++) len += Dist(chain[i - 1], chain[i]);
            ri.Length = len;
        }

        /// <summary>Bend-radius settings of the route being edited (needs a route segment selected). Metres or -1.</summary>
        public static double TryReadMinBendRadius(object modelObj)
        {
            try
            {
                dynamic model = modelObj;
                dynamic rm = model.GetRouteManager();
                dynamic rp = rm.GetRouteProperty();
                if (rp == null) return -1;
                double r = (double)rp.MinimumBendRadius;
                return r > 0 ? r : -1;
            }
            catch { return -1; }
        }
    }
}
