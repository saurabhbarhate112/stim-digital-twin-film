"""The digital-twin look, applied on top of any physical material.

A moving empty ('scan') splits the world: on one side surfaces are their real
selves, on the other they become a glowing engineering hologram. A bright band
marks the seam, so one object can turn from metal into data in a single move.
"""
import bpy

from lib import MINT, empty

_DONE = set()


def scan_empty(x=-10000.0):
    return empty("scan", x, 0, 0)


def twin_shader(n, l, grid=2.0, edge_strength=9.0):
    """Returns the hologram shader output: bright model edges, fine grid, faint fill."""
    bev = n.new("ShaderNodeBevel")
    bev.samples = 3
    bev.inputs["Radius"].default_value = 0.12
    geo = n.new("ShaderNodeNewGeometry")
    dot = n.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    l.new(bev.outputs[0], dot.inputs[0])
    l.new(geo.outputs["Normal"], dot.inputs[1])
    edge = n.new("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value = 0.985
    edge.inputs["From Max"].default_value = 0.8
    l.new(dot.outputs["Value"], edge.inputs["Value"])

    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.25
    fres = n.new("ShaderNodeMath")
    fres.operation = "MULTIPLY"
    fres.inputs[1].default_value = 0.35
    l.new(lw.outputs["Facing"], fres.inputs[0])

    # Thin blueprint grid in world space.
    tc = n.new("ShaderNodeTexCoord")
    wave_in = n.new("ShaderNodeVectorMath")
    wave_in.operation = "FRACTION"
    scale = n.new("ShaderNodeVectorMath")
    scale.operation = "SCALE"
    scale.inputs["Scale"].default_value = 1.0 / grid
    l.new(geo.outputs["Position"], scale.inputs[0])
    l.new(scale.outputs[0], wave_in.inputs[0])
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(wave_in.outputs[0], sep.inputs[0])
    lines = None
    for axis in ("X", "Y"):
        t = n.new("ShaderNodeMath")
        t.operation = "LESS_THAN"
        t.inputs[1].default_value = 0.035
        l.new(sep.outputs[axis], t.inputs[0])
        if lines is None:
            lines = t
        else:
            mx = n.new("ShaderNodeMath")
            mx.operation = "MAXIMUM"
            l.new(lines.outputs[0], mx.inputs[0])
            l.new(t.outputs[0], mx.inputs[1])
            lines = mx
    gridv = n.new("ShaderNodeMath")
    gridv.operation = "MULTIPLY"
    gridv.inputs[1].default_value = 0.22
    l.new(lines.outputs[0], gridv.inputs[0])

    total = n.new("ShaderNodeMath")
    total.operation = "ADD"
    l.new(fres.outputs[0], total.inputs[0])
    l.new(gridv.outputs[0], total.inputs[1])
    e_mul = n.new("ShaderNodeMath")
    e_mul.operation = "MULTIPLY"
    e_mul.inputs[1].default_value = edge_strength
    l.new(edge.outputs[0], e_mul.inputs[0])
    strength = n.new("ShaderNodeMath")
    strength.operation = "ADD"
    l.new(total.outputs[0], strength.inputs[0])
    l.new(e_mul.outputs[0], strength.inputs[1])

    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = MINT
    l.new(strength.outputs[0], em.inputs["Strength"])

    # Mostly clear, so machines read as see-through engineering models.
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.86, 0.95, 0.9, 1)
    add = n.new("ShaderNodeAddShader")
    l.new(tr.outputs[0], add.inputs[0])
    l.new(em.outputs[0], add.inputs[1])
    return add


def twinify(mat, scan, band=1.5, axis="X"):
    """Wrap a material so that it turns to hologram where scan-space X is positive."""
    if mat.name in _DONE or not mat.use_nodes:
        return mat
    _DONE.add(mat.name)
    n, l = mat.node_tree.nodes, mat.node_tree.links
    out = n["Material Output"]
    src = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
    if src is None:
        return mat
    holo = twin_shader(n, l)
    tc = n.new("ShaderNodeTexCoord")
    tc.object = scan
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    side = n.new("ShaderNodeMath")
    side.operation = "GREATER_THAN"
    l.new(sep.outputs[axis], side.inputs[0])
    side.inputs[1].default_value = 0.0

    mix = n.new("ShaderNodeMixShader")
    l.new(side.outputs[0], mix.inputs[0])
    l.new(src, mix.inputs[1])
    l.new(holo.outputs[0], mix.inputs[2])

    # The scan seam itself: a hot band of light travelling across the object.
    dist = n.new("ShaderNodeMath")
    dist.operation = "ABSOLUTE"
    l.new(sep.outputs[axis], dist.inputs[0])
    bandr = n.new("ShaderNodeMapRange")
    bandr.inputs["From Min"].default_value = band
    bandr.inputs["From Max"].default_value = 0.0
    bandr.interpolation_type = "SMOOTHSTEP"
    l.new(dist.outputs[0], bandr.inputs["Value"])
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.5, 1.0, 0.75, 1)
    em.inputs["Strength"].default_value = 14.0
    mix2 = n.new("ShaderNodeMixShader")
    l.new(bandr.outputs[0], mix2.inputs[0])
    l.new(mix.outputs[0], mix2.inputs[1])
    l.new(em.outputs[0], mix2.inputs[2])
    l.new(mix2.outputs[0], out.inputs["Surface"])
    return mat


def twinify_all(scan, skip=()):
    for mat in bpy.data.materials:
        if mat.name not in skip:
            twinify(mat, scan)
