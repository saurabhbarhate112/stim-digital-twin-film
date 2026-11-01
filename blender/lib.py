"""Reusable Blender building blocks: render setup, studio, materials, mesh helpers.

Scene scale: 1 Blender unit = 1 mm x 0.1, i.e. 1 BU = 1 cm, so a 100 mm board is
10 BU wide and camera depth of field behaves like a real macro lens.
"""
import math
import os
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
MAPS = ROOT / "build" / "maps"
MM = 0.1  # one millimetre in Blender units

# STIM palette (from stimcanada.com) as linear-ish colours.
GREEN = (0.0024, 0.19, 0.058, 1)
MINT = (0.06, 0.95, 0.42, 1)
FOREST = (0.004, 0.022, 0.014, 1)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 0.01
    return s


def render_setup(s, samples=32, res=(1280, 720), fps=24, motion_blur=True):
    s.render.engine = "CYCLES"
    c = s.cycles
    c.device = "CPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.04
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.denoising_prefilter = "FAST"
    c.seed = 7  # A fixed seed keeps the leftover noise still between frames.
    c.use_animated_seed = False
    c.max_bounces = 4
    c.diffuse_bounces = 1
    c.glossy_bounces = 2
    c.transmission_bounces = 3
    c.volume_bounces = 0
    c.transparent_max_bounces = 4
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 4.0
    c.blur_glossy = 0.5
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.fps = fps
    s.render.use_motion_blur = motion_blur
    s.render.motion_blur_shutter = 0.5
    s.render.use_persistent_data = True
    s.render.image_settings.file_format = "JPEG"
    s.render.image_settings.quality = 96
    s.render.film_transparent = False
    v = s.view_settings
    v.view_transform = "AgX"
    v.look = "AgX - Medium High Contrast"
    v.exposure = 0.0


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def nodes_of(mat):
    mat.use_nodes = True
    return mat.node_tree.nodes, mat.node_tree.links


def principled(name, color, metallic=0.0, rough=0.5, coat=0.0, coat_rough=0.05, spec=0.5, ior=1.5):
    m = bpy.data.materials.new(name)
    n, _ = nodes_of(m)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = coat_rough
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["IOR"].default_value = ior
    return m


