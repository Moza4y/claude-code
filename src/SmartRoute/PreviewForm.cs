using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Linq;
using System.Windows.Forms;

namespace SmartRoute
{
    public class Alt
    {
        public string Label, Mode;                       // Mode: "flexible" | "orthogonal"
        public List<double[]> Pts = new List<double[]>(), Poly = new List<double[]>();
        public double Length, RadiusRequired;
        public double? MinRadius, MinClearance;
        public int PlannerProblems, BendViolations, Collisions, Tight;

        public bool HasIssues { get { return Collisions > 0 || BendViolations > 0 || PlannerProblems > 0; } }

        public static List<Alt> Parse(Dictionary<string, object> r)
        {
            var res = new List<Alt>();
            foreach (var a in J.Objs(J.Get(r, "alternatives")))
            {
                var alt = new Alt
                {
                    Label = (string)J.Get(a, "label"),
                    Mode = (string)J.Get(a, "mode"),
                    Pts = J.PL(J.Get(a, "pts")),
                    Poly = J.PL(J.Get(a, "poly")),
                    Length = J.D(J.Get(a, "length")),
                    PlannerProblems = J.Objs(J.Get(a, "problems")).Count
                };
                var c = J.Get(a, "check") as Dictionary<string, object>;
                if (c != null)
                {
                    alt.RadiusRequired = J.D(J.Get(c, "radius_required"));
                    if (J.Get(c, "min_radius") != null) alt.MinRadius = J.D(J.Get(c, "min_radius"));
                    if (J.Get(c, "min_clearance") != null) alt.MinClearance = J.D(J.Get(c, "min_clearance"));
                    alt.BendViolations = J.Objs(J.Get(c, "bend_violations")).Count;
                    alt.Collisions = J.Objs(J.Get(c, "collisions")).Count;
                    alt.Tight = J.Objs(J.Get(c, "tight")).Count;
                }
                res.Add(alt);
            }
            return res;
        }

        public string Summary()
        {
            string clr = MinClearance.HasValue ? (MinClearance.Value * 1000).ToString("0.0") + " mm" : "n/a";
            string rad = MinRadius.HasValue ? (MinRadius.Value * 1000).ToString("0") + " mm" : "n/a";
            return "Length " + (Length * 1000).ToString("0.0") + " mm   |   bends " + Math.Max(0, Pts.Count - 2) +
                   "   |   min bend radius " + rad + " (need " + (RadiusRequired * 1000).ToString("0") + ")" +
                   "\nmin clearance " + clr + "   |   collisions " + Collisions + "   |   tight spots " + Tight +
                   "   |   bend problems " + (BendViolations + PlannerProblems);
        }
    }

    /// <summary>Tiny wireframe viewer: drag = orbit, wheel = zoom, right-drag = pan, double-click = reset.</summary>
    public class Viewer3D : Control
    {
        public List<double[]> Cloud = new List<double[]>();
        public List<double[]> Boxes = new List<double[]>();
        public List<List<double[]>> Rigid = new List<List<double[]>>();
        public List<Alt> Alts = new List<Alt>();
        public int Selected;

        double yaw = 0.6, pitch = 0.45, zoom = 1.0, panX, panY;
        double[] c = { 0, 0, 0 };
        double diag = 1;
        Point last;
        static readonly Color[] Colors = { Color.FromArgb(0, 120, 215), Color.FromArgb(16, 137, 62), Color.FromArgb(200, 120, 0), Color.FromArgb(142, 68, 173) };

        public Viewer3D()
        {
            DoubleBuffered = true;
            BackColor = Color.White;
        }

        public void Fit()
        {
            var all = new List<double[]>();
            foreach (var a in Alts) all.AddRange(a.Poly);
            if (all.Count == 0) return;
            double[] lo = { 1e9, 1e9, 1e9 }, hi = { -1e9, -1e9, -1e9 };
            foreach (var p in all) for (int i = 0; i < 3; i++) { lo[i] = Math.Min(lo[i], p[i]); hi[i] = Math.Max(hi[i], p[i]); }
            for (int i = 0; i < 3; i++) c[i] = (lo[i] + hi[i]) / 2;
            diag = Math.Max(1e-3, Math.Sqrt(Math.Pow(hi[0] - lo[0], 2) + Math.Pow(hi[1] - lo[1], 2) + Math.Pow(hi[2] - lo[2], 2)));
            zoom = 1; panX = panY = 0;
            Invalidate();
        }

