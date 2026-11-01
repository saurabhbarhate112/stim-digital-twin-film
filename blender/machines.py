"""Surface-mount line hardware at real scale (1 BU = 1 cm).

The line runs along +X at a 90 cm transport height, in station order:
loader > printer > SPI > placement x2 > reflow > AOI > X-ray > unloader.
"""
import math

import bpy

from lib import MAPS, ROOT, cylinder, empty, lerp, loft, obj, principled, rbox, nodes_of

BELT_Z = 90.0
LINE_DEPTH = 12.0  # distance between conveyor rails, sized for a 10 x 7 cm board

STATIONS = [
    ("loader", 90, "LOADER"),
    ("printer", 150, "PASTE PRINT"),
    ("spi", 95, "PASTE INSPECT"),
    ("pnp1", 160, "PLACE"),
    ("pnp2", 160, "PLACE"),
    ("reflow", 480, "REFLOW"),
    ("aoi", 110, "AOI"),
    ("xray", 110, "X-RAY"),
    ("unloader", 90, "UNLOADER"),
]
GAP = 26.0


def layout_line():
    """Return {station: (x_centre, width)} with the line centred on the origin."""
    total = sum(w for _, w, _ in STATIONS) + GAP * (len(STATIONS) - 1)
    x = -total / 2
    out = {}
    for name, w, _ in STATIONS:
        out[name] = (x + w / 2, w)
        x += w + GAP
    return out


def screen_material(name):
    """Machine HMI: a baked live-process display, self-lit."""
    m = bpy.data.materials.new(name)
    n, l = nodes_of(m)
    for x in list(n):
        if x.type == "BSDF_PRINCIPLED":
            n.remove(x)
    tc = n.new("ShaderNodeTexCoord")
    t = n.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(str(MAPS / "hmi.png"))
    l.new(tc.outputs["UV"], t.inputs["Vector"])
    e = n.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = 1.6
    l.new(t.outputs["Color"], e.inputs["Color"])
    l.new(e.outputs[0], n["Material Output"].inputs["Surface"])
    return m


