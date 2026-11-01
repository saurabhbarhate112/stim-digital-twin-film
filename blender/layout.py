"""Board layout shared by the texture baker and the Blender scene.

Everything is in millimetres on a 100 x 70 mm, 1.6 mm thick four-corner board,
origin at the board centre, seeded so the board is identical on every render.
"""
import math
import random

BOARD_W, BOARD_H, BOARD_T = 100.0, 70.0, 1.6

# Real package dimensions: body (w, d, h), terminal length.
CHIP = {
    "0402": (1.0, 0.5, 0.45, 0.25),
    "0603": (1.6, 0.8, 0.55, 0.3),
    "0805": (2.0, 1.25, 0.7, 0.4),
    "1206": (3.2, 1.6, 0.9, 0.5),
}


def chip_pads(pkg, x, y, rot):
    w, d, _, t = CHIP[pkg]
    pw, pd = t + 0.45, d + 0.2
    off = w / 2 - t / 2 + 0.1
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    return [{"x": x + c * o, "y": y + s * o, "w": pw, "h": pd, "rot": rot} for o in (-off, off)]


def qfn_pads(x, y, n_side=8, pitch=0.5, body=5.0):
    pads = []
    span = (n_side - 1) * pitch
    edge = body / 2 - 0.2
    for i in range(n_side):
        o = -span / 2 + i * pitch
        pads.append({"x": x + o, "y": y - edge - 0.1, "w": 0.28, "h": 0.8, "rot": 0})
        pads.append({"x": x + o, "y": y + edge + 0.1, "w": 0.28, "h": 0.8, "rot": 0})
        pads.append({"x": x - edge - 0.1, "y": y + o, "w": 0.8, "h": 0.28, "rot": 0})
        pads.append({"x": x + edge + 0.1, "y": y + o, "w": 0.8, "h": 0.28, "rot": 0})
    pads.append({"x": x, "y": y, "w": 3.3, "h": 3.3, "rot": 0, "thermal": True})
    return pads


def gull_pads(x, y, n, pitch, span, sides=2):
    """SOIC (sides=2) and TQFP (sides=4) land patterns; n is pins per side."""
    pads = []
    o0 = -(n - 1) * pitch / 2
    for i in range(n):
        o = o0 + i * pitch
        pads.append({"x": x + o, "y": y - span / 2, "w": pitch * 0.55, "h": 1.5, "rot": 0})
        pads.append({"x": x + o, "y": y + span / 2, "w": pitch * 0.55, "h": 1.5, "rot": 0})
        if sides == 4:
            pads.append({"x": x - span / 2, "y": y + o, "w": 1.5, "h": pitch * 0.55, "rot": 0})
            pads.append({"x": x + span / 2, "y": y + o, "w": 1.5, "h": pitch * 0.55, "rot": 0})
    return pads


