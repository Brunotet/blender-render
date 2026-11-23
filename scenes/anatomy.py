import math

import bmesh
from mathutils import Matrix, Vector

def _ell(c, s, rot=(0, 0, 0)):
    return ("ell", c, s, rot)

def _tube(pts, r):
    return ("tube", pts, r)

ORGANS = {
    "brain_l":    ("DEF-head", (0.93, 0.55, 0.62), [_ell((0.034, -0.005, 1.725), (0.036, 0.078, 0.056))]),
    "brain_r":    ("DEF-head", (0.93, 0.55, 0.62), [_ell((-0.034, -0.005, 1.725), (0.036, 0.078, 0.056))]),
    "cerebellum": ("DEF-head", (0.80, 0.42, 0.50), [_ell((0.0, 0.065, 1.668), (0.042, 0.032, 0.026))]),
    "brainstem":  ("DEF-head", (0.85, 0.50, 0.55), [_tube([(0.0, 0.03, 1.69), (0.0, 0.03, 1.60)], 0.012)]),
    "heart":      ("DEF-spine.003", (0.80, 0.07, 0.10), [_ell((0.028, -0.03, 1.375), (0.042, 0.036, 0.052), (0, 0.35, 0.3))]),
    "lung_l":     ("DEF-spine.003", (0.90, 0.55, 0.58), [_ell((0.088, 0.0, 1.38), (0.052, 0.048, 0.095))]),
    "lung_r":     ("DEF-spine.003", (0.90, 0.55, 0.58), [_ell((-0.088, 0.0, 1.38), (0.052, 0.048, 0.095))]),
    "esophagus":  ("DEF-spine.003", (0.85, 0.45, 0.40), [_tube([(0.0, 0.005, 1.575), (0.0, 0.01, 1.50), (0.012, 0.0, 1.40), (0.035, -0.012, 1.30), (0.05, -0.015, 1.245)], 0.011)]),
    "liver":      ("DEF-spine.002", (0.55, 0.16, 0.10), [_ell((-0.06, -0.012, 1.245), (0.105, 0.058, 0.05), (0, 0, 0.12)),
                                                         _ell((0.012, -0.018, 1.225), (0.05, 0.045, 0.04))]),
    "stomach":    ("DEF-spine.002", (0.88, 0.50, 0.38), [_ell((0.062, -0.012, 1.235), (0.058, 0.05, 0.07), (0, 0, -0.4)),
                                                         _ell((0.028, -0.014, 1.185), (0.045, 0.04, 0.032), (0, 0, 0.2))]),
    "pancreas":   ("DEF-spine.001", (0.95, 0.75, 0.40), [_ell((0.02, 0.025, 1.165), (0.085, 0.02, 0.02), (0, 0, 0.12))]),
    "spleen":     ("DEF-spine.002", (0.45, 0.10, 0.22), [_ell((0.115, 0.03, 1.235), (0.02, 0.03, 0.05))]),
    "kidney_l":   ("DEF-spine.001", (0.55, 0.15, 0.15), [_ell((0.065, 0.045, 1.15), (0.022, 0.016, 0.04))]),
    "kidney_r":   ("DEF-spine.001", (0.55, 0.15, 0.15), [_ell((-0.065, 0.045, 1.15), (0.022, 0.016, 0.04))]),
    "intestine_small": ("DEF-spine.001", (0.95, 0.70, 0.60), [_tube(
        [(x, -0.02 + 0.006 * math.sin(i * 2), z) for row, z in enumerate([1.10, 1.07, 1.04, 1.01, 0.98])
         for i, x in enumerate(([-0.065 + 0.0325 * k for k in range(5)] if row % 2 == 0 else [0.065 - 0.0325 * k for k in range(5)]))], 0.013)]),
    "intestine_large": ("DEF-hips", (0.80, 0.55, 0.45), [_tube(
        [(-0.095, -0.01, 0.96), (-0.098, -0.01, 1.04), (-0.095, -0.01, 1.12), (-0.05, -0.03, 1.135), (0.0, -0.035, 1.14),
         (0.05, -0.03, 1.135), (0.095, -0.01, 1.12), (0.098, -0.01, 1.04), (0.09, -0.005, 0.97), (0.04, 0.0, 0.94), (0.0, 0.005, 0.93)], 0.02)]),
    "femur_l":    ("DEF-thigh.L", (0.95, 0.92, 0.82), [_tube([(0.089, 0.0, 0.92), (0.089, 0.005, 0.55)], 0.022), _ell((0.089, 0.0, 0.93), (0.03, 0.03, 0.03)), _ell((0.089, 0.005, 0.545), (0.032, 0.03, 0.03))]),
    "femur_r":    ("DEF-thigh.R", (0.95, 0.92, 0.82), [_tube([(-0.089, 0.0, 0.92), (-0.089, 0.005, 0.55)], 0.022), _ell((-0.089, 0.0, 0.93), (0.03, 0.03, 0.03)), _ell((-0.089, 0.005, 0.545), (0.032, 0.03, 0.03))]),
    "tibia_l":    ("DEF-shin.L", (0.95, 0.92, 0.82), [_tube([(0.089, 0.005, 0.52), (0.089, 0.03, 0.12)], 0.018), _ell((0.089, 0.005, 0.525), (0.034, 0.03, 0.02)), _ell((0.089, 0.03, 0.115), (0.026, 0.026, 0.02))]),
    "tibia_r":    ("DEF-shin.R", (0.95, 0.92, 0.82), [_tube([(-0.089, 0.005, 0.52), (-0.089, 0.03, 0.12)], 0.018), _ell((-0.089, 0.005, 0.525), (0.034, 0.03, 0.02)), _ell((-0.089, 0.03, 0.115), (0.026, 0.026, 0.02))]),
    "fibula_l":   ("DEF-shin.L", (0.92, 0.88, 0.78), [_tube([(0.122, 0.0, 0.50), (0.118, 0.025, 0.11)], 0.009)]),
    "fibula_r":   ("DEF-shin.R", (0.92, 0.88, 0.78), [_tube([(-0.122, 0.0, 0.50), (-0.118, 0.025, 0.11)], 0.009)]),
}
GROUPS = {"brain": ["brain_l", "brain_r", "cerebellum", "brainstem"], "lungs": ["lung_l", "lung_r"],
          "kidneys": ["kidney_l", "kidney_r"], "digestive": ["esophagus", "stomach", "liver", "pancreas", "spleen", "intestine_small", "intestine_large"],
          "leg_bones": ["femur_l", "femur_r", "tibia_l", "tibia_r", "fibula_l", "fibula_r"]}