def add_noise_bump(mat, scale=400.0, strength=0.2, detail=2.0, rough_var=0.0):
    n, l = nodes_of(mat)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = detail
    l.new(tc.outputs["Object"], noise.inputs["Vector"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.02
    l.new(noise.outputs["Fac"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    if rough_var:
        base = b.inputs["Roughness"].default_value
        mr = n.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = max(0, base - rough_var)
        mr.inputs["To Max"].default_value = min(1, base + rough_var)
        l.new(noise.outputs["Fac"], mr.inputs["Value"])
        l.new(mr.outputs["Result"], b.inputs["Roughness"])
    return mat


def brushed(mat, axis=(1, 0.002, 1), scale=900.0, strength=0.12):
    """Anisotropic-looking brushed metal from stretched noise."""
    n, l = nodes_of(mat)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = axis
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 1.0
    l.new(mp.outputs["Vector"], noise.inputs["Vector"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.01
    l.new(noise.outputs["Fac"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return mat


class Mats:
    """One shared material library per scene."""

    def __init__(self):
        self.gold = principled("gold", (1.0, 0.71, 0.33, 1), 1.0, 0.22)
        self.tin = add_noise_bump(principled("tin", (0.82, 0.83, 0.84, 1), 1.0, 0.3), 900, 0.1, 1)
        self.solder = principled("solder", (0.9, 0.91, 0.92, 1), 1.0, 0.09)
        self.paste = add_noise_bump(principled("paste", (0.42, 0.43, 0.45, 1), 0.75, 0.62), 1400, 0.9, 1, 0.2)
        self.epoxy = add_noise_bump(principled("epoxy", (0.0035, 0.0035, 0.004, 1), 0.0, 0.36), 2500, 0.05, 1)
        self.ceramic = add_noise_bump(principled("ceramic", (0.3, 0.19, 0.09, 1), 0.0, 0.5), 1600, 0.06, 1)
        self.etch = principled("etch", (0.5, 0.52, 0.52, 1), 0.0, 0.7)
        self.res_body = principled("res_body", (0.004, 0.004, 0.0045, 1), 0.0, 0.42)
        self.alu = brushed(principled("alu", (0.86, 0.87, 0.88, 1), 1.0, 0.24))
        self.steel = brushed(principled("steel", (0.72, 0.73, 0.75, 1), 1.0, 0.2))
        self.chrome = principled("chrome", (0.9, 0.9, 0.92, 1), 1.0, 0.06)
        self.rubber = principled("rubber", (0.02, 0.02, 0.022, 1), 0.0, 0.7)
        self.nylon = principled("nylon", (0.012, 0.012, 0.013, 1), 0.0, 0.4)
        self.white_panel = principled("white_panel", (0.82, 0.84, 0.84, 1), 0.0, 0.34, coat=0.3, coat_rough=0.2)
        self.grey_panel = principled("grey_panel", (0.14, 0.17, 0.17, 1), 0.2, 0.42)
        self.green_paint = principled("green_paint", (0.004, 0.14, 0.05, 1), 0.0, 0.32, coat=0.5)
        self.glass = self._glass()
        self.led = self._emit("led", (0.1, 1.0, 0.25, 1), 6)

    @staticmethod
    def _glass():
        m = bpy.data.materials.new("glass")
        n, _ = nodes_of(m)
        b = n["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.92, 0.97, 0.96, 1)
        b.inputs["Roughness"].default_value = 0.02
        b.inputs["Transmission Weight"].default_value = 1.0
        b.inputs["IOR"].default_value = 1.2
        return m

    @staticmethod
    def _emit(name, color, strength):
        m = bpy.data.materials.new(name)
        n, l = nodes_of(m)
        for x in list(n):
            if x.type == "BSDF_PRINCIPLED":
                n.remove(x)
        e = n.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = color
        e.inputs["Strength"].default_value = strength
        l.new(e.outputs[0], n["Material Output"].inputs["Surface"])
        return m


def _mark_sharp(bm, angle=35):
    lim = math.radians(angle)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if e.is_manifold and e.calc_face_angle(0) > lim:
            e.smooth = False


def rbox(name, w, d, h, bevel=0.0, segments=2, z0=0.0, mat=None):
    """Box with bevelled edges; its underside rests at z0."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= w
        v.co.y *= d
        v.co.z = v.co.z * h + h / 2 + z0
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=bevel, segments=segments, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    _mark_sharp(bm)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    return me


def cylinder(name, r, h, z0=0.0, verts=48, bevel=0.0, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=h)
    for v in bm.verts:
        v.co.z += h / 2 + z0
    if bevel:
        rim = [e for e in bm.edges if e.calc_face_angle(0) > 1.0]
        bmesh.ops.bevel(bm, geom=rim, offset=bevel, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
    _mark_sharp(bm)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    return me


def loft(name, profile, length, mat=None):
    """Extrude a closed XZ polygon along Y, centred on y=0 (leads, fillets, rails)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new((x, -length / 2, z)) for x, z in profile]
    b = [bm.verts.new((x, length / 2, z)) for x, z in profile]
    n = len(profile)
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    _mark_sharp(bm, 50)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    return me


def obj(name, me, x=0.0, y=0.0, z=0.0, rot=0.0, parent=None, coll=None):
    o = bpy.data.objects.new(name, me)
    o.location = (x, y, z)
    o.rotation_euler = (0, 0, math.radians(rot))
    (coll or bpy.context.scene.collection).objects.link(o)
    if parent:
        o.parent = parent
    return o


def empty(name, x=0.0, y=0.0, z=0.0, parent=None):
    o = bpy.data.objects.new(name, None)
    o.location = (x, y, z)
    bpy.context.scene.collection.objects.link(o)
    if parent:
        o.parent = parent
    return o


def area_light(name, loc, target, size, power, color=(1, 1, 1), shape="RECTANGLE", size_y=None):
    li = bpy.data.lights.new(name, "AREA")
    li.shape = shape
    li.size = size
    if size_y:
        li.size_y = size_y
    li.energy = power
    li.color = color
    o = bpy.data.objects.new(name, li)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return o


def world(s, top=(0.62, 0.72, 0.74), bottom=(0.1, 0.13, 0.13), strength=0.32):
    """Bright high-key sky so metal always has something clean to reflect."""
    w = bpy.data.worlds.new("world")
    s.world = w
    w.use_nodes = True
    n, l = w.node_tree.nodes, w.node_tree.links
    bg = n["Background"]
    bg.inputs["Strength"].default_value = strength
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (*bottom, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (*top, 1)
    m = n.new("ShaderNodeMapRange")
    m.inputs["From Min"].default_value = -1
    m.inputs["From Max"].default_value = 1
    l.new(sep.outputs["Z"], m.inputs["Value"])
    l.new(m.outputs[0], ramp.inputs[0])
    l.new(ramp.outputs[0], bg.inputs["Color"])
    return w


def cyclorama(mats_color=(0.72, 0.76, 0.76, 1), size=400.0, name="cyc"):
    """Seamless curved backdrop, the classic product-photography sweep."""
    prof = []
    r = size * 0.18
    for i in range(25):
        a = i / 24 * math.pi / 2
        prof.append((size * 0.5 + math.sin(a) * r, r - math.cos(a) * r))
    pts = [(-size, 0)] + prof + [(size * 0.5 + r, size)]
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for y_i, y in enumerate((-size, size)):
        for x, z in pts:
            bm.verts.new((x, y, z))
    bm.verts.ensure_lookup_table()
    n = len(pts)
    for i in range(n - 1):
        bm.faces.new((bm.verts[i], bm.verts[i + 1], bm.verts[n + i + 1], bm.verts[n + i]))
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    mat = principled("cyc", mats_color, 0.0, 0.42, spec=0.35)
    me.materials.append(mat)
    o = obj(name, me)
    return o


def studio(s, floor_color=(0.28, 0.33, 0.33, 1), key=1.0):
    """High-key product studio: broad overhead, a long strip for the coat highlight, cool fill."""
    world(s)
    floor = cyclorama(floor_color)
    area_light("key", (-12, -8, 28), (0, 0, 0), 26, 15000 * key, (1.0, 0.97, 0.93), size_y=18)
    area_light("strip", (20, 8, 11), (0, 0, 0), 3, 5200 * key, (0.9, 0.97, 1.0), size_y=44)
    area_light("kicker", (-6, 34, 30), (0, 0, 0), 30, 1000 * key, (0.72, 1.0, 0.86), size_y=3)
    return floor


def camera(s, lens=50.0, fstop=8.0, focus=None, sensor=36.0):
    cam = bpy.data.cameras.new("cam")
    cam.lens = lens
    cam.sensor_width = sensor
    cam.clip_start = 0.05
    cam.clip_end = 3000
    cam.dof.use_dof = fstop > 0
    cam.dof.aperture_fstop = max(fstop, 0.1)
    cam.dof.aperture_blades = 7
    o = bpy.data.objects.new("cam", cam)
    s.collection.objects.link(o)
    s.camera = o
    target = empty("cam_target")
    tr = o.constraints.new("TRACK_TO")
    tr.target = target
    tr.track_axis = "TRACK_NEGATIVE_Z"
    tr.up_axis = "UP_Y"
    cam.dof.focus_object = focus or target
    return o, target


def key_camera(cam, target, s, moves, frames):
    """moves: list of (t 0..1, cam xyz, target xyz); smooth interpolation across the shot."""
    last = max(frames - 1, 1)
    for t, pos, aim in moves:
        f = 1 + round(t * last)
        cam.location = pos
        target.location = aim
        cam.keyframe_insert("location", frame=f)
        target.keyframe_insert("location", frame=f)
    for o in (cam, target):
        if o.animation_data and o.animation_data.action:
            for fc in fcurves(o.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
                    kp.handle_left_type = "AUTO_CLAMPED"
                    kp.handle_right_type = "AUTO_CLAMPED"
                fc.update()
    s.frame_start, s.frame_end = 1, frames


def fcurves(action):
    if hasattr(action, "fcurves"):
        return action.fcurves
    return [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves]


def threads(s, n=None):
    n = n or int(os.environ.get("RENDER_THREADS", "0"))
    if n:
        s.render.threads_mode = "FIXED"
        s.render.threads = n
