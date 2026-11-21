from ui import *
import json, math
IMG = "/tmp/guide/img/"

# ---------------------------------------------------------------- Smart Auto Route dialog (same layout as RouteDialog)
def fig_dialog():
    c = Canvas(430, 270, (255, 255, 255))
    window(c, 15, 10, 400, 245, "Smart Auto Route")
    rows = [("Wire name", "W143012"), ("Cable diameter (mm)", "5"), ("Min bend radius (mm)", "30"),
            ("Wanted length (mm)", ""), ("Safety clearance (mm)", "5")]
    y = 14 + 30
    for i, (lab, val) in enumerate(rows):
        c.text(27, y + 3, lab, 12)
        textbox(c, 225 + 15 - 15, y, 150, 22, val)
        callout(c, 395, y + 11, i + 1)
        y += 30
    button(c, 225, y + 8, 70, 26, "Route", True)
    button(c, 305, y + 8, 70, 26, "Cancel")
    callout(c, 225 - 14, y + 21, 6)
    c.text(27, y + 14, "(empty length = shortest)", 10.5, (110, 110, 110))
    c.save(IMG + "fig_dialog.png")

# ---------------------------------------------------------------- Preview window with REAL engine data
def fig_preview():
    D = json.load(open('/tmp/guide/scene.json'))
    alts, sc = D['alternatives'], D['scene']
    W, H = 1000, 640
    c = Canvas(W, H, (255, 255, 255))
    window(c, 10, 10, 980, 620, "Smart Route - W143012 (Normal, cell 5.0 mm)")
    vx, vy, vw, vh = 22, 50, 640, 520
    v = Canvas(vw, vh, (255, 255, 255))
    allp = [p for a in alts for p in a['poly']]
    lo = [min(p[i] for p in allp) for i in range(3)]; hi = [max(p[i] for p in allp) for i in range(3)]
    cen = [(lo[i] + hi[i]) / 2 for i in range(3)]
    diag = math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3)))
    yaw, pitch = 0.75, 0.42
    scale = min(vw, vh) / (diag * 1.35) * 1.75
    def P(p):
        x, y, z = p[0] - cen[0], p[1] - cen[1], p[2] - cen[2]
        cy, sy_, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
        x1 = x * cy + z * sy_; z1 = -x * sy_ + z * cy
        y2 = y * cp - z1 * sp
        return (vw / 2 + x1 * scale, vh / 2 - y2 * scale)
    for q in sc['cloud']:
        x, y = P(q); v.rect(x, y, 1.8, 1.8, fill=(190, 190, 190))
    def box(b):
        vv = [[b[0] if i & 1 == 0 else b[3], b[1] if i & 2 == 0 else b[4], b[2] if i & 4 == 0 else b[5]] for i in range(8)]
        for a_, b_ in [(0,1),(2,3),(4,5),(6,7),(0,2),(1,3),(4,6),(5,7),(0,4),(1,5),(2,6),(3,7)]:
            v.line([P(vv[a_]), P(vv[b_])], (205, 205, 205), 1)
    for b in sc['boxes']: box(b)
    cols = [(0, 120, 215), (16, 137, 62), (200, 120, 0)]
    sel = 0
    for i, a in enumerate(alts):
        if i == sel: continue
        pts = [P(p) for p in a['poly']]
        for a_, b_ in zip(pts, pts[1:]): v.dashed(a_, b_, cols[i], 2, 8, 5)
    pts = [P(p) for p in alts[sel]['poly']]
    v.line(pts, cols[sel], 4.5)
    s_, e_ = pts[0], pts[-1]
    v.ell(s_[0] - 7, s_[1] - 7, 14, 14, fill=(16, 160, 60)); v.ell(e_[0] - 7, e_[1] - 7, 14, 14, fill=(220, 30, 30))
    v.text(8, vh - 20, "drag: rotate   wheel: zoom   right-drag: pan   double-click: reset", 11, (120, 120, 120))
    c.im.paste(v.im, (vx * S, vy * S))
    c.rect(vx, vy, vw, vh, outline=(120, 120, 120))
    # right panel
    rx = 676
    c.rect(rx, 50, 300, 190, fill=(255, 255, 255), outline=(150, 150, 150))
    c.rect(rx, 50, 300, 22, fill=(240, 240, 240), outline=(200, 200, 200))
    c.text(rx + 8, 55, "Alternative", 11, bold=True); c.text(rx + 150, 55, "Length", 11, bold=True); c.text(rx + 222, 55, "Status", 11, bold=True)
    for i, a in enumerate(alts):
        yy = 74 + i * 22
        if i == sel: c.rect(rx + 1, yy, 298, 22, fill=(204, 228, 247))
        c.text(rx + 8, yy + 4, a['label'], 11)
        c.text(rx + 150, yy + 4, "%d mm" % round(a['length'] * 1000), 11)
        c.text(rx + 222, yy + 4, "OK", 11)
    a = alts[sel]; ck = a['check']
    det = ["%s  (smooth curve route)" % a['label'], "",
           "Length %.1f mm   |   bends %d" % (a['length'] * 1000, len(a['pts']) - 2),
           "min bend radius %.0f mm (need %.0f)" % (ck['min_radius'] * 1000, ck['radius_required'] * 1000),
           "min clearance %.1f mm" % (ck['min_clearance'] * 1000),
           "collisions %d  |  tight spots %d  |  bend problems %d" % (len(ck['collisions']), len(ck['tight']), len(ck['bend_violations'])), "",
           "Green dot = start, red dot = end.", "Dashed = the other alternatives.", "Grey dots/boxes = real geometry nearby."]
    yy = 256
    for ln in det:
        c.text(rx + 2, yy, ln, 11.5, (0, 0, 0)); yy += 19
    button(c, rx, 578, 140, 34, "Create route", True)
    button(c, rx + 152, 578, 148, 34, "Cancel")
    callout(c, vx + 20, vy + 22, 1); callout(c, rx + 286, 62, 2); callout(c, rx + 286, 256, 3); callout(c, rx - 14, 595, 4)
    c.save(IMG + "fig_preview.png")