class Line:
    def __init__(self, mats):
        self.m = mats
        self.pos = layout_line()
        self.screen = screen_material("hmi")
        self.seam = principled("seam", (0.01, 0.012, 0.012, 1), 0, 0.6)
        self.bay = mats._emit("bay", (0.92, 0.97, 1.0, 1), 2.6)
        mats.void = principled("void", (0, 0, 0, 1))
        self.font = bpy.data.fonts.load(str(ROOT / "assets" / "fonts" / "IBMPlexMono-SemiBold.ttf"))
        self.tower_g = mats._emit("tower_green", (0.1, 1.0, 0.3, 1), 8)
        self.tower_off = principled("tower_off", (0.2, 0.05, 0.04, 1), 0, 0.25)
        self.tower_amb = principled("tower_amb", (0.45, 0.28, 0.02, 1), 0, 0.25)
        self.stripe = principled("stripe", (0.0024, 0.19, 0.058, 1), 0, 0.3, coat=0.6)

    def cabinet(self, name, x, w, label, d=120.0, h=165.0):
        m = self.m
        root = empty(name, x, 0, 0)
        front = -d / 2
        # Base plinth, levelling feet, then the hood over the transport height.
        obj("plinth", rbox(name + "_p", w, d, BELT_Z - 12, 2.0, 3, mat=m.grey_panel), 0, 0, 7, parent=root)
        hood = rbox(name + "_h", w, d, h - BELT_Z + 12, 4.0, 4, z0=0, mat=m.white_panel)
        obj("hood", hood, 0, 0, BELT_Z - 5, parent=root)
        obj("stripe", rbox(name + "_s", w + 0.2, d + 0.2, 1.6, 0, 1, mat=self.stripe), 0, 0, BELT_Z - 8.5, parent=root)
        for sx in (-1, 1):
            for sy in (-1, 1):
                obj("foot", cylinder(name + "ft", 3, 7, mat=m.steel), sx * (w / 2 - 8), sy * (d / 2 - 8), 0, parent=root)
        # Lower service doors: seams, vents and handles keep the panels from reading as blank.
        doors = max(2, round(w / 55))
        for i in range(doors):
            dx = -w / 2 + (i + 0.5) * w / doors
            obj("seam", rbox(name + "_sm", 0.5, 0.4, BELT_Z - 18, mat=self.seam), dx - w / doors / 2 + 0.5, front - 0.1, 10, parent=root)
            obj("hndl", rbox(name + "_hn", 2.0, 2.4, 16, 0.6, 2, mat=m.steel), dx + w / doors / 2 - 7, front - 1.0, 44, parent=root)
            for v in range(7):
                obj("vent", rbox(name + "_v", min(30, w / doors - 18), 0.5, 1.2, mat=self.seam), dx - 4, front - 0.1, 18 + v * 3, parent=root)
        # Lit working bay behind the window, with the gantry in silhouette.
        win_w = max(w - 34, 40)
        obj("bay", rbox(name + "_b", win_w - 2, 1.0, 54, mat=self.bay), 0, front + 34, BELT_Z + 12, parent=root)
        obj("bay2", rbox(name + "_b2", win_w + 4, 34, 2, mat=m.grey_panel), 0, front + 17, BELT_Z + 10, parent=root)
        obj("gantry", rbox(name + "_g", win_w - 4, 7, 9, 0.5, 1, mat=m.alu), 0, front + 24, BELT_Z + 48, parent=root)
        obj("gantry2", rbox(name + "_g2", 15, 12, 34, 1.0, 2, mat=m.green_paint), -w * 0.08, front + 21, BELT_Z + 22, parent=root)
        obj("cut", rbox(name + "_c", win_w, 18, 56, mat=m.void), 0, front + 8, BELT_Z + 12, parent=root).hide_render = True
        obj("frame", rbox(name + "_f", win_w + 5, 2.0, 62, 1.0, 2, mat=m.grey_panel), 0, front - 0.6, BELT_Z + 11, parent=root)
        obj("win", rbox(name + "_w", win_w, 0.8, 58, 0.2, 1, mat=m.glass), 0, front - 1.8, BELT_Z + 13, parent=root)
        obj("toph", rbox(name + "_th", w * 0.5, 2.2, 2.2, 0.8, 2, mat=m.steel), 0, front - 1.2, BELT_Z + 66, parent=root)
        # HMI on an arm, tilted to the operator.
        obj("arm", rbox(name + "_a", 3, 6, 34, 1, 2, mat=m.steel), w / 2 - 12, front - 3, BELT_Z + 16, parent=root)
        sc = obj("screen", rbox(name + "_sc", 30, 1.6, 20, 0.6, 2, mat=m.nylon), w / 2 - 12, front - 6.5, BELT_Z + 40, parent=root)
        sc.rotation_euler[0] = math.radians(-8)
        gl = obj("disp", self.hmi_quad(27, 17), 0, -0.85, 10.0, parent=sc)
        # Stack light.
        tz = h + 7
        obj("pole", cylinder(name + "_po", 0.7, 12, mat=m.steel), -w / 2 + 14, d / 2 - 16, tz, parent=root)
        for i, mat in enumerate((self.tower_g, self.tower_amb, self.tower_off)):
            obj("lamp", cylinder(name + f"_l{i}", 2.2, 4.4, verts=24, mat=mat), -w / 2 + 14, d / 2 - 16, tz + 12 + i * 4.5, parent=root)
        self.label(root, label, 0, front - 0.4, h + 2.5)
        return root

    def hmi_quad(self, w, h):
        me = bpy.data.meshes.new("hmi")
        me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
        me.uv_layers.new(name="UVMap")
        for lp, uv in zip(me.uv_layers[0].data, ((0, 0), (1, 0), (1, 1), (0, 1))):
            lp.uv = uv
        me.materials.append(self.screen)
        return me

    def label(self, parent, text, x, y, z):
        c = bpy.data.curves.new("lbl", "FONT")
        c.body = text
        c.font = self.font
        c.size = 6.0
        c.align_x = "CENTER"
        c.materials.append(self.stripe)
        o = bpy.data.objects.new("lbl", c)
        o.parent = parent
        o.location = (x, y, z)
        o.rotation_euler[0] = math.pi / 2
        bpy.context.scene.collection.objects.link(o)

    def conveyor(self, x0, x1, name="conv"):
        m = self.m
        length = x1 - x0
        cx = (x0 + x1) / 2
        rail = [(-1.6, -2.6), (1.6, -2.6), (1.6, 2.2), (0.4, 2.2), (0.4, 0), (-1.6, 0)]
        root = empty(name, cx, 0, BELT_Z)
        for s in (-1, 1):
            me = rbox(name + "_rail", length, 1.6, 5.2, 0.3, 2, z0=-3.2, mat=m.alu)
            obj("rail", me, 0, s * (LINE_DEPTH / 2 + 1.6), 0, parent=root)
            ch = rbox(name + "_chain", length, 1.0, 0.6, 0.1, 1, z0=-0.6, mat=m.rubber)
            obj("chain", ch, 0, s * (LINE_DEPTH / 2 + 0.2), 0, parent=root)
        return root

    def build(self, stations=None):
        for name, w, label in STATIONS:
            if stations and name not in stations:
                continue
            x, w = self.pos[name]
            if name == "reflow":
                self.oven_shell(x, w)
            else:
                self.cabinet(name, x, w, label)
        xs = [self.pos[n][0] for n in (stations or self.pos)]
        self.conveyor(min(xs) - 130, max(xs) + 130)

    def oven_shell(self, x, w, d=140.0, h=150.0):
        m = self.m
        root = empty("oven", x, 0, 0)
        obj("plinth", rbox("ov_p", w, d, BELT_Z - 22, 2.0, 3, mat=m.grey_panel), 0, 0, 7, parent=root)
        for i in range(8):
            sw = w / 8
            zx = -w / 2 + sw * (i + 0.5)
            obj("zone", rbox(f"ov_z{i}", sw - 1.0, d, h - BELT_Z + 26, 3.0, 3, mat=m.white_panel), zx, 0, BELT_Z - 19, parent=root)
            obj("handle", rbox(f"ov_h{i}", sw - 16, 2.2, 2.2, 0.8, 2, mat=m.steel), zx, -d / 2 - 2, h - 18, parent=root)
            obj("sc", rbox(f"ov_s{i}", 12, 1.0, 7, 0.3, 1, mat=self.screen), zx, -d / 2 - 0.6, BELT_Z + 8, parent=root)
        obj("stripe", rbox("ov_st", w + 0.2, d + 0.2, 1.6, 0, 1, mat=self.stripe), 0, 0, BELT_Z - 20, parent=root)
        return root


