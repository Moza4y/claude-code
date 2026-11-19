import auto_cable_route as a
from helpers import geo_from_boxes, inside, WALL


def spec(geo, p0, p1, dia=0.01, k=6, target=None):
    return dict(p0=p0, p1=p1, dia=dia, k=k, target=target, geo=geo)


def test_goes_around_wall_without_touching_it():
    g = geo_from_boxes(WALL)
    r = a.plan_wire(spec(g, (0, 0, 0), (1, 0, 0)), [], 0.005)
    assert r is not None and not r["problems"]
    assert not any(inside(p, WALL["wall"]) for p in r["poly"])
    assert r["length"] < 1.6


def test_thin_plate_is_not_crossed_at_the_connector():
    plate = {"plate": [-0.2, -0.2, -0.003, 0.6, 0.2, 0.0]}
    g = geo_from_boxes(plate)
    r = a.plan_wire(spec(g, (0, 0, 0), (0.4, 0, 0), dia=0.005, k=5), [], 0.003)
    assert r is not None
    assert min(p[2] for p in r["poly"]) > -1e-6          # never goes below the plate


def test_hollow_enclosure_exit_through_opening():
    t = 0.003
    slabs = {"floor": [0, -.1, 0, .3, .1, t], "ceil": [0, -.1, .15 - t, .3, .1, .15], "back": [0, -.1, 0, t, .1, .15],
             "left": [0, -.1, 0, .3, -.1 + t, .15], "right": [0, .1 - t, 0, .3, .1, .15]}
    g = geo_from_boxes(slabs)
    r = a.plan_wire(spec(g, (0.15, 0, t), (0.55, 0, 0.075), dia=0.005, k=4), [], 0.003)
    assert r is not None
    assert max(p[0] for p in r["poly"]) >= 0.55 - 1e-6
    assert not any(inside(p, b) for p in r["poly"] for b in slabs.values())


def test_wanted_length_is_reached():
    g = geo_from_boxes(WALL)
    r = a.plan_wire(spec(g, (0, 0, 0), (1, 0, 0), target=1.9), [], 0.005)
    assert r is not None and abs(r["length"] - 1.9) < 1e-3


def test_wanted_length_shorter_than_possible_uses_shortest():
    g = geo_from_boxes(WALL)
    r = a.plan_wire(spec(g, (0, 0, 0), (1, 0, 0), target=0.5), [], 0.005)
    assert r is not None and r["length"] > 0.5 and r["note"]


def test_earlier_wire_is_rigid():
    g = geo_from_boxes(WALL)
    w1 = a.plan_wire(spec(g, (0, 0, 0), (1, 0, 0)), [], 0.005)
    w2 = a.plan_wire(spec(g, (0, 0.03, 0), (1, 0.03, 0)), [(w1["poly"], 0.01)], 0.005)
    d = min(a.norm(a.sub(p, q)) for p in w2["poly"] for q in w1["poly"])
    assert d >= 0.0099


def test_alternatives_are_verified_and_smooth_is_not_longer():
    g = geo_from_boxes(WALL)
    r = a.plan_with_alternatives(spec(g, (0, 0, 0), (1, 0, 0)), [], 0.005)
    alts = {x["label"]: x for x in r["alternatives"]}
    assert len(alts) >= 2
    smooth, neat = alts["Shortest (free angles)"], alts["Neat (right angles)"]
    assert smooth["length"] <= neat["length"] + 1e-9
    for x in alts.values():
        assert not x["check"]["collisions"] and not x["check"]["bend_violations"]


def test_verifier_catches_collision_and_sharp_bend():
    g = geo_from_boxes(WALL)
    ver = a.Verifier(g, [-0.1, -0.2, -0.2], [1.1, 0.2, 0.6], [], 0.0025)
    bad = [(0, 0, 0), (0.5, 0, 0), (0.5, 0, 0.5), (1, 0, 0.5)]
    c = ver.check([tuple(p) for p in a._densify(bad, 0.005)], 0.01, 6, 0.005)
    assert c["collisions"] and c["bend_violations"]