# ---------------------------------------------------------------- verification message
def fig_after():
    D = json.load(open('/tmp/guide/scene.json')); a = D['alternatives'][0]; ck = a['check']
    lines = ["Route created through %d points, flexible (smooth) mode" % len(a['pts']), "(Routing status code 0). Ctrl+Z undoes it.", "",
             "VERIFICATION of the created route (Route1^Assem1/3DSketch1):",
             "  length %.1f mm" % (a['length'] * 1000),
             "  min bend radius %.1f mm (need %.1f) -> OK" % (ck['min_radius'] * 1000, ck['radius_required'] * 1000),
             "  min clearance to real geometry %.1f mm -> OK" % (ck['min_clearance'] * 1000),
             "SOLIDWORKS interference check: 0 interference(s) in the assembly,", "0 involving the new route."]
    c = Canvas(640, 330, (255, 255, 255))
    msgbox(c, 10, 8, 620, 312, "Smart Route", lines, ["OK"], 12)
    callout(c, 628, 82, 1); callout(c, 628, 114, 2); callout(c, 628, 132, 3); callout(c, 628, 160, 4)
    c.save(IMG + "fig_after.png")

def fig_after_bad():
    lines = ["Route created through 6 points, flexible (smooth) mode", "(Routing status code 0). Ctrl+Z undoes it.", "",
             "VERIFICATION of the created route (Route1^Assem1/3DSketch1):",
             "  length 1337.2 mm",
             "  min bend radius 22.4 mm (need 40.0) -> 1 problem spot(s)",
             "    bend at (412.0, 188.5, 12.0) mm: radius 22.4 mm",
             "  min clearance to real geometry -3.1 mm -> 1 COLLISION(S)",
             "    collision at (455.0, 301.2, 0.0) mm",
             "SOLIDWORKS interference check: 3 interference(s) in the assembly,", "1 involving the new route."]
    c = Canvas(640, 368, (255, 255, 255))
    msgbox(c, 10, 8, 620, 350, "Smart Route", lines, ["OK"], 12, icon="w")
    c.save(IMG + "fig_after_bad.png")

