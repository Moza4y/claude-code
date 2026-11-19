import io, json, os, tempfile
import auto_cable_route as a

TMP = tempfile.mkdtemp()
BOXES = {"wall": [0.4, -0.5, -0.5, 0.5, 0.5, 0.3]}


class Model:
    def GetType(self): return 2
    def GetPathName(self): return os.path.join(TMP, "asm.SLDASM")


def run(reqs, monkeypatch):
    monkeypatch.setattr(a, "connect", lambda y: type("SW", (), {"ActiveDoc": Model()})())
    monkeypatch.setattr(a, "scan_components", lambda m: {n: ((lambda bb=b: a.box_tris(bb)), b, (tuple(b), ())) for n, b in BOXES.items()})
    out = io.StringIO()
    stdout = a.sys.stdout
    try:
        a.serve(io.StringIO("\n".join(json.dumps(r) for r in reqs) + "\n"), out)
    finally:
        a.sys.stdout = stdout
    return [json.loads(l) for l in out.getvalue().splitlines()]


def test_protocol(monkeypatch):
    resp = run([
        dict(id=1, cmd="init", level=2, clearance_mm=5),
        dict(id=2, cmd="plan", p0=[0, 0, 0], p1=[1, 0, 0], dia=0.01, k=6, target=None, rigid=[]),
        dict(id=3, cmd="verify", poly=[[0, 0, 0], [0, 0, 0.5], [1, 0, 0.5], [1, 0, 0]], dia=0.01, k=6, rigid=[]),
        dict(id=4, cmd="bogus"), dict(id=5, cmd="shutdown")], monkeypatch)
    assert [r["id"] for r in resp] == [1, 2, 3, 4, 5]
    assert resp[0]["ok"] and resp[0]["components"] == 1
    assert resp[1]["ok"] and len(resp[1]["alternatives"]) >= 2 and resp[1]["scene"]["cloud"]
    assert resp[2]["ok"] and resp[2]["check"]["bend_violations"]      # sharp corners flagged
    assert not resp[3]["ok"] and resp[4]["version"] == a.ENGINE_VERSION
