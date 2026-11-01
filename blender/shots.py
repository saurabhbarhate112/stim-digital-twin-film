"""Every 3D shot in the film. Each function builds a scene and animates it over
ctx.frames frames (24 fps), so timing follows the narration automatically.
Scenes are reused across shots; only cameras and states change.
"""
import json
import math
import random

import bmesh
import bpy
from mathutils import Vector

import layout
import lib
from lib import MAPS, MM, MINT, cylinder, ease, empty, lerp, loft, nodes_of, obj, principled, rbox
from machines import BELT_Z, LINE_DEPTH, Line, board_collection, factory_room, instance, key_linear
from pcb import T, BoardBuilder, mask_material
from twin import scan_empty, twinify_all


class Ctx:
    def __init__(self, s, frames):
        self.s = s
        self.frames = frames
        self.anchors = {}

    def f(self, t):
        return 1 + round(t * (self.frames - 1))

    def anchor(self, name, target):
        self.anchors[name] = target


def kf(ctx, o, t, loc=None, rot=None, scale=None):
    f = ctx.f(t)
    if loc is not None:
        o.location = loc
        o.keyframe_insert("location", frame=f)
    if rot is not None:
        o.rotation_euler = rot
        o.keyframe_insert("rotation_euler", frame=f)
    if scale is not None:
        o.scale = scale
        o.keyframe_insert("scale", frame=f)


def kprop(ctx, o, name, t, value):
    o[name] = value
    o.keyframe_insert(f'["{name}"]', frame=ctx.f(t))


def camera(ctx, moves, lens=50, fstop=8.0):
    cam, target = lib.camera(ctx.s, lens, fstop)
    lib.key_camera(cam, target, ctx.s, moves, ctx.frames)
    return cam, target


def object_prop(mat, name):
    n, _ = nodes_of(mat)
    a = n.new("ShaderNodeAttribute")
    a.attribute_type = "OBJECT"
    a.attribute_name = name
    return a


def reveal(mat, driver):
    """Hide the surface until the driver empty has passed it (scan-space X < 0 stays hidden)."""
    n, l = nodes_of(mat)
    out = n["Material Output"]
    src = out.inputs["Surface"].links[0].from_socket
    tc = n.new("ShaderNodeTexCoord")
    tc.object = driver
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    gt = n.new("ShaderNodeMath")
    gt.operation = "LESS_THAN"
    gt.inputs[1].default_value = 0.0
    l.new(sep.outputs["X"], gt.inputs[0])
    tr = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    l.new(gt.outputs[0], mix.inputs[0])
    l.new(tr.outputs[0], mix.inputs[1])
    l.new(src, mix.inputs[2])
    l.new(mix.outputs[0], out.inputs["Surface"])


# Scene: board on a stage ---------------------------------------------------------


def stage(ctx, state="reflowed", key=1.0, thin_u1=False):
    s = ctx.s
    lib.studio(s, key=key)
    mats = lib.Mats()
    b = BoardBuilder(mats, state)
    root = b.build()
    root.location.z = 0.42
    obj("stand", rbox("stand", 9, 6, 0.26, 0.02, 1, mat=mats.grey_panel))
    if thin_u1:
        for o in b.deposits:
            if abs(o.location.x - 3.1) < 0.6 and abs(o.location.y + 2.0) < 0.6:
                o.scale.z = 0.78
    return mats, b, root


def paste_macro(ctx):
    stage(ctx, "paste", thin_u1=True)
    camera(ctx, [(0, (4.75, -3.7, 0.72), (3.35, -2.25, 0.46)),
                 (1, (4.25, -3.3, 0.62), (3.05, -2.05, 0.45))], lens=85, fstop=4.0)


def spi_scan(ctx):
    mats, b, root = stage(ctx, "paste", key=0.7)
    # A sheet of laser light sweeps the deposits, as a 3D paste inspector does.
    laser = mats._emit("laser", (0.08, 1.0, 0.45, 1), 40)
    bar = obj("laser", rbox("l", 0.012, 9.0, 0.002, mat=laser), 0, 0, 0.47)
    kf(ctx, bar, 0, loc=(2.2, -1.2, 0.468))
    kf(ctx, bar, 1, loc=(4.2, -1.2, 0.468))
    hd = obj("head", rbox("spi", 3.2, 2.2, 1.2, 0.08, 3, mat=mats.white_panel), 0, 0, 0)
    kf(ctx, hd, 0, loc=(2.2, -1.2, 4.2))
    kf(ctx, hd, 1, loc=(4.2, -1.2, 4.2))
    camera(ctx, [(0, (6.3, -5.0, 2.1), (3.2, -1.9, 0.46)), (1, (5.9, -4.6, 1.9), (3.2, -1.9, 0.46))], lens=70, fstop=5.6)


def clean_deposit(ctx):
    stage(ctx, "paste")
    camera(ctx, [(0, (3.9, -3.3, 2.2), (3.1, -2.0, 0.46)), (1, (3.65, -3.0, 1.5), (3.1, -2.0, 0.46))], lens=85, fstop=6.3)


def final_pull(ctx):
    stage(ctx, "reflowed")
    camera(ctx, [(0, (3.72, -2.75, 0.74), (3.1, -2.0, 0.46)),
                 (0.5, (6.2, -6.0, 3.0), (2.2, -1.4, 0.45)),
                 (1, (9.5, -13.5, 8.6), (0.4, -0.3, 0.45))], lens=75, fstop=7.0)


def board_twin(ctx):
    mats, b, root = stage(ctx, "reflowed")
    scan = scan_empty()
    twinify_all(scan, band=0.08, radius=0.008, grid=0.5, edge=2.2)
    # Scan sweeps the board: the left half stays real, the right becomes its model.
    kf(ctx, scan, 0, loc=(6.5, 0, 0))
    kf(ctx, scan, 0.75, loc=(0, 0, 0))
    kf(ctx, scan, 1, loc=(0, 0, 0))
    ctx.s.cycles.transparent_max_bounces = 10
    camera(ctx, [(0, (9.0, -12.5, 7.6), (0, 0, 0.4)), (1, (7.0, -13.4, 7.0), (0, 0, 0.4))], lens=60, fstop=9.0)


