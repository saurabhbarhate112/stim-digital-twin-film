"""Surface-mount line hardware at real scale (1 BU = 1 cm).

The line runs along +X at a 90 cm transport height, in station order:
loader > printer > SPI > placement x2 > reflow > AOI > X-ray > unloader.
"""
import math

import bpy

from lib import cylinder, empty, lerp, loft, obj, principled, rbox, nodes_of

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


def screen_material(name, base=(0.02, 0.1, 0.07, 1), strength=2.5):
    """Machine HMI: lit panel with procedural bars, enough to read as a live display."""
    m = bpy.data.materials.new(name)
    n, l = nodes_of(m)
    for x in list(n):
        if x.type == "BSDF_PRINCIPLED":
            n.remove(x)
    tc = n.new("ShaderNodeTexCoord")
    wave = n.new("ShaderNodeTexBrick")
    wave.inputs["Color1"].default_value = (0.1, 0.85, 0.5, 1)
    wave.inputs["Color2"].default_value = (0.9, 0.97, 0.93, 1)
    wave.inputs["Mortar"].default_value = base
    wave.inputs["Scale"].default_value = 6.0
    wave.inputs["Mortar Size"].default_value = 0.09
    l.new(tc.outputs["Object"], wave.inputs["Vector"])
    e = n.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = strength
    l.new(wave.outputs["Color"], e.inputs["Color"])
    l.new(e.outputs[0], n["Material Output"].inputs["Surface"])
    return m


class Line:
    def __init__(self, mats):
        self.m = mats
        self.pos = layout_line()
        self.screen = screen_material("hmi")
        self.tower_g = mats._emit("tower_green", (0.1, 1.0, 0.3, 1), 8)
        self.tower_off = principled("tower_off", (0.2, 0.05, 0.04, 1), 0, 0.25)
        self.tower_amb = principled("tower_amb", (0.45, 0.28, 0.02, 1), 0, 0.25)
        self.stripe = principled("stripe", (0.0024, 0.19, 0.058, 1), 0, 0.3, coat=0.6)

    def cabinet(self, name, x, w, label, d=120.0, h=165.0):
        m = self.m
        root = empty(name, x, 0, 0)
        # Base plinth, levelling feet, then the hood over the transport height.
        obj("plinth", rbox(name + "_p", w, d, BELT_Z - 12, 2.0, 3, mat=m.grey_panel), 0, 0, 7, parent=root)
        hood = rbox(name + "_h", w, d, h - BELT_Z + 12, 5.0, 5, z0=0, mat=m.white_panel)
        obj("hood", hood, 0, 0, BELT_Z - 5, parent=root)
        obj("stripe", rbox(name + "_s", w + 0.2, d + 0.2, 1.6, 0, 1, mat=self.stripe), 0, 0, BELT_Z - 8.5, parent=root)
        for sx in (-1, 1):
            for sy in (-1, 1):
                obj("foot", cylinder(name + "ft", 3, 7, mat=m.steel), sx * (w / 2 - 8), sy * (d / 2 - 8), 0, parent=root)
        # Front viewing window with a lit interior behind it.
        win_w = max(w - 34, 40)
        obj("frame", rbox(name + "_f", win_w + 5, 2.0, 62, 1.0, 2, mat=m.grey_panel), 0, -d / 2 - 0.2, BELT_Z + 12, parent=root)
        obj("win", rbox(name + "_w", win_w, 2.6, 58, 0.4, 1, mat=m.glass), 0, -d / 2 - 0.3, BELT_Z + 14, parent=root)
        # HMI on an arm, tilted to the operator.
        arm = rbox(name + "_a", 3, 6, 34, 1, 2, mat=m.steel)
        obj("arm", arm, w / 2 - 12, -d / 2 - 3, BELT_Z + 16, parent=root)
        sc = obj("screen", rbox(name + "_sc", 30, 1.6, 20, 0.6, 2, mat=self.screen), w / 2 - 12, -d / 2 - 6.5, BELT_Z + 40, parent=root)
        sc.rotation_euler[0] = math.radians(-8)
        # Stack light.
        tz = h + 7
        obj("pole", cylinder(name + "_po", 0.7, 12, mat=m.steel), -w / 2 + 14, d / 2 - 16, tz, parent=root)
        for i, mat in enumerate((self.tower_g, self.tower_amb, self.tower_off)):
            obj("lamp", cylinder(name + f"_l{i}", 2.2, 4.4, verts=24, mat=mat), -w / 2 + 14, d / 2 - 16, tz + 12 + i * 4.5, parent=root)
        return root

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