def build():
    rng = random.Random(4812)
    parts, pads = [], []

    def add(kind, ref, x, y, rot=0, plist=(), **kw):
        parts.append({"kind": kind, "ref": ref, "x": x, "y": y, "rot": rot, **kw})
        for p in plist:
            pads.append({**p, "ref": ref})

    # The QFN from the story sits in the lower-right corner, the drifting stencil zone.
    add("qfn", "U1", 31.0, -20.0, plist=qfn_pads(31.0, -20.0))
    add("tqfp", "U2", -6.0, 6.0, n=12, pitch=0.8, body=10.0, span=12.6,
        plist=gull_pads(-6.0, 6.0, 12, 0.8, 12.6, 4))
    add("soic", "U3", 24.0, 14.0, n=4, pitch=1.27, body=(4.9, 3.9), span=5.6,
        plist=gull_pads(24.0, 14.0, 4, 1.27, 5.6))
    add("soic", "U4", -28.0, -16.0, n=4, pitch=1.27, body=(4.9, 3.9), span=5.6,
        plist=gull_pads(-28.0, -16.0, 4, 1.27, 5.6))
    add("soic", "U5", 8.0, -19.0, n=7, pitch=1.27, body=(8.65, 3.9), span=5.6,
        plist=gull_pads(8.0, -19.0, 7, 1.27, 5.6))
    add("crystal", "Y1", -6.0, -8.0, plist=[{"x": -6 + sx * 1.1, "y": -8 + sy * 0.85, "w": 1.2, "h": 0.9, "rot": 0}
                                            for sx in (-1, 1) for sy in (-1, 1)])
    add("inductor", "L1", 36.0, 8.0, plist=[{"x": 36 + s * 3.6, "y": 8, "w": 2.2, "h": 4.0, "rot": 0} for s in (-1, 1)])
    add("elco", "C1", 37.0, 23.0, r=4.0, h=7.7, plist=[{"x": 37 + s * 3.0, "y": 23, "w": 3.0, "h": 1.4, "rot": 0} for s in (-1, 1)])
    add("elco", "C2", -38.0, 22.0, r=3.15, h=5.4, plist=[{"x": -38 + s * 2.6, "y": 22, "w": 2.6, "h": 1.2, "rot": 0} for s in (-1, 1)])
    add("usbc", "J1", -45.0, -1.0, rot=0, plist=[{"x": -41.0, "y": -1 + i * 0.5 - 2.75, "w": 1.2, "h": 0.3, "rot": 0} for i in range(12)])
    add("header", "J2", 45.0, -2.0, n=6, plist=[{"x": 45.0, "y": -2 + (i - 2.5) * 2.54, "w": 1.6, "h": 1.6, "rot": 0, "round": True} for i in range(6)])

    def ring(cx, cy, r, count, pkg, prefix, start=0.0):
        for i in range(count):
            a = start + i / count * math.tau
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            rot = 90 * (round(math.degrees(a) / 90) % 2)
            add("chip", f"{prefix}{i}", round(x, 2), round(y, 2), rot, chip_pads(pkg, x, y, rot),
                pkg=pkg, tone="cap" if i % 3 else "res")

    ring(31.0, -20.0, 7.6, 8, "0402", "CQ", 0.39)
    ring(-6.0, 6.0, 11.5, 12, "0402", "CM", 0.26)
    ring(24.0, 14.0, 6.6, 4, "0603", "CS", 0.78)

    # Passive banks: the dense regular rows that make a board read as real.
    def bank(x0, y0, nx, ny, dx, dy, pkg, prefix):
        for j in range(ny):
            for i in range(nx):
                x, y = x0 + i * dx, y0 + j * dy
                rot = 0 if dx > dy else 90
                add("chip", f"{prefix}{j}{i}", x, y, rot, chip_pads(pkg, x, y, rot), pkg=pkg,
                    tone="res" if rng.random() < 0.55 else "cap")

    bank(-44.0, -29.0, 7, 2, 3.1, 3.2, "0603", "RA")
    bank(-20.0, -29.0, 6, 2, 3.4, 3.2, "0805", "RB")
    bank(12.0, 27.0, 5, 1, 3.4, 3.0, "0603", "RC")
    bank(-26.0, 27.0, 8, 1, 3.2, 3.0, "0402", "RD")
    bank(8.0, 1.0, 2, 4, 3.0, 2.4, "0603", "RE")
    bank(-30.0, 2.0, 2, 5, 2.6, 2.6, "0402", "RF")
    bank(14.0, -6.0, 6, 1, 3.2, 3.0, "1206", "RG")

    for i in range(3):
        x = -24 + i * 9
        add("led", f"D{i}", x, -8.0, 0, chip_pads("0603", x, -8.0, 0), pkg="0603", tone="led")

    # Secondary silicon: small regulators, drivers and protection parts.
    for i, (x, y) in enumerate(((-15.0, 22.0), (2.0, 21.0), (17.0, 22.0), (-34.0, 11.0), (20.0, -28.0), (-8.0, -22.0))):
        add("sot", f"Q{i}", x, y, plist=[{"x": x - 0.95, "y": y - 1.1, "w": 0.6, "h": 0.8, "rot": 0},
                                         {"x": x + 0.95, "y": y - 1.1, "w": 0.6, "h": 0.8, "rot": 0},
                                         {"x": x, "y": y + 1.1, "w": 0.6, "h": 0.8, "rot": 0}])
    for i, (x, y) in enumerate(((-33.0, -4.0), (3.0, -29.0), (40.0, -10.0))):
        add("qfn", f"U{6 + i}", x, y, small=True, plist=qfn_pads(x, y, 4, 0.5, 3.0))
    for i, y in enumerate((-12.0, 16.0)):
        add("switch", f"SW{i}", -42.0, y, plist=[{"x": -42 + a * 3.0, "y": y + b * 1.8, "w": 1.2, "h": 1.0, "rot": 0}
                                                 for a in (-1, 1) for b in (-1, 1)])

    # Fill free board space with decoupling, the density that makes a board read as real.
    def clear(x, y, r):
        for p in pads:
            if abs(p["x"] - x) < r + p["w"] / 2 and abs(p["y"] - y) < r + p["h"] / 2:
                return False
        for part in parts:
            if part["kind"] in ("inductor", "elco", "usbc", "tqfp", "soic", "header") and math.hypot(part["x"] - x, part["y"] - y) < 7.5:
                return False
        return True

    placed = 0
    for _ in range(2600):
        x, y = round(rng.uniform(-47, 47) * 4) / 4, round(rng.uniform(-33, 33) * 4) / 4
        pkg = rng.choice(("0402", "0402", "0603", "0603", "0805"))
        if clear(x, y, 1.9):
            rot = rng.choice((0, 0, 90))
            add("chip", f"X{placed}", x, y, rot, chip_pads(pkg, x, y, rot), pkg=pkg, tone="res" if rng.random() < 0.5 else "cap")
            placed += 1
        if placed >= 190:
            break

    fiducials = [(-46.0, -31.0), (46.0, -31.0), (-46.0, 31.0)]
    holes = [(-46.5, 27.0), (46.5, 31.5), (-46.5, -26.0), (46.5, -26.0)]

    # Routing: 45-degree buses, parallel where they run together, like a real layout.
    traces = []

    def route(a, b, w=0.2, horizontal=True):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        d = min(abs(dx), abs(dy))
        if horizontal:
            run = (abs(dx) - d) * rng.uniform(0.2, 0.8)
            p1 = (ax + math.copysign(run, dx), ay)
            p2 = (p1[0] + math.copysign(d, dx), by)
        else:
            run = (abs(dy) - d) * rng.uniform(0.2, 0.8)
            p1 = (ax, ay + math.copysign(run, dy))
            p2 = (bx, p1[1] + math.copysign(d, dy))
        traces.append({"pts": [a, p1, p2, b], "w": w})

    def bus(x0, y0, x1, y1, n, pitch, horizontal=True):
        for i in range(n):
            o = (i - (n - 1) / 2) * pitch
            if horizontal:
                route((x0, y0 + o), (x1, y1 + o), 0.16, True)
            else:
                route((x0 + o, y0), (x1 + o, y1), 0.16, False)

    bus(-11.5, 6.0, -40.5, -1.0, 10, 0.55, True)
    bus(-0.5, 7.0, 21.0, 15.0, 8, 0.55, True)
    bus(-6.0, 12.0, -22.0, 28.0, 9, 0.55, False)
    bus(-6.0, 0.0, 8.0, -16.0, 11, 0.5, False)
    bus(1.0, 3.0, 28.0, -17.0, 8, 0.55, True)
    bus(14.0, -19.0, 27.0, -22.0, 6, 0.5, True)
    bus(26.0, 11.0, 44.5, 2.0, 6, 0.6, True)
    bus(-29.0, -13.5, -44.0, -2.0, 4, 0.7, False)

    for _ in range(170):
        p, q = rng.choice(pads), rng.choice(pads)
        if 2.5 < math.hypot(q["x"] - p["x"], q["y"] - p["y"]) < 13:
            route((p["x"], p["y"]), (q["x"], q["y"]), rng.choice((0.2, 0.25)), rng.random() < 0.5)

    vias = []
    for _ in range(700):
        x, y = rng.uniform(-48, 48), rng.uniform(-34, 34)
        if all(math.hypot(x - p["x"], y - p["y"]) > 1.1 for p in pads):
            vias.append((round(x, 2), round(y, 2)))
    for gx in range(3):
        for gy in range(3):  # thermal via array inside the QFN centre pad
            vias.append((31.0 + (gx - 1) * 1.0, -20.0 + (gy - 1) * 1.0))

    return {"parts": parts, "pads": pads, "traces": traces, "vias": vias, "fiducials": fiducials, "holes": holes}