def board_feed(ctx):
    """Real board below, its live twin floating above: data rises, adjustments return."""
    mats, b, root = stage(ctx, "reflowed", key=0.75)
    ctx.s.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.14
    m2 = lib.Mats()
    b2 = BoardBuilder(m2, "reflowed")
    root2 = b2.build(mask_material("mask2"))
    root2.location = (0, 0, 4.2)
    root2.rotation_euler[2] = math.radians(0)
    scan = scan_empty(-1000)
    from twin import twinify
    # Only the upper board turns to hologram: scan on Z for the second material set.
    for mat in bpy.data.materials:
        if mat.name.endswith(".001") or mat.name == "mask2":
            twinify(mat, scan, band=0.08, radius=0.008, grid=0.5, edge=2.2)
    ctx.s.cycles.transparent_max_bounces = 10
    ctx.anchor("real", (0, 0, 0.5))
    ctx.anchor("twin", (0, 0, 4.2))
    camera(ctx, [(0, (9.5, -14.5, 7.0), (0, 0, 2.1)), (1, (6.5, -15.0, 6.4), (0, 0, 2.2))], lens=50, fstop=10)


def heatmap(ctx):
    mats, b, root = stage(ctx, "reflowed", key=0.45)
    ctx.s.view_settings.view_transform = "Standard"
    ctx.s.view_settings.look = "None"
    m = b.mask
    n, l = nodes_of(m)
    out = n["Material Output"]
    src = out.inputs["Surface"].links[0].from_socket
    tc = n.new("ShaderNodeTexCoord")
    tx = n.new("ShaderNodeTexImage")
    tx.image = bpy.data.images.load(str(MAPS / "heat.png"))
    tx.image.colorspace_settings.name = "Non-Color"
    l.new(tc.outputs["UV"], tx.inputs["Vector"])
    # Value = progress minus thermal lag, so heavy copper warms last.
    prog = object_prop(m, "heat")
    sub = n.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    l.new(prog.outputs["Fac"], sub.inputs[0])
    l.new(tx.outputs["Color"], sub.inputs[1])
    ramp = n.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    stops = [(0.0, (0.01, 0.03, 0.3)), (0.3, (0.0, 0.5, 0.75)), (0.55, (0.1, 0.9, 0.2)), (0.78, (1.0, 0.8, 0.0)), (1.0, (1.0, 0.1, 0.02))]
    cr.elements[0].position, cr.elements[0].color = stops[0][0], (*stops[0][1], 1)
    cr.elements[1].position, cr.elements[1].color = stops[-1][0], (*stops[-1][1], 1)
    for p, c in stops[1:-1]:
        e = cr.elements.new(p)
        e.color = (*c, 1)
    l.new(sub.outputs[0], ramp.inputs[0])
    em = n.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 0.9
    l.new(ramp.outputs[0], em.inputs["Color"])
    mx = n.new("ShaderNodeAddShader")
    l.new(src, mx.inputs[0])
    l.new(em.outputs[0], mx.inputs[1])
    l.new(mx.outputs[0], out.inputs["Surface"])
    kprop(ctx, b.body, "heat", 0, 0.05)
    kprop(ctx, b.body, "heat", 1, 1.25)
    ctx.anchor("copper", (3.2, 1.6, 0.45))
    camera(ctx, [(0, (6.0, -11.0, 11.0), (0, 0, 0.4)), (1, (4.0, -10.0, 11.5), (0, 0, 0.4))], lens=55, fstop=11)


# Scene: stencil printer ----------------------------------------------------------


def stencil_mesh(mats, data, pad_margin=0.0, region=None):
    w, h = 13.0, 10.0
    th = 0.012
    plate = rbox("stencil", w, h, th, mat=mats.steel)
    o = obj("stencil", plate)
    cutters = bmesh.new()
    for p in data["pads"]:
        px, py = p["x"] * MM, p["y"] * MM
        if region and not (region[0] < px < region[1] and region[2] < py < region[3]):
            continue
        a, b = p["w"] * MM * 0.5, p["h"] * MM * 0.5
        if p.get("thermal"):
            for gx in (-1, 1):
                for gy in (-1, 1):
                    bmesh.ops.create_cube(cutters, size=1, matrix=_box(px + gx * a * 0.46, py + gy * b * 0.46, a * 0.8, b * 0.8))
            continue
        bmesh.ops.create_cube(cutters, size=1, matrix=_box(px, py, a * 2 * 0.92, b * 2 * 0.92))
    me = bpy.data.meshes.new("cut")
    cutters.to_mesh(me)
    cutters.free()
    c = obj("cut", me)
    c.hide_render = True
    c.hide_viewport = True
    mod = o.modifiers.new("holes", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "FAST"
    mod.object = c
    return o


def _box(x, y, w, h):
    from mathutils import Matrix
    return Matrix.Translation((x, y, 0.006)) @ Matrix.Diagonal((w, h, 0.05, 1))


def printer_scene(ctx, state="paste"):
    s = ctx.s
    lib.studio(s, floor_color=(0.2, 0.24, 0.24, 1))
    mats = lib.Mats()
    b = BoardBuilder(mats, state)
    root = b.build()
    root.location.z = 0.42
    obj("support", rbox("support", 16, 12, 0.26, 0.02, 1, mat=mats.alu))
    region = (0.6, 5.0, -3.5, 0.2)
    st = stencil_mesh(mats, b.data, region=region)
    st.location.z = 0.427
    for sx, sy, fw, fh in ((0, -7.3, 18, 2.4), (0, 7.3, 18, 2.4), (-8.5, 0, 2.4, 17), (8.5, 0, 2.4, 17)):
        obj("sframe", rbox("sframe", fw, fh, 0.5, 0.02, 2, mat=mats.alu), sx, sy, 0.44)
    return mats, b, st


def bead_mesh(length=8.0, r=0.16):
    me = bpy.data.meshes.new("bead")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=r, radius2=r, depth=length)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1], cuts=120, use_grid_fill=False)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    return me


