"""Procedural circuit board: real package geometry over a baked copper/silk map.

build_board(state=...) gives the same board at each step of assembly:
bare -> paste -> placed -> reflowed.
"""
import json
import math

import bmesh
import bpy

import layout
from lib import MAPS, MM, Mats, cylinder, empty, loft, nodes_of, obj, rbox

T = layout.BOARD_T * MM


def mask_material(name="soldermask", mask=(0.0012, 0.05, 0.02), over_copper=(0.008, 0.115, 0.04)):
    """Glossy solder mask whose tone and relief come from the baked copper map."""
    m = bpy.data.materials.new(name)
    n, l = nodes_of(m)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")

    def tex(path, offset_y=0):
        t = n.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(path))
        t.image.colorspace_settings.name = "Non-Color"
        t.extension = "EXTEND"
        t.interpolation = "Linear"
        return t

    # Board map over the whole top; a 4x sharper patch round U1 for macro shots.
    board = tex(MAPS / "board.png")
    detail = tex(MAPS / "detail.png")
    l.new(tc.outputs["UV"], board.inputs["Vector"])
    mp = n.new("ShaderNodeMapping")
    mp.vector_type = "TEXTURE"
    # Patch centre (31, -20) mm, 24 mm square, in board UV (0..1 across 100 x 70 mm).
    mp.inputs["Location"].default_value = ((31.0 + 50 - 12) / 100, (-20.0 + 35 - 12) / 70, 0)
    mp.inputs["Scale"].default_value = (24 / 100, 24 / 70, 1)
    l.new(tc.outputs["UV"], mp.inputs["Vector"])
    l.new(mp.outputs[0], detail.inputs["Vector"])

    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(mp.outputs[0], sep.inputs[0])

    def inside(axis):
        g = n.new("ShaderNodeMath")
        g.operation = "GREATER_THAN"
        g.inputs[1].default_value = 0.0
        h = n.new("ShaderNodeMath")
        h.operation = "LESS_THAN"
        h.inputs[1].default_value = 1.0
        l.new(sep.outputs[axis], g.inputs[0])
        l.new(sep.outputs[axis], h.inputs[0])
        a = n.new("ShaderNodeMath")
        a.operation = "MULTIPLY"
        l.new(g.outputs[0], a.inputs[0])
        l.new(h.outputs[0], a.inputs[1])
        return a

    both = n.new("ShaderNodeMath")
    both.operation = "MULTIPLY"
    l.new(inside("X").outputs[0], both.inputs[0])
    l.new(inside("Y").outputs[0], both.inputs[1])
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    l.new(both.outputs[0], mix.inputs["Factor"])
    l.new(board.outputs["Color"], mix.inputs["A"])
    l.new(detail.outputs["Color"], mix.inputs["B"])
    chan = n.new("ShaderNodeSeparateColor")
    l.new(mix.outputs["Result"], chan.inputs[0])

    c1 = n.new("ShaderNodeMix")
    c1.data_type = "RGBA"
    c1.inputs["A"].default_value = (*mask, 1)
    c1.inputs["B"].default_value = (*over_copper, 1)
    l.new(chan.outputs["Red"], c1.inputs["Factor"])

    silk = n.new("ShaderNodeMix")
    silk.data_type = "RGBA"
    silk.inputs["B"].default_value = (0.9, 0.91, 0.89, 1)
    l.new(c1.outputs["Result"], silk.inputs["A"])
    l.new(chan.outputs["Green"], silk.inputs["Factor"])

    hole = n.new("ShaderNodeMix")
    hole.data_type = "RGBA"
    hole.inputs["B"].default_value = (0.005, 0.005, 0.005, 1)
    l.new(silk.outputs["Result"], hole.inputs["A"])
    l.new(chan.outputs["Blue"], hole.inputs["Factor"])
    l.new(hole.outputs["Result"], b.inputs["Base Color"])

    # Silk is matte; the rest wears a clear glossy lacquer.
    rmix = n.new("ShaderNodeMapRange")
    rmix.inputs["To Min"].default_value = 0.2
    rmix.inputs["To Max"].default_value = 0.62
    l.new(chan.outputs["Green"], rmix.inputs["Value"])
    l.new(rmix.outputs[0], b.inputs["Roughness"])
    cmix = n.new("ShaderNodeMapRange")
    cmix.inputs["To Min"].default_value = 1.0
    cmix.inputs["To Max"].default_value = 0.1
    l.new(chan.outputs["Green"], cmix.inputs["Value"])
    l.new(cmix.outputs[0], b.inputs["Coat Weight"])
    b.inputs["Coat Roughness"].default_value = 0.06
    b.inputs["Coat IOR"].default_value = 1.55

    add = n.new("ShaderNodeMath")
    add.operation = "ADD"
    l.new(chan.outputs["Red"], add.inputs[0])
    w = n.new("ShaderNodeMath")
    w.operation = "MULTIPLY"
    w.inputs[1].default_value = 1.4
    l.new(chan.outputs["Green"], w.inputs[0])
    l.new(w.outputs[0], add.inputs[1])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.55
    bump.inputs["Distance"].default_value = 0.0035
    l.new(add.outputs[0], bump.inputs["Height"])

    # Faint orange-peel in the lacquer stops reflections looking like CG glass.
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 26.0
    noise.inputs["Detail"].default_value = 1.0
    tc2 = n.new("ShaderNodeTexCoord")
    l.new(tc2.outputs["Object"], noise.inputs["Vector"])
    peel = n.new("ShaderNodeBump")
    peel.inputs["Strength"].default_value = 0.012
    peel.inputs["Distance"].default_value = 0.02
    l.new(noise.outputs["Fac"], peel.inputs["Height"])
    l.new(bump.outputs["Normal"], peel.inputs["Normal"])
    l.new(peel.outputs["Normal"], b.inputs["Coat Normal"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def board_body(mats, mask):
    w, h = layout.BOARD_W * MM, layout.BOARD_H * MM
    me = bpy.data.meshes.new("board")
    bm = bmesh.new()
    r = 2.5 * MM
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(9):
            a = math.radians(a0 + i * 90 / 8)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    top = [bm.verts.new((x, y, 0)) for x, y in pts]
    bot = [bm.verts.new((x, y, -T)) for x, y in pts]
    ft = bm.faces.new(top)
    fb = bm.faces.new(bot[::-1])
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
        f.material_index = 1
    uv = bm.loops.layers.uv.new("UVMap")
    for f in (ft, fb):
        for lo in f.loops:
            lo[uv].uv = (lo.vert.co.x / w + 0.5, lo.vert.co.y / h + 0.5)
    bm.to_mesh(me)
    bm.free()
    fr4 = mats.fr4 if hasattr(mats, "fr4") else None
    if fr4 is None:
        from lib import add_noise_bump, principled
        mats.fr4 = add_noise_bump(principled("fr4", (0.44, 0.40, 0.2, 1), 0.0, 0.55), 180, 0.25)
    me.materials.append(mask)
    me.materials.append(mats.fr4)
    return me


def fillet_mesh(name, w, length, height, mat, steps=9):
    """Concave solder meniscus: rises from the pad up the part's terminal."""
    prof = [(0.0, 0.0)]
    for i in range(steps + 1):
        t = i / steps
        x = length * (1 - t)
        z = height * (1 - (1 - t) ** 0.45) ** 1.0
        prof.append((x, z * 1.0))
    me = loft(name, prof[::-1], w, mat)
    return me


def lead_mesh(name, width, reach, drop, t, mat):
    """Gull-wing lead profile leaving the package at body mid height."""
    o = t
    p = [(0, drop), (reach * 0.32, drop), (reach * 0.5, t * 0.8), (reach, 0),
         (reach, o * 0.0 + t), (reach * 0.56, t * 1.8), (reach * 0.38, drop + t), (0, drop + t)]
    return loft(name, p, width, mat)


def mark(builder, par, ref, z, size):
    """Laser-etched package marking; deliberately generic, no real manufacturer."""
    c = bpy.data.curves.new("mark" + ref, "FONT")
    c.body = {"U1": "D48\nQ5A", "U2": "STIM\nC4812"}.get(ref, "T" + ref + "\n2642")
    c.size = size
    c.align_x = "CENTER"
    c.align_y = "CENTER"
    c.space_line = 1.05
    c.materials.append(builder.m.etch)
    o = bpy.data.objects.new("mark", c)
    o.parent = par
    o.location = (0, 0, z + 0.0015)
    bpy.context.scene.collection.objects.link(o)


class BoardBuilder:
    def __init__(self, mats, state="reflowed", heat=None):
        self.m = mats
        self.state = state
        self.data = json.loads((MAPS / "layout.json").read_text(encoding="utf-8"))
        self.root = empty("board_root")
        self.meshes = {}
        self.parts = {}
        self.deposits = []
        self.fillets = []

    def shared(self, key, fn):
        if key not in self.meshes:
            self.meshes[key] = fn()
        return self.meshes[key]

    def build(self, mask=None):
        m = self.m
        mask = mask or mask_material()
        self.mask = mask
        self.body = obj("board", board_body(m, mask), parent=self.root)
        self._pads()
        if self.state in ("placed", "reflowed"):
            for p in self.data["parts"]:
                self.parts[p["ref"]] = self._part(p)
        return self.root

    def _pads(self):
        m = self.m
        pad_h = 0.04 * MM
        paste_h = 0.12 * MM
        for i, p in enumerate(self.data["pads"]):
            w, h = p["w"] * MM, p["h"] * MM
            x, y = p["x"] * MM, p["y"] * MM
            if p.get("round"):
                me = self.shared(("rpad", w), lambda: cylinder("rpad", w / 2, pad_h, verts=24, mat=m.gold))
            else:
                me = self.shared(("pad", round(w, 4), round(h, 4)),
                                 lambda: rbox("pad", w, h, pad_h, 0.004 * MM * 3, 1, mat=m.gold))
            obj(f"pad{i}", me, x, y, 0, p.get("rot", 0), self.root)
            if self.state in ("paste", "placed"):
                dw, dh = w * 0.92, h * 0.92
                if p.get("thermal"):  # Windowpane paste pattern on a QFN centre pad.
                    for gx in (-1, 1):
                        for gy in (-1, 1):
                            d = rbox("dep", w * 0.4, h * 0.4, paste_h, 0.02 * MM, 2, mat=m.paste)
                            self.deposits.append(obj(f"dep{i}{gx}{gy}", d, x + gx * w * 0.23, y + gy * h * 0.23, pad_h, 0, self.root))
                    continue
                me = self.shared(("dep", round(dw, 4), round(dh, 4)),
                                 lambda: rbox("dep", dw, dh, paste_h, 0.025 * MM, 2, mat=m.paste))
                self.deposits.append(obj(f"dep{i}", me, x, y, pad_h, p.get("rot", 0), self.root))

    # Packages ----------------------------------------------------------------

    def _chip(self, p):
        m = self.m
        pkg = p["pkg"]
        w, d, h, t = (v * MM for v in layout.CHIP[pkg])
        tone = p.get("tone", "cap")
        z0 = 0.07 * MM
        par = empty(p["ref"], p["x"] * MM, p["y"] * MM, 0, self.root)
        par.rotation_euler[2] = math.radians(p["rot"])
        body_mat = {"cap": m.ceramic, "res": m.res_body, "led": m.glass}[tone]
        body = self.shared(("chipbody", pkg, tone), lambda: rbox("chip", w - 2 * t * 0.9, d * 0.98, h, 0.05 * MM, 2, mat=body_mat))
        term = self.shared(("chipterm", pkg), lambda: rbox("term", t, d, h * 1.02, 0.045 * MM, 2, mat=m.tin))
        obj("b", body, 0, 0, z0, parent=par)
        for s in (-1, 1):
            obj("t", term, s * (w / 2 - t / 2), 0, z0, parent=par)
            if self.state == "reflowed":
                f = self.shared(("chipfil", pkg), lambda: fillet_mesh("fil", d * 0.96, 0.32 * MM, h * 0.7, m.solder))
                o = obj("f", f, s * (w / 2), 0, 0.04 * MM, 0 if s > 0 else 180, par)
                self.fillets.append(o)
        if tone == "res":
            top = self.shared(("restop", pkg), lambda: rbox("top", w - 2 * t, d * 0.82, 0.01 * MM, 0, 1, mat=m.res_body))
            obj("rt", top, 0, 0, z0 + h, parent=par)
        if tone == "led":
            core = self.shared(("ledcore", pkg), lambda: rbox("core", w * 0.3, d * 0.5, h * 0.4, 0.0, 1, mat=m.led))
            obj("c", core, 0, 0, z0 + h * 0.2, parent=par)
        return par

    def _gull(self, p, sides):
        m = self.m
        n, pitch = p["n"], p["pitch"] * MM
        body_w, body_d = (p["body"] if sides == 2 else (p["body"], p["body"]))
        body_w, body_d = body_w * MM, body_d * MM
        span = p["span"] * MM
        h = 1.1 * MM if sides == 4 else 1.55 * MM
        z0 = 0.12 * MM
        par = empty(p["ref"], p["x"] * MM, p["y"] * MM, 0, self.root)
        body = rbox(p["ref"] + "b", body_w, body_d, h, 0.1 * MM, 3, mat=m.epoxy)
        obj("b", body, 0, 0, z0, parent=par)
        reach = (span - body_d) / 2 + 0.35 * MM
        lead = self.shared(("lead", round(pitch, 4)), lambda: lead_mesh("lead", pitch * 0.45, reach, z0 + h * 0.45, 0.13 * MM, m.tin))
        o0 = -(n - 1) * pitch / 2
        for i in range(n):
            o = o0 + i * pitch
            obj("l", lead, o, -body_d / 2, 0.04 * MM, -90, par)
            obj("l", lead, o, body_d / 2, 0.04 * MM, 90, par)
            if sides == 4:
                obj("l", lead, -body_d / 2, o, 0.04 * MM, 180, par)
                obj("l", lead, body_d / 2, o, 0.04 * MM, 0, par)
        dot = cylinder("dot", 0.35 * MM, 0.002, mat=m.tin if sides == 4 else m.tin)
        obj("dot", dot, -body_w / 2 + 0.8 * MM, -body_d / 2 + 0.8 * MM, z0 + h, parent=par)
        mark(self, par, p["ref"], z0 + h, min(body_w, body_d) * 0.16)
        return par

    def _qfn(self, p):
        m = self.m
        small = p.get("small")
        b, h = (3.0 if small else 5.0) * MM, 0.9 * MM
        z0 = 0.06 * MM
        par = empty(p["ref"], p["x"] * MM, p["y"] * MM, 0, self.root)
        obj("b", rbox("qfnb", b, b, h, 0.02 * MM, 2, mat=m.epoxy), 0, 0, z0, parent=par)
        pitch = 0.5 * MM
        count = 4 if small else 8
        for i in range(count):
            o = (i - (count - 1) / 2) * pitch
            term = self.shared("qfnterm", lambda: rbox("qt", 0.25 * MM, 0.03 * MM, 0.2 * MM, 0, 1, mat=m.tin))
            for rot, (x, y) in ((0, (o, -b / 2)), (0, (o, b / 2)), (90, (-b / 2, o)), (90, (b / 2, o))):
                obj("t", term, x, y, z0, rot, par)
                if self.state == "reflowed":
                    f = self.shared("qfnfil", lambda: fillet_mesh("qf", 0.25 * MM, 0.32 * MM, 0.2 * MM, m.solder))
                    a = math.degrees(math.atan2(y, x))
                    a = round(a / 90) * 90
                    self.fillets.append(obj("f", f, x, y, 0.04 * MM, a, par))
        obj("dot", cylinder("dot", 0.25 * MM, 0.002, mat=m.tin), -b / 2 + 0.6 * MM, b / 2 - 0.6 * MM, z0 + h, parent=par)
        mark(self, par, p["ref"], z0 + h, b * 0.14)
        return par

    def _part(self, p):
        m = self.m
        k = p["kind"]
        if k in ("chip", "led"):
            return self._chip(p)
        if k == "soic":
            return self._gull(p, 2)
        if k == "tqfp":
            return self._gull(p, 4)
        if k == "qfn":
            return self._qfn(p)
        par = empty(p["ref"], p["x"] * MM, p["y"] * MM, 0, self.root)
        if k == "sot":
            obj("b", rbox("sb", 2.9 * MM, 1.3 * MM, 1.0 * MM, 0.07 * MM, 2, mat=m.epoxy), 0, 0, 0.1 * MM, parent=par)
            lead = self.shared("sotlead", lambda: lead_mesh("sl", 0.4 * MM, 0.75 * MM, 0.5 * MM, 0.1 * MM, m.tin))
            obj("l", lead, -0.95 * MM, -0.65 * MM, 0.04 * MM, -90, par)
            obj("l", lead, 0.95 * MM, -0.65 * MM, 0.04 * MM, -90, par)
            obj("l", lead, 0, 0.65 * MM, 0.04 * MM, 90, par)
        elif k == "switch":
            obj("b", rbox("swb", 6.0 * MM, 6.0 * MM, 3.4 * MM, 0.25 * MM, 3, mat=m.nylon), 0, 0, 0.05 * MM, parent=par)
            obj("c", cylinder("swc", 1.75 * MM, 1.6 * MM, z0=3.4 * MM, bevel=0.2 * MM, mat=m.steel), 0, 0, 0, parent=par)
        elif k == "crystal":
            obj("b", rbox("xb", 3.2 * MM, 2.5 * MM, 0.15 * MM, 0.02 * MM, 1, mat=m.ceramic), 0, 0, 0.05 * MM, parent=par)
            obj("lid", rbox("xl", 2.9 * MM, 2.2 * MM, 0.6 * MM, 0.12 * MM, 3, mat=m.chrome), 0, 0, 0.2 * MM, parent=par)
        elif k == "inductor":
            obj("b", rbox("ib", 9.0 * MM, 8.0 * MM, 4.0 * MM, 0.5 * MM, 4, mat=m.epoxy), 0, 0, 0.05 * MM, parent=par)
            obj("ring", cylinder("ic", 3.2 * MM, 0.08 * MM, mat=m.grey_panel), 0, 0, 4.05 * MM, parent=par)
        elif k == "elco":
            r, h = p["r"] * MM, p["h"] * MM
            obj("base", rbox("eb", r * 2.1, r * 2.1, 1.2 * MM, 0.3 * MM, 3, mat=m.rubber), 0, 0, 0.05 * MM, parent=par)
            obj("can", cylinder("ec", r, h, z0=1.0 * MM, bevel=0.3 * MM, mat=m.alu), 0, 0, 0, parent=par)
            obj("mark", cylinder("em", r * 0.78, 0.01, z0=h + 1.0 * MM, mat=m.grey_panel), 0, 0, 0, parent=par)
        elif k == "usbc":
            obj("sh", rbox("us", 7.4 * MM, 9.0 * MM, 3.2 * MM, 1.0 * MM, 5, mat=m.chrome), 0, 0, 0.1 * MM, parent=par)
        elif k == "header":
            for i in range(p["n"]):
                y = (i - (p["n"] - 1) / 2) * 2.54 * MM
                obj("hb", rbox("hb", 2.5 * MM, 2.5 * MM, 2.5 * MM, 0.2 * MM, 2, mat=m.nylon), 0, y, 0.0, parent=par)
                obj("pin", rbox("hp", 0.64 * MM, 0.64 * MM, 8.5 * MM, 0.08 * MM, 2, mat=m.gold), 0, y, 0.0, parent=par)
        return par
