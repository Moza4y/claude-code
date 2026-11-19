# -*- coding: utf-8 -*-
"""
Auto Cable Route v4 for SolidWorks (any version) - works through COM, no add-in install.
Requires: Windows, Python 64-bit, pip install pywin32 numpy scipy

v4:
 * ACCURACY LEVEL (1-5, or a custom cell size like "2mm"): higher = finer grid = more accurate
   and slower; lower = fast draft. Change it any time with the command  acc
 * GEOMETRY CACHE: at start the tool reads every component's real faces (mesh) and prepares them
   for the chosen accuracy. After that it does NOT read them again:
     - new wires are just added on top of the stored data,
     - components that changed (moved / added / removed) are detected before each wire and ONLY
       those are re-read,
     - if you change the accuracy, the stored geometry is re-processed at the finer/coarser level.
   The mesh cache is also saved next to the assembly (<assembly>_geom.cache) so the next session
   starts fast (only changed components are re-read).
 * Everything from v3: real geometry obstacles, many wires per session, wanted length per wire,
   earlier wires = rigid, better-order search, problem spots with coordinates.
Commands at the prompt:  Enter = route next wire | done | acc | refresh (force re-read all)
"python auto_cable_route.py --server" = engine mode used by the SmartRoute add-in (JSON lines).
Always run Evaluate > Interference Detection at the end.
"""
import sys, math, heapq, json, os, time, random, pickle
from collections import OrderedDict
import numpy as np

try:
    from scipy.ndimage import distance_transform_edt as _edt
except Exception:  # works without scipy, but clearance is a bit more conservative
    _edt = None

DIRS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
PREFIX = "AutoCable_"
RAYDIR = (0.9167, 0.3718, 0.1496)
END = (-1, -1, -1)

# accuracy levels: cell = grid cell (m), cap = max cells per wire grid, nodes = max A* expansions
LEVELS = {
    1: dict(name="Draft", cell=0.020, cap=500_000, nodes=1_500_000),
    2: dict(name="Fast", cell=0.010, cap=1_500_000, nodes=3_000_000),
    3: dict(name="Normal", cell=0.005, cap=4_000_000, nodes=6_000_000),
    4: dict(name="Fine", cell=0.0025, cap=8_000_000, nodes=10_000_000),
    5: dict(name="Ultra", cell=0.0015, cap=14_000_000, nodes=14_000_000),
}
ST = {}


def set_level(level=3, custom_cell_mm=None):
    if custom_cell_mm:
        cell = custom_cell_mm / 1000.0
        cap = int(min(14e6, max(0.5e6, 4e6 * (0.005 / cell) ** 1.0)))
        ST.update(level=0, name="Custom %.2f mm" % custom_cell_mm, cell=cell, cap=cap, nodes=int(cap * 1.2))
    else:
        L = LEVELS[level]
        ST.update(level=level, name=L["name"], cell=L["cell"], cap=L["cap"], nodes=L["nodes"])


set_level(3)


class TooHeavy(Exception):
    pass


# ---------------- vector helpers ----------------
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def norm(a): return math.sqrt(dot(a, a))
def unit(a):
    n = norm(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)
def poly_length(p): return sum(norm(sub(b, a)) for a, b in zip(p, p[1:]))