def squeegee(ctx):
    mats, b, st = printer_scene(ctx)
    driver = empty("sq", 0, 0, 0)
    for mat in (mats.paste,):
        reveal(mat, driver)
    blade = rbox("blade", 0.03, 8.4, 1.1, 0.004, 1, mat=mats.chrome)
    holder = rbox("holder", 0.5, 8.6, 0.5, 0.05, 2, z0=1.0, mat=mats.alu)
    rig = empty("rig", 0, 0, 0)
    bo = obj("blade", blade, 0, 0, 0, parent=rig)
    ho = obj("holder", holder, 0, 0, 0, parent=rig)
    rig.rotation_euler[1] = math.radians(-30)
    paste_wet = lib.add_noise_bump(principled("wet", (0.2, 0.205, 0.215, 1), 0.35, 0.58), 90, 1.0, 3, 0.15)
    bead = obj("bead", bead_mesh(), 0, 0, 0)
    bead.data.materials.append(paste_wet)
    bead.rotation_euler = (math.radians(90), 0, 0)
    tex = bpy.data.textures.new("lump", "CLOUDS")
    tex.noise_scale = 0.11
    dm = bead.modifiers.new("lump", "DISPLACE")
    dm.texture = tex
    dm.strength = 0.16
    dm.mid_level = 0.5
    x0, x1 = 5.1, 1.6
    for t, x in ((0, x0), (1, x1)):
        kf(ctx, rig, t, loc=(x, -1.6, 0.44))
        kf(ctx, driver, t, loc=(x - 0.18, 0, 0))
        kf(ctx, bead, t, loc=(x - 0.3, -1.6, 0.6), rot=(math.radians(90), (x0 - x) * 5.6, 0))
    from lib import fcurves
    for o in (rig, driver, bead):
        for fc in fcurves(o.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    camera(ctx, [(0, (-0.5, -11.5, 6.8), (3.2, -1.6, 0.5)), (1, (-1.5, -11.0, 6.2), (2.6, -1.6, 0.5))], lens=50, fstop=9)


def wipe(ctx):
    mats, b, st = printer_scene(ctx)
    driver = empty("wipe", 0, 0, 0)
    dirt = lib.add_noise_bump(principled("residue", (0.11, 0.115, 0.125, 1), 0.2, 0.7), 26, 0.8, 2, 0.1)
    reveal(dirt, driver)
    me = rbox("res", 3.6, 3.4, 0.003, mat=dirt)
    obj("res", me, 3.1, -1.8, 0.439)
    cloth = lib.add_noise_bump(principled("cloth", (0.86, 0.87, 0.85, 1), 0, 0.85), 26, 0.6, 3)
    roller = obj("roller", cylinder("roller", 0.28, 4.6, mat=cloth))
    for t, x in ((0, 0.6), (1, 5.8)):
        kf(ctx, roller, t, loc=(x, 0.5, 0.72), rot=(math.radians(90), (x - 0.6) * 3.5, 0))
        kf(ctx, driver, t, loc=(x - 0.5, 0, 0))
    camera(ctx, [(0, (9.5, -11.5, 6.6), (3.0, -1.6, 0.5)), (1, (8.6, -11.0, 6.0), (3.4, -1.6, 0.5))], lens=60, fstop=9)


# Scene: paste at microscopic scale ------------------------------------------------


def micro_scene(ctx, dry=False):
    """A real proportion cross-section: 280 um pad, 100 um stencil, 20-38 um spheres.
    Here 1 BU = 10 um."""
    s = ctx.s
    lib.world(s, strength=0.55)
    area = lib.area_light("key", (-20, -40, 60), (0, 0, 5), 60, 110000, (1, 0.97, 0.93))
    lib.area_light("rim", (40, 40, 30), (0, 0, 5), 8, 26000, (0.8, 1, 0.9), size_y=80)
    mats = lib.Mats()
    w = 28.0  # aperture width
    h = 10.0  # stencil thickness
    depth = 30.0
    for sx in (-1, 1):
        wall = rbox("wall", 40, depth, h, 0.15, 2, mat=mats.steel)
        o = obj("wall", wall, sx * (w / 2 + 20), 0, 0)
        if dry and sx == 1:
            pass
    copper = principled("copper", (0.95, 0.55, 0.32, 1), 1.0, 0.3)
    obj("pad", rbox("pad", w * 1.04, depth, 1.0, 0.05, 1, z0=-1.0, mat=mats.gold))
    obj("cu", rbox("cu", 90, depth, 3.5, z0=-4.5, mat=copper))
    fr4 = lib.add_noise_bump(principled("fr4m", (0.5, 0.45, 0.22, 1), 0, 0.5), 2, 0.5)
    obj("fr4", rbox("fr4", 200, depth, 18, z0=-22.5, mat=fr4))
    flux = bpy.data.materials.new("flux")
    n, l = nodes_of(flux)
    for x in list(n):
        if x.type == "BSDF_PRINCIPLED":
            n.remove(x)
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.97, 0.8, 0.52, 1)
    gl = n.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.22
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.12
    mx = n.new("ShaderNodeMixShader")
    l.new(lw.outputs["Fresnel"], mx.inputs[0])
    l.new(tr.outputs[0], mx.inputs[1])
    l.new(gl.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], n["Material Output"].inputs["Surface"])
    gel = rbox("gel", w - 0.1, depth - 0.2, h * 0.98, 0.2, 2, mat=flux)
    gelo = obj("gel", gel)

    # Rejection-pack spheres in the Type 4 range, 20-38 um across, cut by the front face.
    r = random.Random(4)
    balls = []
    tries = 0
    while len(balls) < 520 and tries < 60000:
        tries += 1
        d = r.uniform(2.0, 3.8) / 2
        p = (r.uniform(-w / 2 + d, w / 2 - d), r.uniform(-depth / 2 - 0.4, 4.0), r.uniform(d, h - d))
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 > (d + q[3]) ** 2 * 0.96 for q in balls):
            balls.append((*p, d))
    sm = bpy.data.meshes.new("ball")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(sm)
    bm.free()
    sm.materials.append(lib.add_noise_bump(principled("ball", (0.84, 0.85, 0.87, 1), 1.0, 0.16), 7, 0.08, 1))
    objs = []
    for i, (x, y, z, d) in enumerate(balls):
        o = obj(f"b{i}", sm, x, y, z)
        o.scale = (d, d, d)
        objs.append(o)
    return mats, gelo, objs, balls, w, h, depth


def paste_spheres(ctx):
    micro_scene(ctx)
    ctx.anchor("sphere", (2.0, -9.0, 5.0))
    camera(ctx, [(0, (-11, -86, 15), (0, 0, 3)), (1, (7, -66, 11), (0, 0, 4))], lens=60, fstop=11.0)


