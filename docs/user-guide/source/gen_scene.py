import sys, json
sys.path.insert(0, '/mnt/user-data/outputs/smart-route/src/engine')
import auto_cable_route as a
a.set_level(2)
g = a.GeoCache(None)
# Y-up scene (SOLIDWORKS default): a wall 0.30 m high between two connectors, 1 m apart
boxes = {"wall": [0.45, -0.25, -0.35, 0.55, 0.30, 0.35]}
g.update({n: ((lambda bb=b: a.box_tris(bb)), b, (tuple(b), ())) for n, b in boxes.items()})
g.prepare(a.ST['cell'], log=lambda *x: None)
spec = dict(p0=(0.0, 0.0, 0.0), p1=(1.0, 0.0, 0.0), dia=0.008, k=5, target=None, geo=g)
r = a.plan_with_alternatives(spec, [], 0.005)
out = dict(alternatives=r['alternatives'], scene=r['scene'], level=a.ST['name'], cell=a.ST['cell'] * 1000)
json.dump(out, open('scene.json', 'w'))
for al in r['alternatives']:
    c = al['check']
    print(al['label'], round(al['length'] * 1000, 1), len(al['pts']) - 2, 'bends', 'clr', round(c['min_clearance'] * 1000, 1), 'minR', round(c['min_radius'] * 1000, 1), 'viol', len(c['bend_violations']), 'col', len(c['collisions']), 'tight', len(c['tight']), 'planner problems', len(al['problems']))
