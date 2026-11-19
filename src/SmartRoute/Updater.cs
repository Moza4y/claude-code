using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Threading;

namespace SmartRoute
{
    /// <summary>
    /// Checks GitHub Releases for a newer Setup.exe. Runs on a background thread, never blocks SOLIDWORKS.
    /// Installing needs SOLIDWORKS closed (the DLL is loaded), so the installer is started after SLDWORKS exits.
    /// </summary>
    public static class Updater
    {
        public class Info
        {
            public string Version, Url, Notes, Name;
        }

        public static Version Parse(string v)
        {
            v = (v ?? "").Trim().TrimStart('v', 'V');
            int dash = v.IndexOfAny(new[] { '-', '+' });
            if (dash > 0) v = v.Substring(0, dash);
            Version r;
            return System.Version.TryParse(v, out r) ? r : new Version(0, 0, 0);
        }

        /// <summary>Calls back on a worker thread: (info or null when up to date, error or null).</summary>
        public static void Check(Action<Info, string> done)
        {
            var t = new Thread(() =>
            {
                try
                {
                    if (AppInfo.Repo.StartsWith("OWNER/")) { done(null, "update repository is not configured"); return; }
                    ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072 | SecurityProtocolType.Tls;  // TLS 1.2
                    using (var wc = new WebClient())
                    {
                        wc.Headers[HttpRequestHeader.UserAgent] = "SmartRoute-Updater";
                        wc.Headers[HttpRequestHeader.Accept] = "application/vnd.github+json";
                        string json = wc.DownloadString("https://api.github.com/repos/" + AppInfo.Repo + "/releases/latest");
                        var d = J.S.DeserializeObject(json) as Dictionary<string, object>;
                        if (d == null) { done(null, "unexpected reply"); return; }
                        string tag = J.Get(d, "tag_name") as string;
                        if (Parse(tag) <= Parse(AppInfo.Version)) { done(null, null); return; }
                        string url = null, name = null;
                        foreach (var a in J.Objs(J.Get(d, "assets")))
                        {
                            string n = J.Get(a, "name") as string;
                            if (n != null && n.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) &&
                                n.IndexOf("Setup", StringComparison.OrdinalIgnoreCase) >= 0)
                            { url = J.Get(a, "browser_download_url") as string; name = n; break; }
                        }
                        if (url == null) { done(null, "release " + tag + " has no Setup.exe"); return; }
                        done(new Info { Version = tag, Url = url, Name = name, Notes = J.Get(d, "body") as string }, null);
                    }
                }
                catch (Exception e) { done(null, e.Message); }
            }) { IsBackground = true };
            t.Start();
        }

        /// <summary>Downloads the installer, then starts it silently once SOLIDWORKS has closed.</summary>
        public static void DownloadAndInstallOnExit(Info info, Action<string> done)
        {
            var t = new Thread(() =>
            {
                try
                {
                    ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072 | SecurityProtocolType.Tls;
                    string dir = Path.Combine(Path.GetTempPath(), "SmartRouteUpdate");
                    Directory.CreateDirectory(dir);
                    string file = Path.Combine(dir, info.Name);
                    using (var wc = new WebClient())
                    {
                        wc.Headers[HttpRequestHeader.UserAgent] = "SmartRoute-Updater";
                        wc.DownloadFile(info.Url, file);
                    }
                    // wait for SOLIDWORKS to close, then run the installer (it asks for admin rights itself)
                    string ps = "Wait-Process -Name SLDWORKS -ErrorAction SilentlyContinue; " +
                                "Start-Process -FilePath '" + file.Replace("'", "''") + "' -ArgumentList '/SILENT','/SUPPRESSMSGBOXES','/NORESTART'";
                    Process.Start(new ProcessStartInfo("powershell.exe", "-NoProfile -WindowStyle Hidden -Command \"" + ps + "\"")
                    { UseShellExecute = false, CreateNoWindow = true });
                    done(null);
                }
                catch (Exception e) { done(e.Message); }
            }) { IsBackground = true };
            t.Start();
        }
    }
}