def aperture_dry(ctx):
    """As flux dries, paste clings to the aperture wall and less is released at lift."""
    mats, gelo, balls_o, balls, w, h, depth = micro_scene(ctx, dry=True)
    walls = [o for o in bpy.data.objects if o.name.startswith("wall")]
    stuck = []
    for o, (x, y, z, d) in zip(balls_o, balls):
        near_wall = x > w / 2 - 7.5 or (x < -w / 2 + 5 and z > 5)
        high = z > 5.5
        if near_wall or high:
            stuck.append(o)
    gelo.scale.z = 1.0
    for t in (0, 0.28):
        for wl in walls:
            kf(ctx, wl, t, loc=(wl.location.x, 0, 0))
        for o in stuck:
            kf(ctx, o, t, loc=tuple(o.location))
    lift = 12.0
    for wl in walls:
        kf(ctx, wl, 0.8, loc=(wl.location.x, 0, lift))
        kf(ctx, wl, 1, loc=(wl.location.x, 0, lift))
    for o in stuck:
        kf(ctx, o, 0.8, loc=(o.location.x, o.location.y, o.location.z + lift))
        kf(ctx, o, 1, loc=(o.location.x, o.location.y, o.location.z + lift))
    kf(ctx, gelo, 0.28, scale=(1, 1, 1))
    kf(ctx, gelo, 0.8, scale=(1, 1, 0.62))
    kf(ctx, gelo, 1, scale=(1, 1, 0.62))
    ctx.anchor("wall", (w / 2 - 2, -9.0, 15.0))
    camera(ctx, [(0, (-4, -82, 15), (1, 0, 5)), (1, (-1, -74, 15), (1, 0, 8))], lens=60, fstop=11.0)


# Scene: pick and place -----------------------------------------------------------


def nozzle_tool(mats, name, tip=0.09):
    root = empty(name)
    obj("n1", cylinder("n1", tip * 1.0, 0.5, verts=24, mat=mats.chrome), parent=root)
    obj("n2", cylinder("n2", tip * 2.4, 0.5, z0=0.5, verts=32, bevel=0.03, mat=mats.alu), parent=root)
    obj("n3", cylinder("n3", tip * 4.5, 2.2, z0=1.0, verts=32, bevel=0.05, mat=mats.steel), parent=root)
    obj("n4", cylinder("n4", tip * 5.6, 1.2, z0=3.2, verts=32, bevel=0.05, mat=mats.green_paint), parent=root)
    return root


def pnp_head(mats, count=4, pitch=1.6):
    head = empty("head")
    body = rbox("hb", pitch * count + 1.6, 3.0, 5.0, 0.2, 3, z0=4.6, mat=mats.white_panel)
    obj("hb", body, parent=head)
    obj("rail", rbox("beam", 60, 3.4, 2.4, 0.15, 2, z0=7.6, mat=mats.alu), 0, 3.0, 0)
    noz = []
    for i in range(count):
        n = nozzle_tool(mats, f"noz{i}")
        n.parent = head
        n.location.x = (i - (count - 1) / 2) * pitch
        noz.append(n)
    cam = cylinder("hc", 0.6, 1.4, z0=3.4, mat=mats.nylon)
    obj("hc", cam, pitch * count / 2 + 1.0, -1.0, 0, parent=head)
    return head, noz


def tape_reel(mats, x, y):
    root = empty("reel", x, y, 2.6)
    disc = cylinder("disc", 3.0, 0.2, mat=principled("reel", (0.015, 0.2, 0.07, 1), 0, 0.3, coat=0.3))
    d = obj("d", disc, parent=root)
    d.rotation_euler[1] = math.radians(90)
    return root


def pnp_scene(ctx):
    s = ctx.s
    lib.studio(s, floor_color=(0.22, 0.26, 0.26, 1))
    mats = lib.Mats()
    b = BoardBuilder(mats, "paste")
    root = b.build()
    root.location.z = 0.42
    obj("support", rbox("support", 26, 16, 0.26, 0.02, 1, mat=mats.alu))
    return mats, b


def part_0603(mats):
    me = {}
    par = empty("part")
    w, d, h, t = (v * MM for v in layout.CHIP["1206"])
    obj("b", rbox("pb", w - 2 * t * 0.9, d * 0.98, h, 0.05 * MM, 2, mat=mats.ceramic), parent=par)
    for s in (-1, 1):
        obj("t", rbox("pt", t, d, h * 1.02, 0.045 * MM, 2, mat=mats.tin), s * (w / 2 - t / 2), 0, 0, parent=par)
    return par


def pnp_wide(ctx):
    mats, b = pnp_scene(ctx)
    head, noz = pnp_head(mats)
    parts = []
    for i, n in enumerate(noz):
        p = part_0603(mats)
        p.parent = n
        p.location.z = -0.1
        parts.append(p)
    # Head sweeps in from the feeders, hovering over the U1 corner.
    kf(ctx, head, 0, loc=(-5.5, -1.4, 1.2))
    kf(ctx, head, 0.55, loc=(1.8, -1.4, 1.2))
    kf(ctx, head, 1, loc=(1.8, -1.4, 1.2))
    for t, z in ((0.55, 0.0), (0.7, -0.62), (0.8, -0.62), (1.0, 0.0)):
        kf(ctx, noz[1], t, loc=(noz[1].location.x, 0, z))
    camera(ctx, [(0, (-15, -24, 13), (-1.5, -0.5, 3.4)), (1, (-9, -25, 11), (1.5, -0.8, 3.0))], lens=55, fstop=11)


def pnp_macro(ctx):
    mats, b = pnp_scene(ctx)
    n = nozzle_tool(mats, "noz")
    part = part_0603(mats)
    x, y = 2.6, -1.1
    h = 0.42 + 0.05
    # The part leaves the nozzle at contact; vacuum off, paste holds it.
    kf(ctx, n, 0, loc=(x, y, h + 1.5))
    kf(ctx, n, 0.45, loc=(x, y, h + 0.1))
    kf(ctx, n, 0.6, loc=(x, y, h + 0.1))
    kf(ctx, n, 1, loc=(x, y, h + 1.6))
    kf(ctx, part, 0, loc=(x, y, h + 1.42))
    kf(ctx, part, 0.45, loc=(x, y, h + 0.02))
    kf(ctx, part, 1, loc=(x, y, h + 0.02))
    camera(ctx, [(0, (4.3, -3.2, 1.1), (x, y, 0.8)), (1, (3.95, -3.0, 0.95), (x, y, 0.62))], lens=90, fstop=5.6)