def factory_room(mats, length=2400.0, width=1100.0, height=420.0, line_light=1.0):
    """Bright electronics hall: glossy epoxy floor, ceiling lightbars, pale walls."""
    floor = principled("epoxy_floor", (0.68, 0.72, 0.71, 1), 0, 0.14, spec=0.5)
    wall = principled("wall", (0.8, 0.83, 0.82, 1), 0, 0.5)
    obj("floor", rbox("floor", length, width, 2, z0=-2, mat=floor))
    walk = principled("walkway", (0.02, 0.32, 0.12, 1), 0, 0.2)
    for s in (-1, 1):
        obj("lane", rbox("lane", length, 8, 0.1, mat=walk), 0, s * 170, 0)
    obj("backwall", rbox("backwall", length, 4, height, mat=wall), 0, width / 2, 0)
    obj("frontwall", rbox("frontwall", length, 4, height, mat=wall), 0, -width / 2, 0)
    obj("ceil", rbox("ceil", length, width, 4, z0=height, mat=wall), 0, 0, 0)
    for side in (-1, 1):
        obj("endwall", rbox("endwall", 4, width, height, mat=wall), side * length / 2, 0, 0)
    bar = mats._emit("lightbar", (1, 1, 0.98, 1), 9)
    me = rbox("bar", 300, 12, 2, mat=bar)
    for ix in range(-4, 5):
        for iy in range(-2, 3):
            obj("bar", me, ix * 460, iy * 170, height - 3)
    # Overhead services along the line: cable tray, compressed-air and exhaust drops.
    tray = principled("tray", (0.5, 0.52, 0.53, 1), 0.8, 0.35)
    for y, zz, hh in ((-30, 285, 8), (30, 300, 22)):
        obj("tray", rbox("tray", length * 0.86, 30, hh, mat=tray), 0, y, zz)
    for ix in range(-9, 10):
        obj("drop", rbox("drop", 5, 5, 118, mat=tray), ix * 118 + 20, 30, 168)
        obj("hang", rbox("hang", 2, 2, 110, mat=tray), ix * 118, -30, 293)
    # Columns give the eye depth when the camera tracks along the line.
    col = rbox("col", 40, 40, height, 3, 2, mat=wall)
    for ix in range(-5, 6):
        obj("col", col, ix * 460, 420, 0)
    return floor


def board_collection(builder_root, name="board_inst"):
    """Move a built board into its own collection for cheap instancing along the line."""
    coll = bpy.data.collections.new(name)
    stack = [builder_root]
    while stack:
        o = stack.pop()
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        stack.extend(o.children)
    return coll


def instance(coll, name, x, y, z, rz=0.0):
    o = bpy.data.objects.new(name, None)
    o.instance_type = "COLLECTION"
    o.instance_collection = coll
    o.location = (x, y, z)
    o.rotation_euler[2] = rz
    bpy.context.scene.collection.objects.link(o)
    return o


def key_linear(o, s, points):
    """Keyframe location with constant speed so conveyors never ease."""
    for f, loc in points:
        o.location = loc
        o.keyframe_insert("location", frame=f)
    from lib import fcurves
    for fc in fcurves(o.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
