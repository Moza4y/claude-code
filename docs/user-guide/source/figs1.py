from ui import *
import math, json

IMG = "/tmp/guide/img/"
ICON = [("S", (0, 120, 215)), ("R", (90, 90, 90)), ("V", (16, 137, 62)), ("A", (200, 120, 0)), ("W", (142, 68, 173)), ("U", (0, 150, 160))]
NAMES = ["Smart Auto Route", "Scan Routes", "Review Routes", "Accuracy", "Auto Watch", "Updates"]

# ---------------------------------------------------------------- fig 1: the tab
def fig_tab():
    c = Canvas(1000, 200, (255, 255, 255))
    c.rect(0, 0, 1000, 200, fill=(250, 250, 250))
    tabs = ["Assembly", "Layout", "Sketch", "Markup", "Evaluate", "SOLIDWORKS Add-Ins", "Routing", "Smart Route"]
    x = 14
    for t in tabs:
        w = c.tw(t, 13) + 26
        act = (t == "Smart Route")
        c.rect(x, 12 if act else 18, w, 34 if act else 28, fill=(255, 255, 255) if act else (232, 232, 232), outline=(150, 150, 150))
        c.text(x + w / 2, 30 if act else 32, t, 13, (0, 90, 180) if act else (40, 40, 40), act, anchor="mm")
        x += w + 2
    c.rect(0, 46, 1000, 150, fill=(255, 255, 255), outline=(150, 150, 150))
    bx = 40
    for i, ((ch, col), nm) in enumerate(zip(ICON, NAMES)):
        c.ell(bx + 14, 66, 56, 56, fill=col)
        c.text(bx + 42, 94, ch, 30, (255, 255, 255), True, anchor="mm")
        c.text(bx + 42, 140, nm, 13, (30, 30, 30), anchor="mm")
        callout(c, bx + 42, 164 + 8, i + 1)
        bx += 150
    c.save(IMG + "fig_tab.png")

# ---------------------------------------------------------------- fig 2: Add-Ins dialog
def fig_addins():
    c = Canvas(640, 380, (255, 255, 255))
    window(c, 10, 10, 610, 355, "Add-Ins")
    c.rect(24, 52, 580, 24, fill=(225, 230, 240), outline=(160, 160, 160))
    c.text(40, 58, "Active Add-ins and Add-in Options", 12, bold=True)
    c.text(470, 58, "Active", 12, bold=True)
    c.text(540, 58, "Start Up", 12, bold=True)
    rows = [("SOLIDWORKS Premium Add-ins", None, None, True), ("SOLIDWORKS Routing", True, True, False), ("SOLIDWORKS Toolbox", False, False, False),
            ("SOLIDWORKS Simulation", False, False, False), ("Other Add-ins", None, None, True), ("Smart Route", True, True, False)]
    y = 82
    for nm, a, s, hdr in rows:
        if hdr:
            c.rect(24, y, 580, 24, fill=(238, 238, 238))
            c.text(34, y + 5, nm, 12, bold=True)
        else:
            hl = (nm == "Smart Route")
            c.rect(24, y, 580, 28, fill=(204, 228, 247) if hl else (255, 255, 255), outline=(215, 215, 215))
            c.text(52, y + 7, nm, 12, bold=hl)
            checkbox(c, 478, y + 7, a)
            checkbox(c, 556, y + 7, s)
        y += 28 if not hdr else 24
    button(c, 410, 322, 90, 28, "OK", True)
    button(c, 512, 322, 90, 28, "Cancel")
    callout(c, 600, 258, 1)      # Smart Route
    callout(c, 600, 138, 2)      # Routing
    c.save(IMG + "fig_addins.png")

# ---------------------------------------------------------------- fig 3: installer wizard
def wizard(c, x, y, title, head, lines, btn, back=True, w=460, h=330, sub=None):
    window(c, x, y, w, h, "Setup - Smart Route for SOLIDWORKS")
    c.rect(x + 1, y + 31, w - 2, h - 32 - 52, fill=(255, 255, 255))
    c.rect(x + 1, y + h - 52, w - 2, 51, fill=(240, 240, 240))
    c.text(x + 24, y + 48, head, 15, (0, 60, 130), True)
    if sub: c.text(x + 24, y + 72, sub, 11, (90, 90, 90))
    yy = y + 100
    for ln in lines:
        c.text(x + 24, yy, ln, 12); yy += 20
    bx = x + w - 14
    for b in reversed(btn):
        bw = 86; bx -= bw
        button(c, bx, y + h - 40, bw, 28, b, default=(b == btn[0])); bx -= 8