def nozzle_drop(ctx):
    mats, b = pnp_scene(ctx)
    wear = principled("worn", (0.4, 0.34, 0.26, 1), 1.0, 0.55)
    n = nozzle_tool(mats, "noz")
    for c in n.children:
        if c.name.startswith("n1"):
            c.data.materials[0] = wear
    part = part_0603(mats)
    x, y = 2.6, -1.1
    h = 0.47
    kf(ctx, n, 0, loc=(x - 0.5, y, h + 0.8))
    kf(ctx, n, 0.45, loc=(x, y, h + 0.7))
    kf(ctx, n, 1, loc=(x, y, h + 0.7))
    kf(ctx, part, 0, loc=(x - 0.5, y, h + 0.72), rot=(0, 0, 0))
    kf(ctx, part, 0.45, loc=(x, y, h + 0.62), rot=(0, 0, 0))
    kf(ctx, part, 0.72, loc=(x + 0.26, y - 0.2, h + 0.02), rot=(1.2, 0.5, 0.8))
    kf(ctx, part, 1, loc=(x + 0.3, y - 0.22, h + 0.02), rot=(math.pi, 0.5, 0.8))
    ctx.anchor("tip", (x, y, h + 0.7))
    camera(ctx, [(0, (5.6, -4.8, 1.6), (x, y, 1.0)), (1, (5.2, -4.4, 1.45), (x, y, 0.95))], lens=70, fstop=7.0)


# Scene: reflow ---------------------------------------------------------------------


def oven_cut(ctx):
    """Cutaway through an eight-zone oven at close range; heater glow follows a real profile."""
    s = ctx.s
    lib.studio(s, floor_color=(0.3, 0.34, 0.34, 1), key=0.6)
    mats = lib.Mats()
    b = BoardBuilder(mats, "placed")
    root = b.build()
    coll = board_collection(root)
    zw = 60.0
    w = zw * 8
    temps = (0.22, 0.32, 0.36, 0.4, 0.46, 0.74, 1.0, 0.1)  # preheat, soak, peak, cool
    obj("back", rbox("oven_back", w, 2, 60, mat=mats.steel), 0, 24, -30)
    for sgn in (-1, 1):
        obj("shell", rbox("shell", w, 56, 3, mat=mats.white_panel), 0, 0, sgn * 30 - 1.5)
    for i in range(8):
        x = -w / 2 + zw * (i + 0.5)
        g = temps[i]
        hot = mats._emit(f"heat{i}", (1.0, lerp(0.28, 0.2, g), 0.03, 1) if g > 0.15 else (0.25, 0.6, 1.0, 1), 0.6 + 7 * g)
        for sgn in (-1, 1):
            for r in range(9):  # IR elements behind a slotted plenum, as in a convection oven.
                obj("rod", cylinder(f"e{i}", 0.5, 46, verts=12, mat=hot), x - zw / 2 + (r + 1) * zw / 10, 23, sgn * 21).rotation_euler[0] = math.radians(90)
            for j in range(10):
                pl = rbox(f"pl{i}{j}", 1.1, 46, 0.5, 0.04, 1, mat=mats.steel)
                obj("slat", pl, x - zw / 2 + (j + 0.5) * zw / 10, 0, sgn * 15)
        div = rbox(f"w{i}", 1.2, 46, 56, 0.1, 1, mat=mats.steel)
        obj("div", div, x - zw / 2, 0, -28)
        ctx.anchor(f"z{i + 1}", (x, -10, 16))
    for sgn in (-1, 1):
        obj("chain", rbox("chain", w + 40, 1.0, 1.0, mat=mats.rubber), 0, sgn * 3.9, -0.5)
        obj("rail", rbox("crail", w + 40, 1.4, 2.4, 0.2, 1, mat=mats.alu), 0, sgn * 4.9, -3)
    speed = 8.0
    dur = ctx.frames / 24
    for i in range(30):
        x0 = -520 + i * 34
        inst = instance(coll, f"b{i}", x0, 0, 0.3)
        key_linear(inst, s, [(1, (x0, 0, 0.3)), (ctx.frames, (x0 + speed * dur, 0, 0.3))])
    camera(ctx, [(0, (-30, -80, 25), (-16, 0, 1)), (1, (130, -76, 23), (144, 0, 1))], lens=50, fstop=0)


