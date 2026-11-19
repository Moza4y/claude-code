using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;

namespace SmartRoute
{
    /// <summary>
    /// Talks to the Python planning engine ("auto_cable_route.py --server") with JSON lines.
    /// Requests are asynchronous: SOLIDWORKS stays free while the engine works (the engine itself
    /// calls back into SOLIDWORKS to read geometry, so we must never block the SOLIDWORKS thread).
    /// Replies are queued and handed to the SOLIDWORKS UI thread by Pump() (called from a timer).
    /// </summary>
    public class EngineClient
    {
        Process proc;
        StreamWriter stdin;
        readonly ConcurrentQueue<Action> uiQueue = new ConcurrentQueue<Action>();
        readonly Dictionary<int, Action<Dictionary<string, object>>> pending =
            new Dictionary<int, Action<Dictionary<string, object>>>();
        int nextId = 1;

        public string PythonExe = "python";
        public string ScriptPath = "";
        public string ExePath = "";          // packaged engine (preferred); Python + script is the fallback

        public bool Running { get { return proc != null && !proc.HasExited; } }

        /// <summary>Returns null on success, otherwise an error message.</summary>
        public string Start()
        {
            if (Running) return null;
            ProcessStartInfo psi;
            if (!string.IsNullOrEmpty(ExePath) && File.Exists(ExePath))
                psi = new ProcessStartInfo(ExePath, "--server");
            else
            {
                if (!File.Exists(ScriptPath)) return "Engine not found: " + ExePath + " / " + ScriptPath;
                psi = new ProcessStartInfo(PythonExe, "\"" + ScriptPath + "\" --server");
            }
            psi.UseShellExecute = false;
            psi.RedirectStandardInput = true;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.CreateNoWindow = true;
            psi.StandardOutputEncoding = Encoding.UTF8;
            try { proc = Process.Start(psi); }
            catch (Exception e) { return e.Message; }

            stdin = new StreamWriter(proc.StandardInput.BaseStream, new UTF8Encoding(false));
            stdin.AutoFlush = true;
            var p = proc;
            new Thread(() => ReadOut(p)) { IsBackground = true }.Start();
            new Thread(() => ReadErr(p)) { IsBackground = true }.Start();
            return null;
        }

        void ReadOut(Process p)
        {
            string line;
            try
            {
                while ((line = p.StandardOutput.ReadLine()) != null)
                {
                    try
                    {
                        var d = J.S.DeserializeObject(line) as Dictionary<string, object>;
                        if (d == null || !d.ContainsKey("id") || d["id"] == null) continue;
                        int id = Convert.ToInt32(d["id"]);
                        Action<Dictionary<string, object>> cb = null;
                        lock (pending)
                        {
                            pending.TryGetValue(id, out cb);
                            pending.Remove(id);
                        }
                        if (cb != null) uiQueue.Enqueue(() => cb(d));
                    }
                    catch (Exception e) { Log.W("engine reply parse: " + e.Message); }
                }
            }
            catch (Exception e) { Log.W("engine stdout closed: " + e.Message); }
            // engine ended: fail every waiting request
            List<Action<Dictionary<string, object>>> left;
            lock (pending) { left = new List<Action<Dictionary<string, object>>>(pending.Values); pending.Clear(); }
            foreach (var cb in left)
            {
                var c = cb;
                uiQueue.Enqueue(() => c(new Dictionary<string, object> { { "ok", false }, { "error", "engine stopped (see log)" } }));
            }
        }

        void ReadErr(Process p)
        {
            string line;
            try { while ((line = p.StandardError.ReadLine()) != null) Log.W("engine: " + line); }
            catch { }
        }

        public void Send(Dictionary<string, object> req, Action<Dictionary<string, object>> callback)
        {
            int id;
            lock (pending) { id = nextId++; pending[id] = callback; }
            req["id"] = id;
            try { stdin.WriteLine(J.S.Serialize(req)); }
            catch (Exception e)
            {
                lock (pending) { pending.Remove(id); }
                callback(new Dictionary<string, object> { { "ok", false }, { "error", e.Message } });
            }
        }

        /// <summary>Run queued callbacks on the calling (SOLIDWORKS UI) thread.</summary>
        public void Pump()
        {
            Action a;
            while (uiQueue.TryDequeue(out a))
            {
                try { a(); }
                catch (Exception e) { Log.W("callback: " + e); }
            }
        }

        public void Stop()
        {
            try
            {
                if (Running)
                {
                    try { stdin.WriteLine("{\"cmd\":\"shutdown\",\"id\":0}"); } catch { }
                    if (!proc.WaitForExit(1500)) proc.Kill();
                }
            }
            catch { }
            proc = null;
        }
    }
}
