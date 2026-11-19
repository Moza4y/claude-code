using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Windows.Forms;
using System.Web.Script.Serialization;

namespace SmartRoute
{
    public class Settings
    {
        public double DiaMm { get; set; } = 5;
        public double BendMm { get; set; } = 30;
        public double ClearanceMm { get; set; } = 5;
        public int Level { get; set; } = 3;
        public double CustomMm { get; set; } = 0;
        public string PythonExe { get; set; } = "python";
        public bool Watch { get; set; } = false;
        public bool AutoUpdate { get; set; } = true;
        public long LastUpdateCheck { get; set; } = 0;
        public bool SwInterference { get; set; } = true;

        public static string Dir
        {
            get
            {
                string d = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "SmartRoute");
                Directory.CreateDirectory(d);
                return d;
            }
        }

        static string FilePath { get { return Path.Combine(Dir, "settings.json"); } }

        public static Settings Load()
        {
            try
            {
                if (File.Exists(FilePath))
                    return new JavaScriptSerializer().Deserialize<Settings>(File.ReadAllText(FilePath));
            }
            catch (Exception e) { Log.W("settings load: " + e.Message); }
            return new Settings();
        }

        public void Save()
        {
            try { File.WriteAllText(FilePath, new JavaScriptSerializer().Serialize(this)); }
            catch (Exception e) { Log.W("settings save: " + e.Message); }
        }
    }

    public static class Log
    {
        static string PathName { get { return Path.Combine(Settings.Dir, "smartroute.log"); } }

        public static void W(string s)
        {
            try { File.AppendAllText(PathName, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss ") + s + Environment.NewLine); }
            catch { }
        }

        public static string FilePath { get { return PathName; } }
    }

    public class Win32Window : IWin32Window
    {
        public IntPtr Handle { get; private set; }
        public Win32Window(IntPtr h) { Handle = h; }
    }

    /// <summary>Small helpers for the JSON the engine sends back (arrays arrive as object[]).</summary>
    public static class J
    {
        public static readonly JavaScriptSerializer S = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };

        public static double D(object o) { return Convert.ToDouble(o); }

        public static object Get(Dictionary<string, object> d, string key)
        {
            object v;
            return d != null && d.TryGetValue(key, out v) ? v : null;
        }

        public static bool Ok(Dictionary<string, object> d)
        {
            object v = Get(d, "ok");
            return v is bool && (bool)v;
        }

        public static string Err(Dictionary<string, object> d)
        {
            object v = Get(d, "error");
            return v == null ? "unknown error" : v.ToString();
        }

        public static double[] P(object o)
        {
            var l = new List<double>();
            foreach (object x in (IEnumerable)o) l.Add(D(x));
            return l.ToArray();
        }

        public static List<double[]> PL(object o)
        {
            var res = new List<double[]>();
            if (o == null) return res;
            foreach (object p in (IEnumerable)o) res.Add(P(p));
            return res;
        }

        public static List<Dictionary<string, object>> Objs(object o)
        {
            var res = new List<Dictionary<string, object>>();
            if (o == null) return res;
            foreach (object x in (IEnumerable)o)
            {
                var d = x as Dictionary<string, object>;
                if (d != null) res.Add(d);
            }
            return res;
        }
    }
}