def melt(ctx):
    """One large chip on two pads: paste slumps, wets and pulls the part square."""
    s = ctx.s
    lib.world(s, top=(0.75, 0.6, 0.45), bottom=(0.16, 0.1, 0.06), strength=0.75)
    lib.area_light("ir", (1.0, -3.0, 9.0), (0, 0, 0), 9, 2200, (1.0, 0.66, 0.34))
    lib.area_light("strip", (-7, 5, 4), (0, 0, 0), 1.4, 1100, (1, 0.9, 0.8), size_y=14)
    mats = lib.Mats()
    mask = principled("pmask", (0.0012, 0.05, 0.02, 1), 0, 0.2, coat=1.0)
    obj("mask", rbox("pm", 20, 20, 0.1, z0=-0.1, mat=mask))
    w, d, h, t = 3.2, 1.6, 0.9, 0.5  # 1206 at x10 scale below
    k = 0.5
    paste = principled("mpaste", (0.42, 0.43, 0.45, 1), 0.75, 0.62)
    lib.add_noise_bump(paste, 34, 0.9, 1, 0.2)
    solder = principled("msolder", (0.9, 0.91, 0.92, 1), 1.0, 0.08)
    # Paste and molten solder share one mesh; 'melt' blends between them.
    m = bpy.data.materials.new("blend")
    n, l = nodes_of(m)
    for x in list(n):
        if x.type == "BSDF_PRINCIPLED":
            n.remove(x)

    def copy_nodes(src):
        nt = src.node_tree
        p = n.new("ShaderNodeBsdfPrincipled")
        b = nt.nodes["Principled BSDF"]
        for name in ("Base Color", "Metallic", "Roughness"):
            p.inputs[name].default_value = b.inputs[name].default_value
        return p

    a = copy_nodes(paste)
    a.inputs["Roughness"].default_value = 0.7
    noi = n.new("ShaderNodeTexNoise")
    noi.inputs["Scale"].default_value = 40
    noi.inputs["Detail"].default_value = 1
    bu = n.new("ShaderNodeBump")
    bu.inputs["Strength"].default_value = 0.9
    bu.inputs["Distance"].default_value = 0.03
    l.new(noi.outputs["Fac"], bu.inputs["Height"])
    l.new(bu.outputs[0], a.inputs["Normal"])
    c = copy_nodes(solder)
    attr = n.new("ShaderNodeAttribute")
    attr.attribute_type = "OBJECT"
    attr.attribute_name = "melt"
    mx = n.new("ShaderNodeMixShader")
    l.new(attr.outputs["Fac"], mx.inputs[0])
    l.new(a.outputs[0], mx.inputs[1])
    l.new(c.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], n["Material Output"].inputs["Surface"])

    pads = []
    for sx in (-1, 1):
        obj("pad", rbox("pad", 1.7 * k * 2, 2.0 * k * 2, 0.06, 0.01, 1, mat=mats.gold), sx * 1.7, 0, 0)
        dep = rbox("dep", 3.0, 3.5, 0.5, 0.04, 2, z0=0, mat=m)
        o = obj("dep", dep, sx * 1.7, 0, 0.06)
        fil = fillet_big(m)
        f = obj("fil", fil, sx * 2.72, 0, 0.06, 0 if sx > 0 else 180)
        kprop(ctx, o, "melt", 0, 0)
        kprop(ctx, o, "melt", 0.36, 0)
        kprop(ctx, o, "melt", 0.5, 1)
        kf(ctx, o, 0.36, scale=(1, 1, 1))
        kf(ctx, o, 0.58, scale=(1.02, 1.0, 0.16))
        f["melt"] = 1.0
        kf(ctx, f, 0.4, scale=(0.3, 1, 0.02))
        kf(ctx, f, 0.62, scale=(1, 1, 1))
        pads.append((o, f))
    part = empty("part")
    pw, pd, ph, pt = 6.4, 3.2, 1.8, 1.0
    obj("b", rbox("cb", pw - 2 * pt * 0.9, pd * 0.98, ph, 0.08, 2, mat=mats.ceramic), parent=part)
    for sx in (-1, 1):
        obj("t", rbox("ct", pt, pd, ph * 1.02, 0.07, 2, mat=mats.tin), sx * (pw / 2 - pt / 2), 0, 0, parent=part)
    # Placed slightly crooked; surface tension of the molten alloy pulls it square.
    kf(ctx, part, 0.38, loc=(0.2, 0.26, 0.56), rot=(0, 0, math.radians(8)))
    kf(ctx, part, 0.72, loc=(0, 0, 0.12), rot=(0, 0, 0))
    camera(ctx, [(0, (8.5, -15.5, 5.6), (0, 0, 0.5)), (1, (7.2, -14.0, 4.6), (0, 0, 0.5))], lens=60, fstop=8.0)
    ctx.s.frame_end = ctx.frames


def fillet_big(mat):
    prof = [(0.0, 0.0)]
    for i in range(16):
        t = i / 15
        prof.append((1.15 * (1 - t), 1.25 * (1 - (1 - t) ** 0.4)))
    return loft("bigf", prof[::-1], 3.1, mat)


# Scene: inspection -----------------------------------------------------------------


def aoi_head(mats):
    """Camera over a tiered red/green/blue dome light, the classic AOI optical stack."""
    root = empty("aoi")
    me = bpy.data.meshes.new("dome")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=64, radius1=1.9, radius2=0.8, depth=1.6)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats.grey_panel)
    obj("dome", me, 0, 0, 1.9, parent=root)
    obj("body", cylinder("ab", 0.8, 3.2, z0=2.7, bevel=0.05, mat=mats.white_panel), parent=root)
    obj("collar", cylinder("ac", 0.86, 0.14, z0=3.4, mat=mats.green_paint), parent=root)
    obj("lens", cylinder("al", 0.34, 0.5, z0=2.3, mat=mats.nylon), parent=root)
    for i, (r, z, col) in enumerate(((1.82, 1.25, (1, 0.04, 0.03, 1)), (1.5, 1.72, (0.03, 1, 0.1, 1)), (1.18, 2.15, (0.05, 0.2, 1, 1)))):
        ringm = mats._emit(f"ring{i}", col, 5)
        tor = bpy.data.meshes.new("t")
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=False, radius=r, segments=64)
        bm.to_mesh(tor)
        bm.free()
        tor.materials.append(ringm)
        o = obj(f"ring{i}", tor, 0, 0, z, parent=root)
        o.modifiers.new("sk", "SKIN")
        for v in o.data.skin_vertices[0].data:
            v.radius = (0.05, 0.05)
    return root


def aoi_pass(ctx):
    mats, b, root = stage(ctx, "reflowed")
    head = aoi_head(mats)
    kf(ctx, head, 0, loc=(-1.5, 0.4, 0.05))
    kf(ctx, head, 1, loc=(3.0, -2.0, 0.05))
    camera(ctx, [(0, (11.0, -16.5, 8.2), (0.6, -0.8, 1.6)), (1, (9.4, -16.8, 7.6), (1.6, -1.0, 1.5))], lens=55, fstop=9.0)
    ctx.anchor("u1", (3.1, -2.0, 0.55))
    ctx.anchor("u2", (-0.6, 0.6, 0.55))
    ctx.anchor("u3", (2.4, 1.4, 0.55))
    ctx.anchor("u5", (0.8, -1.9, 0.55))


def aoi_cam(ctx):
    mats, b, root = stage(ctx, "reflowed", key=0.8)
    head = aoi_head(mats)
    kf(ctx, head, 0, loc=(2.3, -1.2, 0.05))
    kf(ctx, head, 1, loc=(3.3, -2.1, 0.05))
    camera(ctx, [(0, (7.6, -8.6, 2.6), (3.0, -1.8, 1.4)), (1, (7.0, -8.2, 2.4), (3.2, -1.9, 1.3))], lens=50, fstop=8.0)


XRAY_DENSITY = {"etch": 1.0, "gold": 0.6, "tin": 0.55, "solder": 0.3, "chrome": 0.6, "alu": 0.86, "epoxy": 0.97, "ceramic": 0.8,
                "res_body": 0.92, "soldermask": 0.985, "fr4": 0.985, "paste": 0.5, "copperx": 0.72, "wire": 0.5, "die": 0.74}


def xray_mats():
    """Swap every material for tinted transparency so stacked metal darkens like a radiograph."""
    for mat in bpy.data.materials:
        n, l = nodes_of(mat)
        k = XRAY_DENSITY.get(mat.name, 0.9)
        for x in list(n):
            if x.type != "OUTPUT_MATERIAL":
                n.remove(x)
        tr = n.new("ShaderNodeBsdfTransparent")
        tr.inputs["Color"].default_value = (k, k, k, 1)
        l.new(tr.outputs[0], n["Material Output"].inputs["Surface"])