        PointF P(double[] p)
        {
            double x = p[0] - c[0], y = p[1] - c[1], z = p[2] - c[2];
            double cy = Math.Cos(yaw), sy = Math.Sin(yaw), cp = Math.Cos(pitch), sp = Math.Sin(pitch);
            double x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
            double y2 = y * cp - z1 * sp;
            double scale = Math.Min(Width, Height) / (diag * 1.35) * zoom;
            return new PointF((float)(Width / 2.0 + x1 * scale + panX), (float)(Height / 2.0 - y2 * scale + panY));
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(BackColor);
            foreach (var p in Cloud)
            {
                var q = P(p);
                g.FillRectangle(Brushes.LightGray, q.X, q.Y, 1.6f, 1.6f);
            }
            using (var pen = new Pen(Color.FromArgb(200, 200, 200)))
                foreach (var b in Boxes) DrawBox(g, pen, b);
            using (var pen = new Pen(Color.DimGray, 2f))
                foreach (var w in Rigid) DrawLine(g, pen, w);
            for (int i = 0; i < Alts.Count; i++)
            {
                if (i == Selected) continue;
                using (var pen = new Pen(Color.FromArgb(140, Colors[i % Colors.Length]), 1.5f) { DashStyle = DashStyle.Dash })
                    DrawLine(g, pen, Alts[i].Poly);
            }
            if (Selected >= 0 && Selected < Alts.Count)
            {
                var a = Alts[Selected];
                using (var pen = new Pen(Colors[Selected % Colors.Length], 3.5f)) DrawLine(g, pen, a.Poly);
                if (a.Poly.Count > 1)
                {
                    var s = P(a.Poly[0]); var t = P(a.Poly[a.Poly.Count - 1]);
                    g.FillEllipse(Brushes.Green, s.X - 5, s.Y - 5, 10, 10);
                    g.FillEllipse(Brushes.Red, t.X - 5, t.Y - 5, 10, 10);
                }
            }
            g.DrawRectangle(Pens.Gray, 0, 0, Width - 1, Height - 1);
            g.DrawString("drag: rotate   wheel: zoom   right-drag: pan   double-click: reset", Font, Brushes.Gray, 6, Height - 20);
        }

        void DrawLine(Graphics g, Pen pen, List<double[]> pl)
        {
            for (int i = 1; i < pl.Count; i++) g.DrawLine(pen, P(pl[i - 1]), P(pl[i]));
        }

        void DrawBox(Graphics g, Pen pen, double[] b)
        {
            var v = new double[8][];
            for (int i = 0; i < 8; i++)
                v[i] = new[] { (i & 1) == 0 ? b[0] : b[3], (i & 2) == 0 ? b[1] : b[4], (i & 4) == 0 ? b[2] : b[5] };
            int[,] edges = { { 0, 1 }, { 2, 3 }, { 4, 5 }, { 6, 7 }, { 0, 2 }, { 1, 3 }, { 4, 6 }, { 5, 7 }, { 0, 4 }, { 1, 5 }, { 2, 6 }, { 3, 7 } };
            for (int k = 0; k < 12; k++) g.DrawLine(pen, P(v[edges[k, 0]]), P(v[edges[k, 1]]));
        }