# ---------------- geometry: meshes / cache ----------------
def box_tris(b):
    x0, y0, z0, x1, y1, z1 = b
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
         (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return np.array([[v[i], v[j], v[k]] for i, j, k in f], dtype=float)


def sample_surface(tris, step):
    """Points on the mesh surface, spacing <= step (longest-edge bisection)."""
    cur = np.asarray(tris, dtype=np.float32)
    out, total = [], 0
    perm = np.array([[0, 1, 2], [1, 2, 0], [2, 0, 1]])
    while len(cur):
        e = np.stack([np.linalg.norm(cur[:, 0] - cur[:, 1], axis=1),
                      np.linalg.norm(cur[:, 1] - cur[:, 2], axis=1),
                      np.linalg.norm(cur[:, 2] - cur[:, 0], axis=1)], 1)
        big = e.max(1) > step
        sm = cur[~big]
        if len(sm):
            out.append(sm.reshape(-1, 3))
            out.append(sm.mean(axis=1))
            total += len(sm) * 4
        bg = cur[big]
        if not len(bg):
            break
        if total + len(bg) > 8_000_000:       # safety: stop refining
            out.append(bg.reshape(-1, 3))
            break
        v = np.take_along_axis(bg, perm[e[big].argmax(1)][:, :, None], axis=1)
        m = (v[:, 0] + v[:, 1]) / 2
        cur = np.concatenate([np.stack([v[:, 0], m, v[:, 2]], 1), np.stack([m, v[:, 1], v[:, 2]], 1)])
    return np.concatenate(out) if out else np.zeros((0, 3), np.float32)


_PK = 1 << 20


def _pack(idx):
    i = idx + _PK
    return (i[:, 0] << 42) | (i[:, 1] << 21) | i[:, 2]


def _unpack(keys):
    m = (1 << 21) - 1
    return np.stack([(keys >> 42) & m, (keys >> 21) & m, keys & m], 1) - _PK


class Part:
    """One component: its box, change-signature, mesh (read once) and surface voxels per accuracy."""

    def __init__(self, name, box, sig=None, loader=None, tris=None, mode=None):
        self.name, self.box, self.sig, self.loader = name, list(box), sig, loader
        self._tris, self.mode = tris, mode
        self._skey, self._samp = None, None

    def has_tris(self):
        return self._tris is not None

    def tris(self):
        if self._tris is None:
            t = None
            if self.loader:
                try:
                    t = self.loader()
                except Exception:
                    t = None
            if t is None or len(t) == 0:
                self._tris, self.mode = np.asarray(box_tris(self.box), dtype=np.float32), "box"
            else:
                self._tris, self.mode = np.asarray(t, dtype=np.float32), "mesh"
            self.read_from_sw = True
        return self._tris

    def samples(self, cell):
        """Unique surface voxels (packed ints) on the global lattice of size `cell`."""
        key = round(cell, 7)
        if self._skey != key:
            pts = sample_surface(self.tris(), cell * 0.5)
            idx = np.rint(pts.astype(np.float64) / cell).astype(np.int64)
            self._samp = np.unique(_pack(idx)) if len(idx) else np.zeros(0, np.int64)
            self._skey = key
        return self._samp


class GeoCache:
    def __init__(self, path=None):
        self.parts, self.version, self.path = {}, 0, path
        self.disk = {}
        self.stats = dict(read_sw=0, from_disk=0)

    def load_disk(self):
        if self.path and os.path.exists(self.path):
            try:
                with open(self.path, "rb") as f:
                    self.disk = pickle.load(f)
            except Exception:
                self.disk = {}

    def save_disk(self):
        if not self.path:
            return
        try:
            data = {n: (p.sig, p._tris, p.mode) for n, p in self.parts.items() if p._tris is not None}
            with open(self.path, "wb") as f:
                pickle.dump(data, f, protocol=4)
        except Exception as e:
            print("  (could not save geometry cache: %s)" % e)

    def update(self, scan):
        """scan: {name: (loader, box, sig)} -> (added, changed, removed). Only those get re-read."""
        added = changed = 0
        for name, (loader, box, sig) in scan.items():
            p = self.parts.get(name)
            if p is None:
                d = self.disk.get(name)
                if d and d[0] == sig and d[1] is not None:
                    self.parts[name] = Part(name, box, sig, loader, tris=d[1], mode=d[2])
                    self.stats["from_disk"] += 1
                else:
                    self.parts[name] = Part(name, box, sig, loader)
                    added += 1
            elif p.sig != sig:
                self.parts[name] = Part(name, box, sig, loader)
                changed += 1
            else:
                p.loader = loader
        removed = [n for n in self.parts if n not in scan]
        for n in removed:
            del self.parts[n]
        if added or changed or removed:
            self.version += 1
        return added, changed, len(removed)

    def prepare(self, cell, log=print):
        """Read missing meshes (once) and build surface voxels for this accuracy."""
        t0 = time.time()
        todo = [p for p in self.parts.values() if not p.has_tris()]
        for i, p in enumerate(todo):
            p.tris()
            self.stats["read_sw"] += 1
            if len(todo) >= 20 and (i + 1) % max(1, len(todo) // 10) == 0:
                log("    reading geometry from SolidWorks: %d/%d" % (i + 1, len(todo)))
        if todo:
            self.save_disk()
        t1 = time.time()
        stale = [p for p in self.parts.values() if p._skey != round(cell, 7)]
        for i, p in enumerate(stale):
            p.samples(cell)
            if len(stale) >= 20 and (i + 1) % max(1, len(stale) // 10) == 0:
                log("    preparing surfaces (cell %.1f mm): %d/%d" % (cell * 1000, i + 1, len(stale)))
        return dict(read=len(todo), prep=len(stale), t_read=t1 - t0, t_prep=time.time() - t1)

    def summary(self):
        ps = list(self.parts.values())
        tr = sum(len(p._tris) for p in ps if p._tris is not None)
        vox = sum(len(p._samp) for p in ps if p._samp is not None)
        box = [p.name for p in ps if p.mode == "box"]
        return len(ps), tr, vox, box


def point_in_solid(q, tris):
    """Ray-parity test (Moller-Trumbore, vectorised) against one closed mesh."""
    t = np.asarray(tris, dtype=np.float64)
    d = np.array(RAYDIR)
    q = np.array(q)
    v0 = t[:, 0]
    e1, e2 = t[:, 1] - v0, t[:, 2] - v0
    pv = np.cross(d, e2)
    det = (e1 * pv).sum(1)
    ok = np.abs(det) > 1e-14
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    tv = q - v0
    u = (tv * pv).sum(1) * inv
    qv = np.cross(tv, e1)
    v = (qv * d).sum(1) * inv
    tt = (e2 * qv).sum(1) * inv
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (tt > 1e-9)
    return int(hit.sum()) % 2 == 1


def local_surface(parts, lo, h, n, cell):
    S = np.zeros(n, dtype=bool)
    lo_a, n_a = np.array(lo), np.array(n)
    for p in parts:
        keys = p.samples(cell)
        if not len(keys):
            continue
        c = _unpack(keys).astype(np.float64) * cell
        idx = np.rint((c - lo_a) / h).astype(np.int64)
        ok = (idx >= 0).all(1) & (idx < n_a).all(1)
        idx = idx[ok]
        S[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    return S


def dist_cells(S):
    """Distance (in cells) from every cell to the nearest surface voxel."""
    if not S.any():
        return np.full(S.shape, 1e9, np.float32)
    if _edt is not None:
        return _edt(~S).astype(np.float32)
    d = np.full(S.shape, 1e9, np.float32)   # fallback: chessboard distance (conservative)
    cur = S.copy()
    d[cur] = 0
    for r in range(1, 13):
        nxt = cur.copy()
        for ax in range(3):
            a = nxt.copy()
            s1, s2 = [slice(None)] * 3, [slice(None)] * 3
            s1[ax], s2[ax] = slice(1, None), slice(None, -1)
            nxt[tuple(s1)] |= a[tuple(s2)]
            nxt[tuple(s2)] |= a[tuple(s1)]
        new = nxt & ~cur
        if not new.any():
            break
        d[new] = r
        cur = nxt
    return d


_FIELDS = OrderedDict()          # small LRU of distance fields (reused e.g. by the order search)
_FIELD_BUDGET = 40_000_000


def _field(key, build):
    if key in _FIELDS:
        _FIELDS.move_to_end(key)
        return _FIELDS[key]
    val = build()
    _FIELDS[key] = val
    while len(_FIELDS) > 1 and sum(v[0].size for v in _FIELDS.values()) > _FIELD_BUDGET:
        _FIELDS.popitem(last=False)
    return val


def block_polyline(blocked, lo, h, poly, radius):
    n = blocked.shape
    r = int(math.ceil(radius / h))
    for a, b in zip(poly, poly[1:]):
        steps = max(1, int(math.ceil(norm(sub(b, a)) / (h * 0.5))))
        for s in range(steps + 1):
            p = add(a, mul(sub(b, a), s / steps))
            c = [int(round((p[i] - lo[i]) / h)) for i in range(3)]
            blocked[max(0, c[0] - r):max(0, min(n[0], c[0] + r + 1)),
                    max(0, c[1] - r):max(0, min(n[1], c[1] + r + 1)),
                    max(0, c[2] - r):max(0, min(n[2], c[2] + r + 1))] = True


def to_cell(p, lo, h, n):
    return tuple(min(n[i] - 1, max(0, int(round((p[i] - lo[i]) / h)))) for i in range(3))


def polyline_free(grid, pts):
    blocked, lo, h, n = grid
    for a, b in zip(pts, pts[1:]):
        steps = max(1, int(math.ceil(norm(sub(b, a)) / (h * 0.5))))
        for s in range(steps + 1):
            p = add(a, mul(sub(b, a), s / steps))
            c = tuple(int(round((p[i] - lo[i]) / h)) for i in range(3))
            if any(c[i] < 0 or c[i] >= n[i] for i in range(3)) or blocked[c]:
                return False
    return True


# ---------------- search ----------------
def astar_multi(blocked, starts, goals, gpt, slack_cells, turn_cost=3.0, max_nodes=6_000_000):
    """starts: {cell:(cost,dir)}, goals: {cell:cost}. Returns list of cells or None.
    Integer-coded nodes + larger-g tie-breaking (much fewer expansions in open space)."""
    nx, ny, nz = blocked.shape
    b = blocked.copy()
    b[0, :, :] = b[-1, :, :] = True          # solid border -> no bounds checks in the loop
    b[:, 0, :] = b[:, -1, :] = True
    b[:, :, 0] = b[:, :, -1] = True
    flat = bytes(b.ravel())
    sy, sx = nz, ny * nz
    offs = [dx * sx + dy * sy + dz for dx, dy, dz in DIRS]
    hx = [max(0, abs(i - gpt[0]) - slack_cells) for i in range(nx)]
    hy = [abs(i - gpt[1]) for i in range(ny)]
    hz = [abs(i - gpt[2]) for i in range(nz)]
    gl = {c[0] * sx + c[1] * sy + c[2]: v for c, v in goals.items()}
    heap, best, parent, pops = [], {}, {}, 0
    push, pop = heapq.heappush, heapq.heappop
    for c, (cost, d) in starts.items():
        idx = c[0] * sx + c[1] * sy + c[2]
        node = idx * 6 + d
        best[node] = cost
        push(heap, (cost + hx[c[0]] + hy[c[1]] + hz[c[2]], -cost, node))
    while heap:
        f, ng_, node = pop(heap)
        gc = -ng_
        pops += 1
        if pops > max_nodes:
            raise TooHeavy()
        if node == -1:
            key = parent[-1]
            path = [key // 6]
            while key in parent:
                key = parent[key]
                path.append(key // 6)
            return [(i // sx, (i % sx) // sy, i % sy) for i in reversed(path)]
        if gc > best.get(node, 1e18):
            continue
        idx, d = divmod(node, 6)
        if idx in gl:
            gcost = gc + gl[idx]
            if gcost < best.get(-1, 1e18):
                best[-1] = gcost
                parent[-1] = node
                push(heap, (gcost, -gcost, -1))
        x, r = divmod(idx, sx)
        y, z = divmod(r, sy)
        for nd in range(6):
            nidx = idx + offs[nd]
            if flat[nidx]:
                continue
            g2 = gc + 1 + (turn_cost if nd != d else 0)
            nn = nidx * 6 + nd
            if g2 < best.get(nn, 1e18):
                best[nn] = g2
                parent[nn] = node
                dx, dy, dz = DIRS[nd]
                push(heap, (g2 + hx[x + dx] + hy[y + dy] + hz[z + dz], -g2, nn))
    return None


def corners_only(pts):
    clean = [pts[0]]
    for p in pts[1:]:
        if norm(sub(p, clean[-1])) > 1e-6:
            clean.append(p)
    if len(clean) < 3:
        return clean
    out = [clean[0]]
    for i in range(1, len(clean) - 1):
        a = unit(sub(clean[i], clean[i - 1]))
        b = unit(sub(clean[i + 1], clean[i]))
        if dot(a, b) < 0.999:
            out.append(clean[i])
    out.append(clean[-1])
    return out


def fillet(pts, R, nseg=8):
    """Round every corner with radius R -> (polyline, problems[(corner, eff_radius)])."""
    poly, problems = [pts[0]], []
    last = len(pts) - 1
    for i in range(1, last):
        v, a, b = pts[i], pts[i - 1], pts[i + 1]
        u1, u2 = unit(sub(a, v)), unit(sub(b, v))
        phi = math.acos(max(-1.0, min(1.0, dot(u1, u2))))
        if phi > math.pi - 1e-3:
            poly.append(v)
            continue
        t = R / math.tan(phi / 2)
        la, lb = norm(sub(a, v)), norm(sub(b, v))
        cap = min(la if i - 1 == 0 else 0.5 * la, lb if i + 1 == last else 0.5 * lb)
        reff = R
        if t > cap:
            t = cap
            reff = t * math.tan(phi / 2)
            problems.append((v, reff))
        t1, t2 = add(v, mul(u1, t)), add(v, mul(u2, t))
        c = add(v, mul(unit(add(u1, u2)), reff / math.sin(phi / 2)))
        r1, r2 = sub(t1, c), sub(t2, c)
        theta = math.pi - phi
        for k in range(nseg + 1):
            s = k / nseg
            w1 = math.sin((1 - s) * theta) / math.sin(theta)
            w2 = math.sin(s * theta) / math.sin(theta)
            poly.append(add(c, add(mul(r1, w1), mul(r2, w2))))
    poly.append(pts[-1])
    return poly, problems


# ---------------- slack (wanted length) ----------------
def add_slack(pts, R, target, grid, tol=5e-4):
    """Add U-shaped bumps on long straight runs until the rounded length == target."""
    cur = list(pts)
    base_probs = len(fillet(cur, R)[1])
    h = grid[2]
    for _ in range(4):
        L = poly_length(fillet(cur, R)[0])
        if abs(L - target) <= tol:
            return cur
        partial = over = None
        order = sorted(range(len(cur) - 1), key=lambda i: -norm(sub(cur[i + 1], cur[i])))
        for i in order[:6]:
            A, B = cur[i], cur[i + 1]
            Ls = norm(sub(B, A))
            if Ls < 2.5 * R:
                continue
            e = unit(sub(B, A))
            w = min(0.7 * Ls, max(4 * R, 0.4 * Ls))
            a = add(A, mul(e, (Ls - w) / 2))
            b = add(a, mul(e, w))
            for dv in DIRS:
                nrm = sub(dv, mul(e, dot(dv, e)))
                if norm(nrm) < 0.8:
                    continue
                nrm = unit(nrm)

                def build(d, i=i, a=a, b=b, nrm=nrm, base=cur):
                    return base[:i + 1] + [a, add(a, mul(nrm, d)), add(b, mul(nrm, d)), b] + base[i + 1:]

                def ev(d):
                    p, pr = fillet(build(d), R)
                    return poly_length(p), len(pr)

                dcap = (target - L) + 4 * R
                dmax, d = 0.0, h
                while d <= dcap:
                    if polyline_free(grid, [a, add(a, mul(nrm, d)), add(b, mul(nrm, d)), b]):
                        dmax = d
                    else:
                        break
                    d += h
                if dmax < R:
                    continue
                dmin, d, step = None, R, max(R / 4, h / 2)
                while d <= dmax + 1e-9:
                    if ev(d)[1] <= base_probs:
                        dmin = d
                        break
                    d += step
                if dmin is None:
                    continue
                Lmin, Lmax = ev(dmin)[0], ev(dmax)[0]
                if Lmin > target + tol:
                    if over is None or Lmin < over[0]:
                        over = (Lmin, build(dmin))
                    continue
                if Lmax < target - tol:
                    if partial is None or Lmax > partial[0]:
                        partial = (Lmax, build(dmax))
                    continue
                lo_d, hi_d = dmin, dmax
                for _k in range(40):
                    mid = (lo_d + hi_d) / 2
                    if ev(mid)[0] < target:
                        lo_d = mid
                    else:
                        hi_d = mid
                return build(hi_d)
        if partial:
            cur = partial[1]
            continue
        if over:
            return over[1]
        return cur
    return cur


# ---------------- plan one wire ----------------
def _entries(blocked, p, lo, h, n, kmax, dirs_ok, kmin=0):
    """Straight stubs from the connection point out of the surface layer.
    The stub is at least `kmin` cells long (>= bend radius) when the space allows it."""
    c0 = to_cell(p, lo, h, n)
    out = {}
    for di in dirs_ok:
        dx, dy, dz = DIRS[di]
        nb = 0
        for kk in range(1, kmax + 1):
            c = (c0[0] + dx * kk, c0[1] + dy * kk, c0[2] + dz * kk)
            if not all(0 <= c[i] < n[i] for i in range(3)):
                break
            if blocked[c]:
                nb += 1
                if nb > 2:
                    break
                continue
            kt, ok = max(kk, kmin), True
            for k2 in range(kk + 1, kt + 1):
                c2 = (c0[0] + dx * k2, c0[1] + dy * k2, c0[2] + dz * k2)
                if not all(0 <= c2[i] < n[i] for i in range(3)) or blocked[c2]:
                    ok = False
                    break
            if ok:
                out[(c0[0] + dx * kt, c0[1] + dy * kt, c0[2] + dz * kt)] = (float(kt), di)
            else:
                out[c] = (float(kk), di)
            break
    return out


def _dirs_outside(p, sel):
    dl = 5e-4   # 0.5 mm: must stay smaller than any wall thickness
    ok = []
    for di, d in enumerate(DIRS):
        q = add(p, mul(d, dl))
        inside_any = False
        for part in sel:
            b = part.box
            if all(b[i] - 1e-4 <= q[i] <= b[i + 3] + 1e-4 for i in range(3)) and point_in_solid(q, part.tris()):
                inside_any = True
                break
        if not inside_any:
            ok.append(di)
    return ok or list(range(6))


COARSE_TRIGGER = 1_000_000     # fine grids bigger than this are solved coarse-to-fine
COARSE_TARGET = 450_000


def _grid(spec, rigid, clr, ms, lo, hi, h, cell):
    """Dense blocked-grid for one wire at cell size h (field cached, wires added on top)."""
    p0, p1, dia, k = spec["p0"], spec["p1"], spec["dia"], spec["k"]
    geo, R = spec["geo"], spec["dia"] * spec["k"]
    margin = dia / 2 + (clr + 0.41 * R) * ms
    n = [int(math.ceil((hi[i] - lo[i]) / h)) + 1 for i in range(3)]
    sel = [q for q in geo.parts.values()
           if all(q.box[i] <= hi[i] + margin and q.box[i + 3] >= lo[i] - margin for i in range(3))]

    def build_field():
        d = dist_cells(local_surface(sel, lo, h, n, cell))
        return d, [q.name for q in sel if q.mode == "box"]

    fkey = (geo.version, round(h, 7), round(cell, 7), tuple(round(x, 6) for x in lo), tuple(n), round(margin, 6))
    dcell, box_parts = _field(fkey, build_field)
    dist = dcell * h
    full = dist <= max(margin + 0.5 * h, 1.01 * h)
    near = dist <= 1.01 * h
    wfull = np.zeros(n, dtype=bool)
    wnear = np.zeros(n, dtype=bool)
    for poly, d in rigid:
        block_polyline(wfull, lo, h, poly, d / 2 + dia / 2 + clr * ms)
        block_polyline(wnear, lo, h, poly, d / 2 + dia / 2)
    full |= wfull
    near |= wnear
    rho = margin + 2 * h          # near the endpoints only a thin skin is blocked
    blocked = full.copy()
    for p in (p0, p1):
        c = to_cell(p, lo, h, n)
        rc = int(math.ceil(rho / h)) + 1
        sl = tuple(slice(max(0, c[i] - rc), min(n[i], c[i] + rc + 1)) for i in range(3))
        g = np.ogrid[sl[0], sl[1], sl[2]]
        mask = ((g[0] - c[0]) ** 2 + (g[1] - c[1]) ** 2 + (g[2] - c[2]) ** 2) <= (rho / h) ** 2
        sub_b = blocked[sl]
        sub_b[mask] = near[sl][mask]
    return dict(blocked=blocked, lo=lo, h=h, n=n, sel=sel, box_parts=box_parts, rho=rho)


def _route(G, spec, corridor=None):
    """A* on a prepared grid -> dict(pts, poly, problems) (pts = corner points before rounding)."""
    p0, p1, R = spec["p0"], spec["p1"], spec["dia"] * spec["k"]
    blocked, lo, h, n = G["blocked"], G["lo"], G["h"], G["n"]
    kmin = int(math.ceil(R / h))                 # first/last straight piece >= bend radius
    kmax = max(int(math.ceil(G["rho"] / h)) + 2, kmin + 2)
    starts = _entries(blocked, p0, lo, h, n, kmax, _dirs_outside(p0, G["sel"]), kmin)
    goals_raw = _entries(blocked, p1, lo, h, n, kmax, _dirs_outside(p1, G["sel"]), kmin)
    if not starts or not goals_raw:
        return None
    goals = {c: v[0] for c, v in goals_raw.items()}
    gcell = to_cell(p1, lo, h, n)
    blk = blocked if corridor is None else (blocked | ~corridor)
    best = None
    for tc in (4.0, 20.0):
        path = astar_multi(blk, starts, goals, gcell, kmax + 3, tc, ST["nodes"])
        if not path:
            break
        cen = [(lo[0] + c[0] * h, lo[1] + c[1] * h, lo[2] + c[2] * h) for c in path]
        pts = corners_only([tuple(p0)] + cen + [tuple(p1)])
        poly, problems = fillet(pts, R)
        cand = (len(problems), poly_length(poly))
        if best is None or cand < best[0]:
            best = (cand, pts, poly, problems)
        if not problems:
            break
    if best is None:
        return None
    return dict(pts=best[1], poly=best[2], problems=best[3])


def _plan(spec, rigid, clr, factor, ms, seen):
    p0, p1, dia, k, target = spec["p0"], spec["p1"], spec["dia"], spec["k"], spec.get("target")
    R = dia * k
    cell, cap = ST["cell"], ST["cap"]
    margin = dia / 2 + (clr + 0.41 * R) * ms
    d01 = norm(sub(p1, p0))
    pad = max(factor * max(0.08, 0.4 * d01), 3 * cell)

    def dims(lo, hi, h):
        return [int(math.ceil((hi[i] - lo[i]) / h)) + 1 for i in range(3)]

    lo = [min(p0[i], p1[i]) - pad for i in range(3)]
    hi = [max(p0[i], p1[i]) + pad for i in range(3)]
    h = cell
    n = dims(lo, hi, h)
    cells = n[0] * n[1] * n[2]
    sig = (round(pad, 4), ms)
    if sig in seen:
        return None
    seen.add(sig)
    notes = []
    rlo, rhi, hc, coarse_mode = list(lo), list(hi), None, False

    if cells <= COARSE_TRIGGER:                      # small region: one fine pass
        G = _grid(spec, rigid, clr, ms, lo, hi, h, cell)
        rf = _route(G, spec)
        if rf is None:
            return None
        slack_grid = (G["blocked"], G["lo"], G["h"], G["n"])
    else:                                            # coarse over everything, fine only around the path
        f = max(2, int(math.ceil((cells / COARSE_TARGET) ** (1.0 / 3.0))))
        hc = h * f
        coarse_mode = True
        Gc = _grid(spec, rigid, clr, ms, lo, hi, hc, cell)
        rc = _route(Gc, spec)
        if rc is None:
            return None
        rf = None
        for width in (3, 8):
            r_c = width * hc
            flo = [max(lo[i], min(q[i] for q in rc["pts"]) - r_c) for i in range(3)]
            fhi = [min(hi[i], max(q[i] for q in rc["pts"]) + r_c) for i in range(3)]
            h = cell
            fn = dims(flo, fhi, h)
            while fn[0] * fn[1] * fn[2] > cap:       # protect memory: coarsen only the fine pass
                h *= 1.1
                fn = dims(flo, fhi, h)
            if h > cell * 1.0001 and not any("coarsened" in x for x in notes):
                notes.append("fine cell coarsened from %.1f to %.1f mm (path region too big for this accuracy level)"
                             % (cell * 1000, h * 1000))
            G = _grid(spec, rigid, clr, ms, flo, fhi, h, cell)
            corridor = np.zeros(G["n"], dtype=bool)
            block_polyline(corridor, flo, h, rc["pts"], r_c)
            for p in (p0, p1):
                block_polyline(corridor, flo, h, [tuple(p), tuple(p)], G["rho"] + h)
            rf = _route(G, spec, corridor)
            if rf is not None:
                break
        if rf is None:
            return None
        lo, hi, n = flo, fhi, G["n"]
    pts, poly, problems = rf["pts"], rf["poly"], rf["problems"]
    shortest = poly_length(poly)
    if target is not None:
        if target <= shortest + 5e-4:
            if target < shortest - 5e-4:
                notes.append("wanted %.1f mm is shorter than the shortest possible (%.1f mm) - using shortest"
                             % (target * 1000, shortest * 1000))
        else:
            if coarse_mode:      # fine grid around everything a slack bump could reach
                rs = (target - shortest) / 2 + 5 * R + 3 * hc
                slo = [max(rlo[i], min(q[i] for q in pts) - rs) for i in range(3)]
                shi = [min(rhi[i], max(q[i] for q in pts) + rs) for i in range(3)]
                hs = cell
                while True:
                    sn = dims(slo, shi, hs)
                    if sn[0] * sn[1] * sn[2] <= cap:
                        break
                    hs *= 1.1
                Gs = _grid(spec, rigid, clr, ms, slo, shi, hs, cell)
                slack_grid = (Gs["blocked"], Gs["lo"], Gs["h"], Gs["n"])
            pts = add_slack(pts, R, target, slack_grid)
            poly, problems = fillet(pts, R)
            if abs(poly_length(poly) - target) > 1e-3:
                notes.append("closest achievable length is %.1f mm (wanted %.1f mm)"
                             % (poly_length(poly) * 1000, target * 1000))
    return dict(poly=poly, pts=pts, problems=problems, length=poly_length(poly), shortest=shortest,
                note=" | ".join(notes) if notes else None, cell_mm=G["h"] * 1000, box_parts=G["box_parts"],
                level=ST["name"])


FAIL = {"reason": None}


def plan_wire(spec, rigid, clearance):
    """spec: dict(geo,p0,p1,dia,k,target). rigid: [(poly, dia)]. All meters."""
    FAIL["reason"] = "no path"
    seen = set()
    try:
        for ms in (1.0, 0.6, 0.3):
            for factor in (1, 2, 4):
                res = _plan(spec, rigid, clearance, factor, ms, seen)
                if res:
                    if ms < 1.0:
                        msg = "clearance reduced to %d%% to find a path" % int(ms * 100)
                        res["note"] = (res["note"] + " | " + msg) if res["note"] else msg
                    return res
    except TooHeavy:
        FAIL["reason"] = "search too heavy for this accuracy level - lower the accuracy (command: acc)"
    return None


# ---------------- better order for all wires ----------------
def score_of(results):
    return (sum(r is None for r in results),
            sum(len(r["problems"]) for r in results if r),
            sum(r["length"] for r in results if r))


def search_orders(specs, rigid0, clearance, baseline_results, budget_s=120):
    n = len(specs)
    t0 = time.time()
    best = {"score": score_of(baseline_results), "order": None, "results": None}
    rng = random.Random(1)
    stats = {"timeout": False}

    def rec(order, rigid, results):
        if time.time() - t0 > budget_s:
            stats["timeout"] = True
            return
        part = score_of(results)
        if results and part >= best["score"]:
            return  # scores only grow -> cannot beat best any more
        if len(order) == n:
            best.update(score=part, order=list(order), results=list(results))
            return
        kids = [i for i in range(n) if i not in order]
        if n > 6:
            rng.shuffle(kids)
        for i in kids:
            r = plan_wire(specs[i], rigid, clearance)
            rec(order + [i], rigid + ([(r["poly"], specs[i]["dia"])] if r else []), results + [r])

    rec([], list(rigid0), [])
    return best, stats


# ---------------- persistence ----------------
def asm_base(model):
    p = model.GetPathName
    p = p() if callable(p) else p
    return os.path.splitext(p)[0] if p else os.path.join(os.getcwd(), "unsaved")


def load_store(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_store(path, wires):
    with open(path, "w") as f:
        json.dump(wires, f)


# ---------------- SolidWorks side ----------------
def connect(year):
    import win32com.client as wc
    if year:
        try:
            return wc.Dispatch("SldWorks.Application.%d" % (year - 1992))  # 2023 -> 31
        except Exception:
            print("Version %d not found, using the running SolidWorks..." % year)
    return wc.GetActiveObject("SldWorks.Application")


def _mesh_matches(t, box):
    v = t.reshape(-1, 3)
    lo, hi, b = v.min(0), v.max(0), np.array(box)
    size = max(float(np.max(b[3:] - b[:3])), 1e-3)
    tol = max(1e-3, 0.02 * size)
    inside = np.all(lo >= b[:3] - tol) and np.all(hi <= b[3:] + tol)
    cover = np.all((hi - lo) >= 0.5 * (b[3:] - b[:3]) - tol)
    return bool(inside and cover)


def mesh_for(comp, box):
    """Triangles (m,3,3) of the component in ASSEMBLY coordinates, or None."""
    try:
        if comp.GetSuppression2() in (1, 4):      # lightweight -> resolve
            comp.SetSuppression2(3)
    except Exception:
        pass
    cands = []
    for no_conv in (False, True):
        try:
            arr = comp.GetTessTriangles(no_conv)
        except Exception:
            continue
        if arr is None:
            continue
        a = np.array(arr, dtype=np.float64)
        if a.size == 0 or a.size % 9:
            continue
        t = a.reshape(-1, 3, 3)
        if _mesh_matches(t, box):
            return t
        cands.append(t)
    try:                                          # maybe component coords -> apply transform
        T = list(comp.Transform2.ArrayData)
        rot, tr, sc = np.array(T[0:9]).reshape(3, 3), np.array(T[9:12]), T[12]
    except Exception:
        return None
    for t in cands:
        for M in (rot, rot.T):
            t2 = ((t.reshape(-1, 3) @ M.T) * sc + tr).reshape(-1, 3, 3)
            if _mesh_matches(t2, box):
                return t2
    return None


def scan_components(model):
    """{name: (loader, box, signature)} for every unsuppressed component."""
    out = {}
    for c in model.GetComponents(False) or ():
        try:
            if c.IsSuppressed():
                continue
            b = c.GetBox(False, False)
        except Exception:
            continue
        if not b:
            continue
        b = list(b)
        try:
            tf = tuple(round(x, 7) for x in c.Transform2.ArrayData)
        except Exception:
            tf = ()
        out[c.Name2] = ((lambda comp=c, bb=b: mesh_for(comp, bb)), b, (tuple(round(x, 7) for x in b), tf))
    return out


def select_sketch(model, name):
    import win32com.client as wc, pythoncom
    nothing = wc.VARIANT(pythoncom.VT_DISPATCH, None)
    model.ClearSelection2(True)
    return bool(model.Extension.SelectByID2(PREFIX + name, "SKETCH", 0, 0, 0, False, 0, nothing, 0))


def sketch_exists(model, name):
    ok = select_sketch(model, name)
    model.ClearSelection2(True)
    return ok


def delete_sketch(model, name):
    if select_sketch(model, name):
        model.Extension.DeleteSelection2(2)


def create_sketch(model, name, poly):
    sk = model.SketchManager
    sk.Insert3DSketch(True)
    for a, b in zip(poly, poly[1:]):
        sk.CreateLine(a[0], a[1], a[2], b[0], b[1], b[2])
    sk.Insert3DSketch(True)
    try:
        model.FeatureByPositionReverse(0).Name = PREFIX + name
        return True
    except Exception:
        return False


def ask_float(prompt, default=None):
    while True:
        s = input(prompt + (" [%s]" % default if default is not None else "") + ": ").strip()
        if not s and default is not None:
            return float(default)
        try:
            return float(s)
        except ValueError:
            print("  numbers only please")


def ask_accuracy(current=3):
    print("\nAccuracy (grid cell size):")
    for k, v in LEVELS.items():
        print("  %d = %-6s cell %.1f mm" % (k, v["name"], v["cell"] * 1000))
    print("  or type a custom cell size, e.g. 3mm")
    while True:
        s = input("Accuracy [%d]: " % current).strip().lower()
        if not s:
            return dict(level=current)
        try:
            if s.endswith("mm"):
                return dict(custom=float(s[:-2]))
            v = int(s)
            if v in LEVELS:
                return dict(level=v)
        except ValueError:
            pass
        print("  type 1-5 or e.g. 3mm")


def apply_accuracy(choice):
    set_level(choice.get("level", 3), choice.get("custom"))
    print("Accuracy: %s (cell %.1f mm)" % (ST["name"], ST["cell"] * 1000))


def prepare_geometry(geo):
    r = geo.prepare(ST["cell"])
    n, tr, vox, box = geo.summary()
    print("Geometry ready: %d components, %d triangles, %.1fM surface voxels | read %d, prepared %d (%.1fs + %.1fs)"
          % (n, tr, vox / 1e6, r["read"], r["prep"], r["t_read"], r["t_prep"]))
    if box:
        print("  no mesh for (bounding box used): %s" % ", ".join(box[:8]) + (" ..." if len(box) > 8 else ""))


def describe(name, res, dia, k):
    print("  %s: length %.1f mm (shortest possible %.1f mm) | %s, cell %.1f mm"
          % (name, res["length"] * 1000, res["shortest"] * 1000, res["level"], res["cell_mm"]))
    if res["note"]:
        print("  NOTE:", res["note"])
    if res["box_parts"]:
        print("  (bounding box used for: %s)" % ", ".join(res["box_parts"][:8]))
    for v, reff in res["problems"]:
        print("  PROBLEM at (%.1f, %.1f, %.1f) mm -> radius only %.1f mm, needed %.1f mm"
              % (v[0] * 1000, v[1] * 1000, v[2] * 1000, reff * 1000, dia * k * 1000))


def sync_changes(model, geo):
    a, c, r = geo.update(scan_components(model))
    if a or c or r:
        print("Assembly changed: +%d new, %d modified, -%d removed -> updating only those..." % (a, c, r))
        prepare_geometry(geo)
        return True
    return False


def main():
    if _edt is None:
        print("(tip: pip install scipy  -> more accurate clearance)")
    s = input("SolidWorks year (e.g. 2023) or Enter for the running one: ").strip()
    year = int(s) if s else None
    clr = ask_float("Safety clearance (mm)", 5) / 1000
    apply_accuracy(ask_accuracy(3))

    sw = connect(year)
    model = sw.ActiveDoc
    if model is None or model.GetType() != 2:
        sys.exit("Open an ASSEMBLY first.")
    sm = model.SelectionManager
    base = asm_base(model)
    spath = base + "_cables.json"

    geo = GeoCache(base + "_geom.cache")
    geo.load_disk()
    print("\nReading the assembly geometry (once)...")
    a, c, r = geo.update(scan_components(model))
    if geo.stats["from_disk"]:
        print("  %d components loaded from the saved cache (unchanged)" % geo.stats["from_disk"])
    prepare_geometry(geo)

    old = [w for w in load_store(spath) if sketch_exists(model, w["name"])]
    save_store(spath, old)
    rigid_old = [([tuple(p) for p in w["poly"]], w["dia"]) for w in old]
    if old:
        print("Found %d earlier wire(s) -> treated as rigid: %s" % (len(old), ", ".join(w["name"] for w in old)))
    used = {w["name"] for w in old}

    specs, results, created = [], [], []
    last_dia, last_k = 5.0, 6.0
    while True:
        cmd = input("\nSelect START and END points of wire #%d, then press Enter "
                    "(or: done | acc | refresh): " % (len(specs) + 1)).strip().lower()
        if cmd.startswith("d"):
            break
        if cmd.startswith("acc"):
            apply_accuracy(ask_accuracy(ST["level"] or 3))
            print("Re-processing the stored geometry at the new accuracy...")
            prepare_geometry(geo)
            continue
        if cmd.startswith("ref"):
            geo.parts.clear()
            geo.disk = {}
            geo.version += 1
            geo.update(scan_components(model))
            print("Re-reading everything from SolidWorks...")
            prepare_geometry(geo)
            continue
        if sm.GetSelectedObjectCount2(-1) < 2:
            print("  Select 2 points/faces/vertices first.")
            continue
        p0 = tuple(sm.GetSelectionPoint2(1, -1))
        p1 = tuple(sm.GetSelectionPoint2(2, -1))
        model.ClearSelection2(True)
        dn = len(specs) + len(old) + 1
        name = input("Wire name [W%d]: " % dn).strip() or "W%d" % dn
        while name in used:
            name += "_"
        dia = ask_float("Cable diameter (mm)", last_dia)
        k = ask_float("Min bend radius = how many x diameter", last_k)
        last_dia, last_k = dia, k
        t = input("Wanted length (mm) - Enter = shortest path: ").strip()
        target = float(t) / 1000 if t else None
        sync_changes(model, geo)          # picks up any modification since last time
        spec = dict(name=name, p0=p0, p1=p1, dia=dia / 1000, k=k, target=target, geo=geo)
        print("  planning (%s)..." % ST["name"])
        t0 = time.time()
        res = plan_wire(spec, rigid_old + [(r["poly"], sp["dia"]) for r, sp in zip(results, specs)], clr)
        if res is None:
            print("  No result for %s: %s." % (name, FAIL["reason"]))
            continue
        ok = create_sketch(model, name, res["poly"])
        if not ok:
            print("  (sketch created but could not be renamed - order optimisation can't delete it)")
        describe(name, res, spec["dia"], k)
        print("  took %.1f s" % (time.time() - t0))
        specs.append(spec)
        results.append(res)
        created.append(name if ok else None)
        used.add(name)
        js = load_store(spath)
        js.append(dict(name=name, dia=spec["dia"], k=k, p0=p0, p1=p1, target=target,
                       poly=[list(q) for q in res["poly"]]))
        save_store(spath, js)

    if len(specs) >= 2:
        a = input("\nSearch for a BETTER connection order for all wires? (y/n) [n]: ").strip().lower()
        if a.startswith("y"):
            bud = ask_float("Max search time (seconds)", 120)
            print("Searching...")
            best, stats = search_orders(specs, rigid_old, clr, results, bud)
            cur = score_of(results)
            if best["order"] is None:
                print("Current order is already the best found%s." %
                      (" (search stopped by time limit)" if stats["timeout"] else ""))
            else:
                names = [specs[i]["name"] for i in best["order"]]
                bs = best["score"]
                print("Better order found: %s" % " -> ".join(names))
                print("  failed wires %d -> %d | bend problems %d -> %d | total length %.1f -> %.1f mm"
                      % (cur[0], bs[0], cur[1], bs[1], cur[2] * 1000, bs[2] * 1000))
                if input("Rebuild all wires of this session in the better order? (y/n) [n]: ").strip().lower().startswith("y"):
                    if all(created):
                        for nm in created:
                            delete_sketch(model, nm)
                        js = [w for w in load_store(spath) if w["name"] not in set(created)]
                        newres = [None] * len(specs)
                        for pos, i in enumerate(best["order"]):
                            r = best["results"][pos]
                            newres[i] = r
                            if r is None:
                                print("  %s failed in this order - skipped" % specs[i]["name"])
                                continue
                            create_sketch(model, specs[i]["name"], r["poly"])
                            js.append(dict(name=specs[i]["name"], dia=specs[i]["dia"], k=specs[i]["k"],
                                           p0=specs[i]["p0"], p1=specs[i]["p1"], target=specs[i]["target"],
                                           poly=[list(q) for q in r["poly"]]))
                        save_store(spath, js)
                        results = newres
                        print("Rebuilt.")
                    else:
                        print("Some sketches could not be renamed, so I can't delete them safely. Delete them manually.")

    print("\nSUMMARY")
    for sp, r in zip(specs, results):
        if r:
            print("  %s: %.1f mm, problems: %d" % (sp["name"], r["length"] * 1000, len(r["problems"])))
    print("Now run Evaluate > Interference Detection to double-check.")


# ---------------- server mode (used by the SolidWorks add-in; JSON lines on stdin/stdout) ----------------
def _res_json(res):
    if res is None:
        return dict(ok=False, error=FAIL["reason"])
    return dict(ok=True, poly=[list(p) for p in res["poly"]], pts=[list(p) for p in res["pts"]],
                problems=[dict(at=list(v), radius=r) for v, r in res["problems"]],
                length=res["length"], shortest=res["shortest"], note=res["note"],
                cell_mm=res["cell_mm"], level=res["level"], box_parts=res["box_parts"])


class Server:
    """Keeps the geometry cache alive between requests (no re-reading unless something changed)."""

    def __init__(self):
        self.sw = self.model = self.geo = self.path = None
        self.clr = 0.005

    def ensure(self, year=None):
        if self.sw is None:
            self.sw = connect(year)
        model = self.sw.ActiveDoc
        if model is None or model.GetType() != 2:
            raise RuntimeError("Open an assembly first.")
        base = asm_base(model)
        if self.geo is None or base != self.path:
            self.geo = GeoCache(base + "_geom.cache")
            self.geo.load_disk()
            self.path = base
        self.model = model

    def sync(self):
        a, c, r = self.geo.update(scan_components(self.model))
        info = self.geo.prepare(ST["cell"], log=lambda *x: None)
        return dict(added=a, changed=c, removed=r, read=info["read"], prep=info["prep"])

    def spec(self, req):
        t = req.get("target")
        return dict(p0=tuple(req["p0"]), p1=tuple(req["p1"]), dia=float(req["dia"]), k=float(req["k"]),
                    target=float(t) if t else None, geo=self.geo)

    def handle(self, req):
        cmd = req.get("cmd")
        if cmd in ("ping", "shutdown"):
            return dict(ok=True)
        if "clearance_mm" in req:
            self.clr = float(req["clearance_mm"]) / 1000.0
        if cmd in ("init", "accuracy") and ("level" in req or "custom_mm" in req):
            set_level(int(req.get("level") or 3), req.get("custom_mm") or None)
        self.ensure(req.get("year"))
        if cmd in ("init", "accuracy", "sync"):
            ch = self.sync()
            n, tr, vox, box = self.geo.summary()
            return dict(ok=True, components=n, triangles=tr, box_parts=box[:20], accuracy=ST["name"],
                        cell_mm=ST["cell"] * 1000, **ch)
        if cmd == "refresh":
            self.geo.parts.clear()
            self.geo.disk = {}
            self.geo.version += 1
            return dict(ok=True, **self.sync())
        rigid = [([tuple(p) for p in r["poly"]], float(r["dia"])) for r in req.get("rigid", [])]
        if cmd == "plan":
            self.sync()
            return _res_json(plan_wire(self.spec(req), rigid, self.clr))
        if cmd == "review":
            self.sync()
            routes, out = req.get("routes", []), []
            for i, r in enumerate(routes):
                others = [([tuple(p) for p in o["poly"]], float(o["dia"])) for j, o in enumerate(routes) if j != i]
                cur = poly_length([tuple(p) for p in r["poly"]])
                spec = dict(p0=tuple(r["p0"]), p1=tuple(r["p1"]), dia=float(r["dia"]), k=float(r["k"]),
                            target=None, geo=self.geo)
                res = plan_wire(spec, others + rigid, self.clr)
                if res is None:
                    out.append(dict(name=r["name"], current=cur, ok=False, error=FAIL["reason"]))
                    continue
                saving = cur - res["length"]
                out.append(dict(name=r["name"], current=cur, best=res["length"], saving=saving,
                                problems=len(res["problems"]),
                                suggest=bool(saving > max(0.02 * cur, 0.005) and not res["problems"]),
                                pts=[list(p) for p in res["pts"]], poly=[list(p) for p in res["poly"]]))
            return dict(ok=True, results=out)
        return dict(ok=False, error="unknown command: %s" % cmd)


def serve(stdin=None, stdout=None):
    real_out = stdout or sys.stdout
    sys.stdout = sys.stderr          # engine prints must never pollute the JSON channel
    srv = Server()
    for line in (stdin or sys.stdin):
        line = line.strip()
        if not line:
            continue
        rid = None
        try:
            req = json.loads(line)
            rid = req.get("id")
            resp = srv.handle(req)
        except Exception as e:
            import traceback
            traceback.print_exc()
            resp = dict(ok=False, error=str(e))
        resp["id"] = rid
        real_out.write(json.dumps(resp) + "\n")
        real_out.flush()
        if rid is not None and req.get("cmd") == "shutdown":
            break


if __name__ == "__main__":
    if "--server" in sys.argv:
        serve()
    else:
        main()