def xray_board(ctx, weak=False):
    s = ctx.s
    w = bpy.data.worlds.new("w")
    s.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.96, 0.98, 0.97, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    mats = lib.Mats()
    b = BoardBuilder(mats, "reflowed")
    root = b.build()
    die_m = principled("die", (1, 1, 1, 1))
    wire_m = principled("wire", (1, 1, 1, 1))
    cx, cy = 3.1, -2.0
    obj("die", rbox("die", 0.34, 0.34, 0.02, mat=die_m), cx, cy, 0.075)
    obj("paddle", rbox("paddle", 0.33, 0.33, 0.012, mat=mats.gold), cx, cy, 0.03)
    for i in range(8):
        o = (i - 3.5) * 0.05
        for dx, dy in ((o, -1), (o, 1), (-1, o), (1, o)):
            a = (dx * 0.17 if abs(dy) == 1 else dx * 0.15, dy * 0.15 if abs(dy) == 1 else dy * 0.17)
            e = (dx * 0.23 if abs(dy) != 1 else dx, dy * 0.23 if abs(dy) == 1 else dy)
            me = bpy.data.meshes.new("w")
            me.from_pydata([(a[0], a[1], 0.08), ((a[0] + e[0]) / 2, (a[1] + e[1]) / 2, 0.11), (e[0], e[1], 0.04)], [(0, 1), (1, 2)], [])
            wo = obj("wire", me, cx, cy, 0)
            wo.data.materials.append(wire_m)
            wo.modifiers.new("sk", "SKIN")
            for v in wo.data.skin_vertices[0].data:
                v.radius = (0.0024, 0.0024)
    if weak:
        # Starved joints on the side that printed thin, voids in the rest.
        hide = 0
        for o in b.fillets:
            if o.parent and o.parent.name == "U1" and o.location.x > 0.2:
                o.scale = (0.28, 0.75, 0.3)
    xray_mats()
    s.cycles.transparent_max_bounces = 48
    s.cycles.min_transparent_bounces = 48
    s.cycles.max_bounces = 48
    s.cycles.samples = 16
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.view_settings.exposure = 0.25
    return b


def xray(ctx):
    xray_board(ctx)
    camera(ctx, [(0, (3.1, -2.02, 4.2), (3.1, -2.0, 0)), (1, (3.1, -2.02, 2.4), (3.1, -2.0, 0))], lens=90, fstop=0)


def xray_weak(ctx):
    xray_board(ctx, weak=True)
    camera(ctx, [(0, (3.1, -2.02, 2.3), (3.1, -2.0, 0)), (1, (3.1, -2.02, 2.1), (3.1, -2.0, 0))], lens=90, fstop=0)
    ctx.anchor("weak", (3.36, -2.0, 0.05))


def test_probe(ctx):
    mats, b, root = stage(ctx, "reflowed")
    arms = []
    for i, (x, y) in enumerate(((2.3, -1.2), (-0.6, -1.5))):
        rig = empty(f"probe{i}")
        obj("sh", cylinder("ps", 0.07, 2.4, z0=0.34, verts=20, mat=mats.gold), parent=rig)
        obj("tip", cylinder("pt", 0.018, 0.34, verts=12, mat=mats.chrome), parent=rig)
        obj("arm", rbox("pa", 0.5, 0.5, 2.8, 0.05, 2, z0=2.6, mat=mats.white_panel), parent=rig)
        rig.rotation_euler[0] = math.radians(10 if i else -10)
        z0 = 0.52
        kf(ctx, rig, 0, loc=(x - 0.8, y, z0 + 0.7))
        kf(ctx, rig, 0.35, loc=(x, y, z0 + 0.7))
        kf(ctx, rig, 0.52, loc=(x, y, z0))
        kf(ctx, rig, 0.8, loc=(x, y, z0))
        kf(ctx, rig, 1, loc=(x, y, z0 + 0.6))
        arms.append(rig)
    camera(ctx, [(0, (6.8, -9.6, 3.0), (0.9, -1.2, 0.9)), (1, (5.8, -9.2, 2.7), (0.9, -1.2, 0.8))], lens=60, fstop=6.3)


# Scene: map vs. traffic app --------------------------------------------------------


