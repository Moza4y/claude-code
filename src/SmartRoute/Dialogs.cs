using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.Windows.Forms;

namespace SmartRoute
{
    static class UI
    {
        public static Label L(string t, int x, int y) { return new Label { Text = t, Left = x, Top = y + 3, Width = 190, AutoSize = false }; }
        public static TextBox T(string v, int x, int y, int w) { return new TextBox { Text = v, Left = x, Top = y, Width = w }; }

        public static bool Num(string s, out double v)
        {
            return double.TryParse(s.Trim().Replace(',', '.'), NumberStyles.Float, CultureInfo.InvariantCulture, out v);
        }

        public static string F(double v) { return v.ToString("0.###", CultureInfo.InvariantCulture); }
    }

    /// <summary>Wire parameters for one Smart Auto Route.</summary>
    public class RouteDialog : Form
    {
        TextBox name, dia, bend, len, clr;
        public string WireName;
        public double DiaMm, BendMm, ClearanceMm;
        public double? TargetMm;

        public RouteDialog(string defName, double diaMm, double bendMm, double clrMm, bool bendFromRoute)
        {
            Text = "Smart Auto Route";
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false; MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(380, 215);
            int y = 14;
            Controls.Add(UI.L("Wire name", 12, y)); name = UI.T(defName, 210, y, 150); Controls.Add(name); y += 30;
            Controls.Add(UI.L("Cable diameter (mm)", 12, y)); dia = UI.T(UI.F(diaMm), 210, y, 150); Controls.Add(dia); y += 30;
            Controls.Add(UI.L(bendFromRoute ? "Min bend radius (mm) - from route" : "Min bend radius (mm)", 12, y)); bend = UI.T(UI.F(bendMm), 210, y, 150); Controls.Add(bend); y += 30;
            Controls.Add(UI.L("Wanted length (mm) - empty = shortest", 12, y)); len = UI.T("", 210, y, 150); Controls.Add(len); y += 30;
            Controls.Add(UI.L("Safety clearance (mm)", 12, y)); clr = UI.T(UI.F(clrMm), 210, y, 150); Controls.Add(clr); y += 38;
            var ok = new Button { Text = "Route", Left = 210, Top = y, Width = 70, DialogResult = DialogResult.None };
            var cancel = new Button { Text = "Cancel", Left = 290, Top = y, Width = 70, DialogResult = DialogResult.Cancel };
            ok.Click += OnOk;
            Controls.Add(ok); Controls.Add(cancel);
            AcceptButton = ok; CancelButton = cancel;
        }

        void OnOk(object s, EventArgs e)
        {
            double d, b, c, t;
            if (!UI.Num(dia.Text, out d) || d <= 0 || !UI.Num(bend.Text, out b) || b <= 0 || !UI.Num(clr.Text, out c) || c < 0)
            { MessageBox.Show(this, "Diameter, bend radius and clearance must be numbers (diameter/bend > 0).", "Smart Route"); return; }
            TargetMm = null;
            if (len.Text.Trim().Length > 0)
            {
                if (!UI.Num(len.Text, out t) || t <= 0) { MessageBox.Show(this, "Wanted length must be a number.", "Smart Route"); return; }
                TargetMm = t;
            }
            WireName = name.Text.Trim().Length > 0 ? name.Text.Trim() : "W";
            DiaMm = d; BendMm = b; ClearanceMm = c;
            DialogResult = DialogResult.OK;
        }
    }

    public class AccuracyDialog : Form
    {
        ComboBox box; TextBox custom;
        public int Level = 3;
        public double CustomMm = 0;

        public AccuracyDialog(int level, double customMm)
        {
            Text = "Smart Route - accuracy";
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false; MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(380, 150);
            Controls.Add(UI.L("Accuracy level", 12, 14));
            box = new ComboBox { Left = 150, Top = 14, Width = 215, DropDownStyle = ComboBoxStyle.DropDownList };
            box.Items.AddRange(new object[] {
                "1 - Draft  (cell 20 mm)", "2 - Fast  (cell 10 mm)", "3 - Normal  (cell 5 mm)",
                "4 - Fine  (cell 2.5 mm)", "5 - Ultra  (cell 1.5 mm)" });
            box.SelectedIndex = Math.Max(0, Math.Min(4, level - 1));
            Controls.Add(box);
            Controls.Add(UI.L("or custom cell size (mm)", 12, 48));
            custom = UI.T(customMm > 0 ? UI.F(customMm) : "", 150, 48, 215);
            Controls.Add(custom);
            Controls.Add(new Label { Text = "Higher = slower but more exact. Stored geometry is re-processed, not re-read from SOLIDWORKS.", Left = 12, Top = 80, Width = 355, Height = 30 });
            var ok = new Button { Text = "OK", Left = 210, Top = 115, Width = 70 };
            var cancel = new Button { Text = "Cancel", Left = 290, Top = 115, Width = 70, DialogResult = DialogResult.Cancel };
            ok.Click += (s, e) =>
            {
                double v = 0;
                if (custom.Text.Trim().Length > 0 && (!UI.Num(custom.Text, out v) || v < 0.5 || v > 100))
                { MessageBox.Show(this, "Custom cell size must be between 0.5 and 100 mm.", "Smart Route"); return; }
                Level = box.SelectedIndex + 1; CustomMm = v;
                DialogResult = DialogResult.OK;
            };
            Controls.Add(ok); Controls.Add(cancel);
            AcceptButton = ok; CancelButton = cancel;
        }
    }

    public class Suggestion
    {
        public string Name;
        public double Current, Best;
        public List<double[]> Poly = new List<double[]>();
    }

    /// <summary>Non-modal list of better routes found by the review.</summary>
    public class SuggestForm : Form
    {
        ListView list;
        readonly List<Suggestion> items;
        readonly Action<Suggestion> draw;

        public SuggestForm(List<Suggestion> suggestions, Action<Suggestion> drawCallback)
        {
            items = suggestions; draw = drawCallback;
            Text = "Smart Route - suggestions";
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(560, 260);
            TopMost = true;
            list = new ListView { Left = 10, Top = 10, Width = 540, Height = 190, View = View.Details, FullRowSelect = true, MultiSelect = false };
            list.Columns.Add("Route", 250); list.Columns.Add("Current", 90); list.Columns.Add("Suggested", 90); list.Columns.Add("Saving", 90);
            foreach (var s in items)
            {
                var it = new ListViewItem(s.Name);
                it.SubItems.Add((s.Current * 1000).ToString("0.0") + " mm");
                it.SubItems.Add((s.Best * 1000).ToString("0.0") + " mm");
                double pct = s.Current > 0 ? (s.Current - s.Best) / s.Current * 100 : 0;
                it.SubItems.Add(pct.ToString("0.0") + " %");
                list.Items.Add(it);
            }
            Controls.Add(list);
            var btn = new Button { Text = "Draw selected as 3D sketch", Left = 10, Top = 215, Width = 200 };
            btn.Click += (s, e) => { if (list.SelectedIndices.Count > 0) draw(items[list.SelectedIndices[0]]); };
            var close = new Button { Text = "Close", Left = 470, Top = 215, Width = 80 };
            close.Click += (s, e) => Close();
            Controls.Add(btn); Controls.Add(close);
        }
    }
}