        protected override void OnMouseDown(MouseEventArgs e) { last = e.Location; base.OnMouseDown(e); }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left)
            {
                yaw += (e.X - last.X) * 0.01;
                pitch = Math.Max(-1.5, Math.Min(1.5, pitch + (e.Y - last.Y) * 0.01));
                Invalidate();
            }
            else if (e.Button == MouseButtons.Right)
            {
                panX += e.X - last.X; panY += e.Y - last.Y;
                Invalidate();
            }
            last = e.Location;
            base.OnMouseMove(e);
        }

        protected override void OnMouseWheel(MouseEventArgs e)
        {
            zoom = Math.Max(0.2, Math.Min(20, zoom * Math.Pow(1.1, e.Delta / 120.0)));
            Invalidate();
            base.OnMouseWheel(e);
        }

        protected override void OnMouseDoubleClick(MouseEventArgs e) { Fit(); base.OnMouseDoubleClick(e); }
    }

    /// <summary>Preview of the alternatives; nothing is created in SOLIDWORKS until "Create route".</summary>
    public class PreviewForm : Form
    {
        readonly Viewer3D view = new Viewer3D();
        readonly ListView list = new ListView();
        readonly Label details = new Label();
        readonly List<Alt> alts;
        public Alt Chosen;

        public PreviewForm(string title, List<Alt> alternatives, List<double[]> cloud, List<double[]> boxes, List<List<double[]>> rigid)
        {
            alts = alternatives;
            Text = title;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(940, 600);
            MinimizeBox = false;

            view.Left = 10; view.Top = 10; view.Width = 610; view.Height = 520;
            view.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Bottom | AnchorStyles.Right;
            view.Cloud = cloud; view.Boxes = boxes; view.Rigid = rigid; view.Alts = alts;
            Controls.Add(view);

            list.Left = 630; list.Top = 10; list.Width = 300; list.Height = 220;
            list.View = View.Details; list.FullRowSelect = true; list.MultiSelect = false; list.HideSelection = false;
            list.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            list.Columns.Add("Alternative", 140); list.Columns.Add("Length", 70); list.Columns.Add("Status", 80);
            foreach (var a in alts)
            {
                var it = new ListViewItem(a.Label);
                it.SubItems.Add((a.Length * 1000).ToString("0") + " mm");
                it.SubItems.Add(a.HasIssues ? "check!" : "OK");
                if (a.HasIssues) it.ForeColor = Color.Firebrick;
                list.Items.Add(it);
            }
            list.SelectedIndexChanged += (s, e) => ShowSelected();
            Controls.Add(list);

            details.Left = 630; details.Top = 240; details.Width = 300; details.Height = 190;
            details.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            Controls.Add(details);

            var ok = new Button { Text = "Create route", Left = 630, Top = 545, Width = 140, Height = 32, Anchor = AnchorStyles.Bottom | AnchorStyles.Right };
            var cancel = new Button { Text = "Cancel", Left = 780, Top = 545, Width = 150, Height = 32, Anchor = AnchorStyles.Bottom | AnchorStyles.Right, DialogResult = DialogResult.Cancel };
            ok.Click += (s, e) =>
            {
                int i = list.SelectedIndices.Count > 0 ? list.SelectedIndices[0] : 0;
                var a = alts[i];
                if (a.HasIssues &&
                    MessageBox.Show(this, "This alternative has collisions or bend problems:\n\n" + a.Summary() + "\n\nCreate it anyway?",
                        "Smart Route", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
                Chosen = a;
                DialogResult = DialogResult.OK;
            };
            Controls.Add(ok); Controls.Add(cancel);
            AcceptButton = ok; CancelButton = cancel;

            Shown += (s, e) => { view.Fit(); if (list.Items.Count > 0) list.Items[0].Selected = true; };
        }

        void ShowSelected()
        {
            if (list.SelectedIndices.Count == 0) return;
            int i = list.SelectedIndices[0];
            view.Selected = i;
            var a = alts[i];
            details.ForeColor = a.HasIssues ? Color.Firebrick : Color.Black;
            details.Text = a.Label + (a.Mode == "flexible" ? "  (smooth curve route)" : "  (orthogonal route)") + "\n\n" + a.Summary() +
                           "\n\nGreen dot = start, red dot = end. Dashed = the other alternatives. Grey dots/boxes = the real geometry nearby.";
            view.Invalidate();
        }
    }
}