def resolve(names):
    out = []
    for n in names:
        out += GROUPS.get(n, [n])
    bad = [n for n in out if n not in ORGANS]
    if bad:
        raise ValueError(f"unknown organs {bad}; known: {sorted(ORGANS)} groups: {sorted(GROUPS)}")
    return out

def _tube_mesh(bpy, name, pts, r, seg=12):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    P = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(P):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = t.cross(a).normalized(); v = t.cross(u).normalized()
        rings.append([bm.verts.new(p + (u * math.cos(k * math.tau / seg) + v * math.sin(k * math.tau / seg)) * r) for k in range(seg)])
    for i in range(len(rings) - 1):
        for k in range(seg):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % seg], rings[i + 1][(k + 1) % seg], rings[i + 1][k]))
    for ring in (rings[0], rings[-1]):
        bm.faces.new(ring[::-1] if ring is rings[0] else ring)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return bpy.data.objects.new(name, me)

def _ell_obj(bpy, name, c, s, rot):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=24, ring_count=14, location=c)
    o = bpy.context.object
    o.name = name
    o.scale = s
    o.rotation_euler = rot
    for p in o.data.polygons:
        p.use_smooth = True
    return o

def organ_material(bpy, name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.name = "DIMMIX"
    mul.inputs[0].default_value = 1.0
    mul.inputs[6].default_value = color + (1,)
    dim = nt.nodes.new("ShaderNodeValue"); dim.name = "DIM"; dim.outputs[0].default_value = 1.0
    gray = nt.nodes.new("ShaderNodeCombineColor"); gray.name = "DIMRGB"
    for i in range(3):
        nt.links.new(dim.outputs[0], gray.inputs[i])
    nt.links.new(gray.outputs[0], mul.inputs[7])
    nt.links.new(mul.outputs[2], b.inputs["Base Color"])
    nt.links.new(mul.outputs[2], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.35
    b.inputs["Subsurface Weight"].default_value = 0.15
    return m

def make_body_xray(bpy, mat):
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader"); mix.name = "XRMIX"
    xr = nt.nodes.new("ShaderNodeValue"); xr.name = "XR"; xr.outputs[0].default_value = 1.0
    nt.links.new(xr.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(src, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat

def build_anatomy(bpy, arm, prefix):
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    out = {}
    for name, (bone, color, parts) in ORGANS.items():
        mat = organ_material(bpy, f"{prefix}_{name}", color)
        objs = []
        for i, part in enumerate(parts):
            oname = f"{prefix}_{name}_{i}"
            if part[0] == "ell":
                o = _ell_obj(bpy, oname, part[1], part[2], part[3])
            else:
                o = _tube_mesh(bpy, oname, part[1], part[2])
                bpy.context.scene.collection.objects.link(o)
            o.data.materials.clear()
            o.data.materials.append(mat)
            o.parent, o.parent_type, o.parent_bone = arm, "BONE", bone
            o.matrix_parent_inverse = Matrix.Identity(4)
            bpy.context.view_layer.update()
            P = o.matrix_world @ o.matrix_basis.inverted()
            o.matrix_parent_inverse = P.inverted()
            bpy.context.view_layer.update()
            objs.append(o)
        out[name] = objs
    return out