def fig_installer():
    c = Canvas(980, 720, (255, 255, 255))
    wizard(c, 10, 10, "", "Welcome to the Smart Route Setup Wizard",
           ["This will install Smart Route 0.3.0 on your computer.", "", "It is recommended that you close SOLIDWORKS", "before continuing.", "", "Click Next to continue, or Cancel to exit Setup."], ["Next >", "Cancel"])
    wizard(c, 500, 10, "", "Select Destination Location", ["Where should Smart Route be installed?", "", "Setup will install it into the following folder:"],
           ["Next >", "< Back", "Cancel"], sub="Choose the folder (the default is fine).")
    textbox(c, 524, 186, 300, 26, "C:\\Program Files\\SmartRoute")
    button(c, 832, 186, 90, 26, "Browse...")
    wizard(c, 10, 360, "", "Ready to Install", ["Setup is now ready to begin installing Smart Route", "on your computer.", "", "Click Install to continue."], ["Install", "< Back", "Cancel"])
    wizard(c, 500, 360, "", "Completing the Smart Route Setup Wizard", ["Smart Route has been installed.", "", "Start SOLIDWORKS, then: Tools > Add-Ins >", "tick Smart Route (and SOLIDWORKS Routing).", "", "Click Finish to exit Setup."], ["Finish"])
    callout(c, 260, 10 + 330 - 52, 1)       # Next
    callout(c, 720, 10 + 330 - 52, 2)       # Next
    callout(c, 220, 360 + 330 - 52, 3)      # Install
    callout(c, 930, 360 + 330 - 52, 4)      # Finish
    c.save(IMG + "fig_installer.png")

# ---------------------------------------------------------------- isometric helpers
def iso(x, y, z, ox, oy, s):
    return (ox + (x - y) * math.cos(math.radians(30)) * s, oy + (x + y) * math.sin(math.radians(30)) * s - z * s)

def iso_box(c, x0, y0, z0, x1, y1, z1, ox, oy, s, top=(235, 235, 235), left=(190, 190, 195), right=(210, 210, 215), outline=(90, 90, 90)):
    P = lambda x, y, z: iso(x, y, z, ox, oy, s)
    c.poly([P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)], fill=left, outline=outline)     # front-left face
    c.poly([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], fill=right, outline=outline)    # front-right face
    c.poly([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], fill=top, outline=outline)

def fig_select():
    c = Canvas(900, 520, (255, 255, 255))
    c.rect(0, 0, 900, 520, fill=(246, 248, 252))
    c.rect(0, 0, 900, 38, fill=(0, 120, 215))
    c.text(14, 10, "Edit Route  -  Route1^Assem1 (the route's 3D sketch is active)", 14, (255, 255, 255), True)
    ox, oy, s = 450, 262, 112
    iso_box(c, -1.6, -0.9, -0.15, 1.6, 0.9, 0.0, ox, oy, s, top=(225, 232, 240), left=(180, 190, 205), right=(200, 208, 220))   # base plate
    iso_box(c, -1.4, -0.6, 0.0, -0.6, 0.6, 0.55, ox, oy, s, top=(120, 160, 205), left=(80, 120, 170), right=(100, 140, 190))       # box A
    iso_box(c, -0.12, -0.8, 0.0, 0.12, 0.8, 0.95, ox, oy, s, top=(190, 190, 190), left=(150, 150, 150), right=(170, 170, 170))   # wall
    iso_box(c, 0.6, -0.6, 0.0, 1.4, 0.6, 0.55, ox, oy, s, top=(120, 160, 205), left=(80, 120, 170), right=(100, 140, 190))        # box B
    iso_box(c, -1.15, -0.1, 0.55, -0.95, 0.1, 0.7, ox, oy, s, top=(40, 40, 40), left=(25, 25, 25), right=(35, 35, 35))             # connector A
    iso_box(c, 0.95, -0.1, 0.55, 1.15, 0.1, 0.7, ox, oy, s, top=(40, 40, 40), left=(25, 25, 25), right=(35, 35, 35))              # connector B
    A, B = iso(-1.05, 0, 0.7, ox, oy, s), iso(1.05, 0, 0.7, ox, oy, s)
    c.dashed(A, B, (230, 120, 0), 3, 10, 6)
    for (px, py), n, nm, dx in ((A, 1, "Point 1 (start)", -150), (B, 2, "Point 2 (end)", 20)):
        c.ell(px - 9, py - 9, 18, 18, fill=(0, 120, 215), outline=(255, 255, 255), width=2)
        callout(c, px, py - 30, n)
        c.text(px + dx, py + 14, nm, 14, (0, 70, 150), True)
    c.text(450, 470, "Hold Ctrl to pick the second point.  Both points are in the route's 3D sketch.", 14, (60, 60, 60), anchor="mm")
    c.text(450, 492, "Orange dashed line = the straight link Routing would draw (through the wall). Smart Route plans around it.", 13, (120, 80, 0), anchor="mm")
    c.save(IMG + "fig_select.png")

if __name__ == "__main__":
    fig_tab(); fig_addins(); fig_installer(); fig_select()
    print("ok")