def map_phone(ctx):
    s = ctx.s
    lib.world(s, strength=0.5)
    lib.area_light("key", (-8, -6, 30), (0, 0, 0), 18, 3800, (1, 0.96, 0.9))
    lib.area_light("strip", (16, 8, 9), (0, 0, 0), 3, 2200, (0.9, 0.98, 1), size_y=30)
    mats = lib.Mats()
    desk = lib.add_noise_bump(principled("desk", (0.3, 0.2, 0.12, 1), 0, 0.3), 3, 0.05, 2, 0.08)
    obj("desk", rbox("desk", 240, 240, 2, z0=-2, mat=desk))

    def textured(name, img, rough):
        m = principled(name, (1, 1, 1, 1), 0, rough)
        n, l = nodes_of(m)
        t = n.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(MAPS / img))
        tc = n.new("ShaderNodeTexCoord")
        l.new(tc.outputs["UV"], t.inputs["Vector"])
        l.new(t.outputs["Color"], n["Principled BSDF"].inputs["Base Color"])
        return m, n, l, t, tc

    paper, *_ = textured("mapmat", "paper_map.png", 0.62)
    w, h = 42.0, 29.7
    me = bpy.data.meshes.new("paper")
    bm = bmesh.new()
    nx, ny = 32, 24
    uv = bm.loops.layers.uv.new("UVMap")
    verts = {}
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = (i / nx - 0.5) * w, (j / ny - 0.5) * h
            # Soft concertina folds, like a real map opened flat.
            z = 0.28 * abs(math.sin(i / nx * math.pi * 3)) + 0.1 * abs(math.sin(j / ny * math.pi * 2))
            verts[(i, j)] = bm.verts.new((x, y, z))
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((verts[(i, j)], verts[(i + 1, j)], verts[(i + 1, j + 1)], verts[(i, j + 1)]))
            f.smooth = (i % (nx // 3)) != 0
            for lo in f.loops:
                c = lo.vert.co
                lo[uv].uv = (c.x / w + 0.5, c.y / h + 0.5)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(paper)
    po = obj("map", me, -8.0, 0, 0.05, -4)

    ph = empty("phone")
    body = rbox("pb", 7.6, 15.8, 0.8, 0.34, 6, mat=principled("ph", (0.02, 0.022, 0.025, 1), 1.0, 0.25))
    obj("pb", body, parent=ph)
    sc, n, l, tex, tc = textured("screen", "phone_ui.png", 0.08)
    for lk in list(tex.outputs["Color"].links):
        l.remove(lk)
    n["Principled BSDF"].inputs["Base Color"].default_value = (0, 0, 0, 1)
    e = n.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = 0.8
    l.new(tex.outputs["Color"], e.inputs["Color"])
    add = n.new("ShaderNodeAddShader")
    l.new(n["Principled BSDF"].outputs[0], add.inputs[0])
    l.new(e.outputs[0], add.inputs[1])
    l.new(add.outputs[0], n["Material Output"].inputs["Surface"])
    gm = bpy.data.meshes.new("gl")
    gm.from_pydata([(-3.5, -7.5, 0), (3.5, -7.5, 0), (3.5, 7.5, 0), (-3.5, 7.5, 0)], [], [(0, 1, 2, 3)])
    gm.uv_layers.new(name="UVMap")
    for lp, uv2 in zip(gm.uv_layers[0].data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp.uv = uv2
    gm.materials.append(sc)
    obj("gl", gm, 0, 0, 0.805, parent=ph)
    ph.rotation_euler = (math.radians(14), math.radians(-5), math.radians(10))
    kf(ctx, ph, 0, loc=(30, -10, 5.0))
    kf(ctx, ph, 0.38, loc=(30, -10, 5.0))
    kf(ctx, ph, 0.6, loc=(13.5, 0, 3.4))
    kf(ctx, ph, 1, loc=(13.5, 0, 3.4))
    camera(ctx, [(0, (-11, -35, 30), (-6, 0, 0)), (0.5, (-2, -35, 31), (2, 0, 1)), (1, (9, -22, 22), (11, 0, 2))], lens=50, fstop=9)


# Scene: the production line ---------------------------------------------------------


def line_scene(ctx):
    s = ctx.s
    lib.world(s, strength=0.3)
    mats = lib.Mats()
    room = factory_room(mats)
    li = Line(mats)
    li.build()
    b = BoardBuilder(mats, "reflowed")
    root = b.build()
    root.location = (0, 0, 0)
    coll = board_collection(root)
    for k, x in enumerate((-250, 250)):
        lib.area_light(f"fill{k}", (x, -260, 340), (x, 0, 80), 520, 1500000, (1, 0.98, 0.95), size_y=420)
    z = BELT_Z + T
    speed = 16.0  # cm/s, a realistic conveyor pace
    dur = ctx.frames / 24
    for i in range(46):
        x0 = -1150 + i * 52
        inst = instance(coll, f"bd{i}", x0, 0, z)
        key_linear(inst, s, [(1, (x0, 0, z)), (ctx.frames, (x0 + speed * dur, 0, z))])
    return mats, li


def line_wide(ctx):
    line_scene(ctx)
    camera(ctx, [(0, (-760, -330, 175), (-150, 0, 95)), (1, (-640, -340, 165), (-40, 0, 95))], lens=34, fstop=0)


def line_track(ctx):
    mats, li = line_scene(ctx)
    z = BELT_Z + 2
    camera(ctx, [(0, (-890, -40, 112), (-820, 0, z)), (1, (-842, -40, 110), (-772, 0, z))], lens=45, fstop=5.6)


def ordinary(ctx):
    line_scene(ctx)
    camera(ctx, [(0, (-40, -470, 215), (-130, 0, 100)), (1, (-170, -460, 200), (-260, 0, 100))], lens=30, fstop=0)


def twin_setup(ctx):
    mats, li = line_scene(ctx)
    scan = scan_empty()
    twinify_all(scan, skip=("glass",), band=14.0, radius=1.2, grid=40.0)
    ctx.s.cycles.transparent_max_bounces = 14
    ctx.s.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.035
    return scan


def twin_reveal(ctx):
    scan = twin_setup(ctx)
    kf(ctx, scan, 0, loc=(1400, 0, 0))
    kf(ctx, scan, 0.08, loc=(1400, 0, 0))
    kf(ctx, scan, 0.9, loc=(-1000, 0, 0))
    kf(ctx, scan, 1, loc=(-1000, 0, 0))
    camera(ctx, [(0, (-720, -420, 190), (-120, 0, 95)), (1, (-560, -430, 190), (20, 0, 95))], lens=32, fstop=0)


def twin_orbit(ctx):
    scan = twin_setup(ctx)
    scan.location.x = -1500
    camera(ctx, [(0, (-560, -430, 190), (20, 0, 95)), (1, (40, -380, 250), (160, 0, 95))], lens=32, fstop=0)


# Stills used as motion-graphics backdrops (rendered once, one frame each) ---------------


def plate_chip(ctx):
    stage(ctx, "reflowed")
    camera(ctx, [(0, (5.6, -4.4, 1.25), (3.1, -2.0, 0.42)), (1, (5.6, -4.4, 1.25), (3.1, -2.0, 0.42))], lens=100, fstop=4)


def plate_line(ctx):
    line_scene(ctx)
    camera(ctx, [(0, (-300, -420, 200), (40, 0, 90)), (1, (-300, -420, 200), (40, 0, 90))], lens=30, fstop=0)


def plate_twin(ctx):
    twin_setup(ctx).location.x = -1500
    camera(ctx, [(0, (-300, -420, 200), (40, 0, 90)), (1, (-300, -420, 200), (40, 0, 90))], lens=30, fstop=0)


def joint_macro(ctx):
    stage(ctx, "reflowed")
    camera(ctx, [(0, (3.76, -2.8, 0.66), (3.1, -2.2, 0.47)), (1, (3.5, -2.92, 0.64), (3.0, -2.25, 0.47))], lens=100, fstop=5)


def plate_oven(ctx):
    oven_cut(ctx)


SHOTS = {k: v for k, v in globals().items() if callable(v) and getattr(v, "__module__", "") == __name__
         and k not in ("stage", "camera", "kf", "kprop", "object_prop", "reveal", "stencil_mesh", "printer_scene",
                       "bead_mesh", "micro_scene", "nozzle_tool", "pnp_head", "tape_reel", "pnp_scene", "part_0603",
                       "fillet_big", "aoi_head", "xray_mats", "xray_board", "line_scene", "twin_setup", "Ctx", "_box")}
