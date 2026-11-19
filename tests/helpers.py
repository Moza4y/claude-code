import auto_cable_route as a


def geo_from_boxes(boxes, level=2):
    a.set_level(level)
    g = a.GeoCache(None)
    g.update({n: ((lambda bb=b: a.box_tris(bb)), b, (tuple(b), ())) for n, b in boxes.items()})
    g.prepare(a.ST["cell"], log=lambda *x: None)
    return g


def inside(p, b):
    return all(b[i] < p[i] < b[i + 3] for i in range(3))


WALL = {"wall": [0.4, -0.5, -0.5, 0.5, 0.5, 0.3]}      # a wall with a gap above z = 0.3
