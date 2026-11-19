import os, tempfile
import auto_cable_route as a


def scan(boxes, calls):
    out = {}
    for n, b in boxes.items():
        def loader(n=n, bb=b):
            calls[n] = calls.get(n, 0) + 1
            return a.box_tris(bb)
        out[n] = (loader, b, (tuple(b), ()))
    return out


def test_geometry_is_read_once_and_only_changes_are_reread():
    boxes = {"wall": [0.4, -0.5, -0.5, 0.5, 0.5, 0.3], "L1": [0.1, 0.3, -0.3, 0.2, 0.4, -0.2]}
    calls = {}
    geo = a.GeoCache(None)
    assert geo.update(scan(boxes, calls)) == (2, 0, 0)
    for lv in (1, 2, 3):                                   # accuracy changes never re-read
        a.set_level(lv)
        geo.prepare(a.ST["cell"], log=lambda *x: None)
    assert calls == {"wall": 1, "L1": 1}
    boxes2 = dict(boxes, L1=[0.1, 0.3, -0.3, 0.25, 0.4, -0.2], new=[0.6, 0, 0, 0.7, 0.1, 0.1])
    calls.clear()
    assert geo.update(scan(boxes2, calls)) == (1, 1, 0)       # 1 new, 1 moved
    geo.prepare(a.ST["cell"], log=lambda *x: None)
    assert calls == {"L1": 1, "new": 1}                       # only those two were re-read
    assert geo.update(scan({k: v for k, v in boxes2.items() if k != "new"}, calls)) == (0, 0, 1)


def test_disk_cache_means_zero_reads_next_session():
    path = os.path.join(tempfile.mkdtemp(), "g.cache")
    boxes = {"wall": [0.4, -0.5, -0.5, 0.5, 0.5, 0.3]}
    calls = {}
    g1 = a.GeoCache(path)
    g1.update(scan(boxes, calls))
    a.set_level(2)
    g1.prepare(a.ST["cell"], log=lambda *x: None)
    g1.save_disk()
    calls.clear()
    g2 = a.GeoCache(path)
    g2.load_disk()
    assert g2.update(scan(boxes, calls)) == (0, 0, 0)
    g2.prepare(a.ST["cell"], log=lambda *x: None)
    assert calls == {} and g2.stats["from_disk"] == 1