# ---------------------------------------------------------------- accuracy dialog
def fig_accuracy():
    c = Canvas(420, 215, (255, 255, 255))
    window(c, 15, 10, 390, 195, "Smart Route - accuracy")
    c.text(27, 54, "Accuracy level", 12); combo(c, 165, 50, 225, 24, "3 - Normal  (cell 5 mm)")
    c.text(27, 88, "or custom cell size (mm)", 12); textbox(c, 165, 84, 225, 24, "")
    c.text(27, 118, "Higher = slower but more exact. Stored geometry is", 11, (60, 60, 60))
    c.text(27, 134, "re-processed, not re-read from SOLIDWORKS.", 11, (60, 60, 60))
    button(c, 225, 164, 80, 28, "OK", True); button(c, 315, 164, 80, 28, "Cancel")
    callout(c, 400, 62, 1); callout(c, 400, 96, 2)
    c.save(IMG + "fig_accuracy.png")

# ---------------------------------------------------------------- review window
def fig_review():
    c = Canvas(600, 300, (255, 255, 255))
    window(c, 10, 10, 580, 275, "Smart Route - suggestions")
    c.rect(22, 50, 556, 150, fill=(255, 255, 255), outline=(150, 150, 150))
    c.rect(22, 50, 556, 22, fill=(240, 240, 240), outline=(200, 200, 200))
    for x, t in ((30, "Route"), (282, "Current"), (372, "Suggested"), (462, "Saving")): c.text(x, 55, t, 11, bold=True)
    rows = [("Harness1^Assem1/3DSketch1", "520.0 mm", "470.4 mm", "9.5 %"), ("Harness2^Assem1/3DSketch1", "845.2 mm", "801.9 mm", "5.1 %")]
    for i, r in enumerate(rows):
        yy = 74 + i * 22
        if i == 0: c.rect(23, yy, 554, 22, fill=(204, 228, 247))
        for x, t in zip((30, 282, 372, 462), r): c.text(x, yy + 4, t, 11.5)
    button(c, 22, 226, 215, 30, "Draw selected as 3D sketch"); button(c, 497, 226, 80, 30, "Close")
    callout(c, 560, 62, 1); callout(c, 250, 241, 2)
    c.save(IMG + "fig_review.png")

# ---------------------------------------------------------------- update message
def fig_update():
    lines = ["Smart Route v0.4.0 is available (installed: 0.3.0).", "", "- Faster planning in large assemblies", "- Better preview", "",
             "Download it now and install it automatically", "when SOLIDWORKS is closed?"]
    c = Canvas(560, 260, (255, 255, 255))
    msgbox(c, 10, 8, 540, 242, "Smart Route update", lines, ["Yes", "No"], 12, icon="q")
    c.save(IMG + "fig_update.png")

# ---------------------------------------------------------------- workflow flowchart
def fig_flow():
    steps = [("1", "Start / edit the\nroute (Routing)"), ("2", "Select the two\nend points"), ("3", "Click\nSmart Auto Route"), ("4", "Enter wire data\n(diameter, bend...)"),
             ("5", "Preview the\nalternatives"), ("6", "Create route"), ("7", "Read the\nverification report")]
    c = Canvas(1000, 250, (255, 255, 255))
    xs = [24 + i * 138 for i in range(7)]
    for i, ((n, t), x) in enumerate(zip(steps, xs)):
        col = [(0, 120, 215)] * 5 + [(16, 137, 62), (142, 68, 173)]
        c.rect(x, 70, 118, 110, fill=(245, 248, 253), outline=col[i], width=2, r=10)
        c.ell(x + 44, 50, 30, 30, fill=col[i])
        c.text(x + 59, 65, n, 15, (255, 255, 255), True, anchor="mm")
        yy = 112
        for ln in t.split("\n"):
            c.text(x + 59, yy, ln, 12, (30, 30, 30), anchor="mm"); yy += 18
        if i < 6:
            c.line([(x + 120, 125), (x + 136, 125)], (90, 90, 90), 2)
            c.poly([(x + 136, 119), (x + 144, 125), (x + 136, 131)], fill=(90, 90, 90))
    c.text(500, 215, "Cancel at step 5 = nothing is created.   Ctrl+Z after step 6 undoes the route.", 13, (90, 90, 90), anchor="mm")
    c.save(IMG + "fig_flow.png")

if __name__ == "__main__":
    fig_dialog(); fig_preview(); fig_after(); fig_after_bad(); fig_accuracy(); fig_review(); fig_update(); fig_flow()
    print("ok")
