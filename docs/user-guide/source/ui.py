from PIL import Image, ImageDraw, ImageFont
S = 2
FR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FB = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FM = "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"
_cache = {}
def font(size, bold=False, mono=False):
    k = (size, bold, mono)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(FM if mono else (FB if bold else FR), int(round(size * S)))
    return _cache[k]

class Canvas:
    def __init__(self, w, h, bg=(255, 255, 255)):
        self.w, self.h = w, h
        self.im = Image.new("RGB", (w * S, h * S), bg)
        self.d = ImageDraw.Draw(self.im)
    def _b(self, x, y, w, h): return [x * S, y * S, (x + w) * S, (y + h) * S]
    def rect(self, x, y, w, h, fill=None, outline=None, width=1, r=0):
        if r: self.d.rounded_rectangle(self._b(x, y, w, h), radius=r * S, fill=fill, outline=outline, width=int(width * S))
        else: self.d.rectangle(self._b(x, y, w, h), fill=fill, outline=outline, width=int(width * S))
    def ell(self, x, y, w, h, fill=None, outline=None, width=1):
        self.d.ellipse(self._b(x, y, w, h), fill=fill, outline=outline, width=int(width * S))
    def line(self, pts, fill=(0, 0, 0), width=1):
        self.d.line([(px * S, py * S) for px, py in pts], fill=fill, width=int(width * S), joint="curve")
    def dashed(self, a, b, fill, width=1.5, dash=7, gap=5):
        import math
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L == 0: return
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        t = 0.0
        while t < L:
            e = min(L, t + dash)
            self.line([(a[0] + ux * t, a[1] + uy * t), (a[0] + ux * e, a[1] + uy * e)], fill, width)
            t += dash + gap
    def text(self, x, y, s, size=12, fill=(0, 0, 0), bold=False, mono=False, anchor="la"):
        self.d.text((x * S, y * S), s, font=font(size, bold, mono), fill=fill, anchor=anchor)
    def tw(self, s, size=12, bold=False, mono=False):
        return self.d.textlength(s, font=font(size, bold, mono)) / S
    def poly(self, pts, fill=None, outline=None):
        self.d.polygon([(px * S, py * S) for px, py in pts], fill=fill, outline=outline)
    def save(self, path):
        self.im.resize((self.w, self.h), Image.LANCZOS).save(path)

def window(c, x, y, w, h, title, body=(240, 240, 240)):
    c.rect(x + 3, y + 3, w, h, fill=(205, 205, 205))                      # shadow
    c.rect(x, y, w, h, fill=body, outline=(100, 100, 100))
    c.rect(x, y, w, 30, fill=(255, 255, 255), outline=(100, 100, 100))
    c.text(x + 10, y + 8, title, 12, (0, 0, 0))
    c.text(x + w - 22, y + 5, "x", 15, (60, 60, 60))

def button(c, x, y, w, h, label, default=False, size=12):
    c.rect(x, y, w, h, fill=(225, 225, 225), outline=(0, 120, 215) if default else (173, 173, 173), width=2 if default else 1)
    c.text(x + w / 2, y + h / 2, label, size, anchor="mm")

def textbox(c, x, y, w, h, s="", size=12, fill=(255, 255, 255)):
    c.rect(x, y, w, h, fill=fill, outline=(122, 122, 122))
    if s: c.text(x + 5, y + h / 2, s, size, anchor="lm")

def label(c, x, y, s, size=12, fill=(0, 0, 0), bold=False):
    c.text(x, y, s, size, fill, bold)

def checkbox(c, x, y, on):
    c.rect(x, y, 14, 14, fill=(255, 255, 255), outline=(60, 60, 60))
    if on: c.line([(x + 3, y + 7), (x + 6, y + 11), (x + 12, y + 3)], (0, 90, 180), 2)

def callout(c, x, y, n, r=11):
    c.ell(x - r, y - r, 2 * r, 2 * r, fill=(220, 38, 38), outline=(255, 255, 255), width=1.5)
    c.text(x, y, str(n), 13, (255, 255, 255), True, anchor="mm")

def combo(c, x, y, w, h, s):
    textbox(c, x, y, w, h, s)
    c.rect(x + w - 22, y + 1, 21, h - 2, fill=(235, 235, 235))
    c.poly([(x + w - 16, y + h / 2 - 2), (x + w - 6, y + h / 2 - 2), (x + w - 11, y + h / 2 + 4)], fill=(60, 60, 60))

def msgbox(c, x, y, w, h, title, lines, buttons, size=12, icon="i"):
    window(c, x, y, w, h, title, body=(255, 255, 255))
    c.rect(x + 1, y + h - 52, w - 2, 51, fill=(240, 240, 240))
    col = {"i": (0, 120, 215), "w": (230, 160, 0), "q": (0, 120, 215)}[icon]
    c.ell(x + 16, y + 46, 32, 32, fill=col)
    c.text(x + 32, y + 62, {"i": "i", "w": "!", "q": "?"}[icon], 20, (255, 255, 255), True, anchor="mm")
    ty = y + 44
    for ln in lines:
        bold = ln.startswith("**")
        c.text(x + 64, ty, ln.strip("*"), size, bold=bold, mono=False)
        ty += size + 6
    bx = x + w - 12
    for b in reversed(buttons):
        bw = 78
        bx -= bw
        button(c, bx, y + h - 40, bw, 28, b, default=(b == buttons[0]))
        bx -= 8
