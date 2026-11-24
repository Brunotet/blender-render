import math

import bmesh
from mathutils import Euler, Matrix, Vector

def _fin(bpy, name, bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o

def blob(bpy, c, s, rot=(0, 0, 0), fn=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=26, radius=1.0)
    for v in bm.verts:
        p = Vector(v.co)
        if fn:
            p = fn(p)
        v.co = Vector((p.x * s[0], p.y * s[1], p.z * s[2]))
    bm.transform(Matrix.Translation(c) @ Euler(rot).to_matrix().to_4x4())
    return _fin(bpy, "blob", bm)

def _cr(pts, n=8):
    P = [Vector(p) for p in pts]
    if len(P) < 3:
        return P
    Q = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1])
    return out

def tube(bpy, pts, rad, seg=14, n=8):
    P = _cr(pts, n) if n > 1 else [Vector(p) for p in pts]
    rf = rad if callable(rad) else (lambda t: rad)
    bm = bmesh.new()
    rings, u = [], None
    for i, p in enumerate(P):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        if u is None:
            u = t.cross(Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))).normalized()
        else:
            u = u - t * u.dot(t)
            u = u.normalized() if u.length > 1e-6 else t.orthogonal().normalized()
        v = t.cross(u).normalized()
        r = max(rf(i / max(len(P) - 1, 1)), 0.0006)
        rings.append([bm.verts.new(p + (u * math.cos(k * math.tau / seg) + v * math.sin(k * math.tau / seg)) * r) for k in range(seg)])
    for i in range(len(rings) - 1):
        for k in range(seg):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % seg], rings[i + 1][(k + 1) % seg], rings[i + 1][k]))
    bm.faces.new(rings[0])
    bm.faces.new(rings[-1][::-1])
    return _fin(bpy, "tube", bm)

def hemi(sg):
    def f(p):
        if p.x * sg < 0:
            p.x *= 0.5
        if p.z < 0:
            p.z *= 0.7
        return p
    return f

def kidney(sg):
    def f(p):
        k = math.exp(-(p.y ** 2 + p.z ** 2) / 0.15)
        if p.x * sg < 0:
            p.x *= (1 - 0.7 * k)
        return p
    return f

def heart_fn(p):
    q = (p.z + 1) / 2
    f = 0.3 + 0.7 * q
    p.x = p.x * f + 0.55 * max(0, -p.z)
    p.y *= f
    return p

def liver_fn(p):
    t = (p.x + 1) / 2
    p.z *= 1 - 0.65 * t ** 2
    p.y *= 1 - 0.35 * t
    if p.z < 0:
        p.z *= 0.45
    return p

def lung_fn(sg):
    def f(p):
        if p.x * sg < 0:
            p.x *= 0.6
        return p
    return f

def b_brain(sg):
    return lambda bpy: [blob(bpy, (sg * 0.036, -0.004, 1.728), (0.040, 0.082, 0.058), fn=hemi(sg))]

def b_cerebellum(bpy):
    return [blob(bpy, (0, 0.066, 1.668), (0.05, 0.034, 0.026))]

def b_brainstem(bpy):
    return [tube(bpy, [(0, 0.03, 1.69), (0, 0.035, 1.64), (0, 0.04, 1.585)], lambda t: 0.014 - 0.005 * t)]

def b_heart(bpy):
    return [blob(bpy, (0.026, -0.03, 1.375), (0.05, 0.042, 0.058), fn=heart_fn)]

def b_aorta(bpy):
    return [tube(bpy, [(0.012, -0.02, 1.415), (0.012, -0.012, 1.47), (-0.005, 0.0, 1.495), (-0.028, 0.012, 1.475), (-0.034, 0.025, 1.43), (-0.032, 0.035, 1.36), (-0.03, 0.04, 1.28)], 0.0115)]

def b_vena(bpy):
    return [tube(bpy, [(-0.022, -0.02, 1.42), (-0.028, -0.01, 1.47), (-0.03, 0.0, 1.53)], 0.0095),
            tube(bpy, [(-0.022, -0.02, 1.34), (-0.032, 0.0, 1.27), (-0.034, 0.02, 1.20)], 0.0095)]

def b_lung_l(bpy):
    return [blob(bpy, (0.094, 0.004, 1.425), (0.052, 0.052, 0.068), fn=lung_fn(1)),
            blob(bpy, (0.092, 0.012, 1.335), (0.054, 0.054, 0.062), fn=lung_fn(1))]

def b_lung_r(bpy):
    return [blob(bpy, (-0.094, 0.004, 1.435), (0.054, 0.052, 0.056), fn=lung_fn(-1)),
            blob(bpy, (-0.094, -0.012, 1.375), (0.052, 0.046, 0.042), fn=lung_fn(-1)),
            blob(bpy, (-0.092, 0.014, 1.31), (0.056, 0.056, 0.062), fn=lung_fn(-1))]

def b_trachea(bpy):
    rib = lambda t: 0.0105 * (1 + 0.14 * math.sin(t * 90))
    return [tube(bpy, [(0, 0.004, 1.59), (0, 0.004, 1.52), (0, 0.006, 1.455)], rib),
            tube(bpy, [(0, 0.006, 1.455), (0.03, 0.01, 1.43), (0.062, 0.012, 1.405)], lambda t: 0.0075 * (1 + 0.14 * math.sin(t * 60))),
            tube(bpy, [(0, 0.006, 1.455), (-0.03, 0.01, 1.43), (-0.062, 0.012, 1.405)], lambda t: 0.0075 * (1 + 0.14 * math.sin(t * 60)))]

def b_esophagus(bpy):
    return [tube(bpy, [(0, 0.018, 1.58), (0, 0.02, 1.50), (0.006, 0.016, 1.40), (0.025, 0.0, 1.31), (0.05, -0.015, 1.255)], 0.0095)]

def b_stomach(bpy):
    prof = lambda t: 0.011 + 0.034 * math.sin(math.pi * min(1, t * 1.05)) ** 0.7 * (1 - 0.35 * t)
    return [tube(bpy, [(0.05, -0.015, 1.262), (0.092, -0.02, 1.25), (0.1, -0.028, 1.205), (0.075, -0.035, 1.16), (0.03, -0.034, 1.14), (-0.012, -0.028, 1.155)], prof, seg=20)]

def b_liver(bpy):
    return [blob(bpy, (-0.052, -0.022, 1.238), (0.118, 0.062, 0.058), fn=liver_fn)]

def b_gall(bpy):
    return [blob(bpy, (-0.08, -0.058, 1.188), (0.014, 0.03, 0.014), rot=(0.3, 0, 0))]

def b_pancreas(bpy):
    prof = lambda t: 0.017 * (1.35 - 0.85 * t) + 0.0025 * math.sin(t * 70)
    return [tube(bpy, [(-0.045, 0.022, 1.14), (-0.02, 0.032, 1.158), (0.012, 0.037, 1.17), (0.048, 0.037, 1.178), (0.088, 0.03, 1.19)], prof, seg=18)]

def b_spleen(bpy):
    return [blob(bpy, (0.118, 0.034, 1.23), (0.024, 0.02, 0.052), rot=(0, 0, -0.3))]

def b_kidney(sg):
    return lambda bpy: [blob(bpy, (sg * 0.07, 0.052, 1.165), (0.026, 0.02, 0.046), rot=(0, 0, sg * 0.2), fn=kidney(-sg))]

def b_bladder(bpy):
    return [blob(bpy, (0, -0.012, 0.9), (0.036, 0.032, 0.032))]

def b_small(bpy):
    pts = []
    for row, z in enumerate([1.105, 1.075, 1.045, 1.015, 0.985]):
        xs = [-0.07 + 0.035 * k for k in range(5)]
        xs = xs if row % 2 == 0 else xs[::-1]
        for i, x in enumerate(xs):
            pts.append((x, -0.025 + 0.008 * math.sin(i * 2.3 + row), z + 0.006 * math.sin(x * 150)))
    return [tube(bpy, pts, 0.0125, seg=12, n=6)]

def b_large(bpy):
    pts = [(-0.098, -0.008, 0.955), (-0.1, -0.008, 1.04), (-0.097, -0.008, 1.125), (-0.05, -0.03, 1.14), (0.0, -0.036, 1.145),
           (0.05, -0.03, 1.14), (0.097, -0.008, 1.125), (0.1, -0.008, 1.04), (0.092, -0.004, 0.97), (0.05, 0.0, 0.94), (0.01, 0.006, 0.925)]
    return [tube(bpy, pts, lambda t: 0.021 * (1 + 0.17 * math.sin(t * 70)), seg=16, n=8)]

def b_skull(bpy):
    return [blob(bpy, (0, 0.006, 1.712), (0.077, 0.094, 0.1), fn=lambda p: Vector((p.x, p.y, p.z * (0.8 if p.z < 0 else 1)))),
            tube(bpy, [(-0.05, -0.01, 1.63), (-0.03, -0.058, 1.608), (0.03, -0.058, 1.608), (0.05, -0.01, 1.63)], 0.008)]

def b_spine(bpy):
    out = []
    for i in range(18):
        z = 0.98 + i * 0.034
        out.append(blob(bpy, (0, 0.05, z), (0.017, 0.015, 0.013)))
    return out

def b_ribs(bpy):
    out = []
    for i in range(10):
        z0 = 1.52 - i * 0.029
        a = 0.078 + 0.011 * min(i, 5) - 0.004 * max(0, i - 5)
        for sx in (1, -1):
            out.append(tube(bpy, [(sx * 0.016, 0.042, z0), (sx * a * 0.8, 0.034, z0 - 0.004), (sx * a, -0.01, z0 - 0.012),
                                  (sx * a * 0.85, -0.062, z0 - 0.022), (sx * 0.016, -0.09, z0 - 0.036)], 0.0036, seg=8, n=5))
    out.append(tube(bpy, [(0, -0.092, 1.505), (0, -0.095, 1.40)], 0.0085, seg=8, n=2))
    return out

def b_leg(sg, kind):
    x = sg * 0.089
    if kind == "femur":
        return lambda bpy: [tube(bpy, [(x, 0.0, 0.92), (x, 0.004, 0.74), (x, 0.005, 0.55)], lambda t: 0.019 + 0.004 * math.sin(math.pi * t) * 0, seg=12, n=3),
                            blob(bpy, (x - sg * 0.02, 0.0, 0.93), (0.027, 0.027, 0.027)), blob(bpy, (x, 0.005, 0.545), (0.032, 0.03, 0.022))]
    if kind == "tibia":
        return lambda bpy: [tube(bpy, [(x, 0.005, 0.52), (x, 0.02, 0.32), (x, 0.03, 0.12)], 0.016, seg=12, n=3),
                            blob(bpy, (x, 0.005, 0.525), (0.036, 0.032, 0.02)), blob(bpy, (x, 0.03, 0.115), (0.026, 0.026, 0.018))]
    return lambda bpy: [tube(bpy, [(sg * 0.122, 0.0, 0.50), (sg * 0.12, 0.012, 0.3), (sg * 0.118, 0.025, 0.11)], 0.008, seg=8, n=3)]

PINK, BONE = None, None
ORGANS = {
    "brain_l": ("DEF-head", dict(c=(0.80, 0.58, 0.60), tex="gyri", rough=0.45, sss=0.25), b_brain(1)),
    "brain_r": ("DEF-head", dict(c=(0.80, 0.58, 0.60), tex="gyri", rough=0.45, sss=0.25), b_brain(-1)),
    "cerebellum": ("DEF-head", dict(c=(0.62, 0.40, 0.42), tex="stripes", rough=0.5, sss=0.2), b_cerebellum),
    "brainstem": ("DEF-head", dict(c=(0.86, 0.80, 0.70), tex="smooth", rough=0.5, sss=0.2), b_brainstem),
    "heart": ("DEF-spine.003", dict(c=(0.55, 0.03, 0.05), tex="smooth", rough=0.22, sss=0.1, coat=0.6), b_heart),
    "aorta": ("DEF-spine.003", dict(c=(0.85, 0.06, 0.06), tex="smooth", rough=0.2, coat=0.5), b_aorta),
    "vena_cava": ("DEF-spine.003", dict(c=(0.15, 0.20, 0.65), tex="smooth", rough=0.2, coat=0.5), b_vena),
    "lung_l": ("DEF-spine.003", dict(c=(0.88, 0.60, 0.62), tex="spongy", rough=0.65, sss=0.3), b_lung_l),
    "lung_r": ("DEF-spine.003", dict(c=(0.88, 0.60, 0.62), tex="spongy", rough=0.65, sss=0.3), b_lung_r),
    "trachea": ("DEF-spine.003", dict(c=(0.72, 0.82, 0.90), tex="smooth", rough=0.35), b_trachea),
    "esophagus": ("DEF-spine.003", dict(c=(0.78, 0.30, 0.28), tex="stripes", rough=0.4, sss=0.2), b_esophagus),
    "stomach": ("DEF-spine.002", dict(c=(0.92, 0.50, 0.40), tex="rugae", rough=0.4, sss=0.3), b_stomach),
    "liver": ("DEF-spine.002", dict(c=(0.40, 0.11, 0.07), tex="smooth", rough=0.3, sss=0.15, coat=0.4), b_liver),
    "gallbladder": ("DEF-spine.002", dict(c=(0.22, 0.48, 0.10), tex="smooth", rough=0.2, coat=0.5), b_gall),
    "pancreas": ("DEF-spine.001", dict(c=(0.92, 0.74, 0.40), tex="lobules", rough=0.55, sss=0.2), b_pancreas),
    "spleen": ("DEF-spine.002", dict(c=(0.36, 0.07, 0.16), tex="smooth", rough=0.35), b_spleen),
    "kidney_l": ("DEF-spine.001", dict(c=(0.48, 0.09, 0.06), tex="smooth", rough=0.3, coat=0.3), b_kidney(1)),
    "kidney_r": ("DEF-spine.001", dict(c=(0.48, 0.09, 0.06), tex="smooth", rough=0.3, coat=0.3), b_kidney(-1)),
    "bladder": ("DEF-hips", dict(c=(0.92, 0.84, 0.45), tex="smooth", rough=0.25, sss=0.2), b_bladder),
    "intestine_small": ("DEF-spine.001", dict(c=(0.95, 0.52, 0.50), tex="stripes", rough=0.35, sss=0.3), b_small),
    "intestine_large": ("DEF-hips", dict(c=(0.72, 0.48, 0.28), tex="smooth", rough=0.5, sss=0.1), b_large),
    "skull": ("DEF-head", dict(c=(0.93, 0.89, 0.78), tex="bone", rough=0.55), b_skull),
    "spine": ("DEF-spine.002", dict(c=(0.93, 0.89, 0.78), tex="bone", rough=0.55), b_spine),
    "ribs": ("DEF-spine.003", dict(c=(0.93, 0.89, 0.78), tex="bone", rough=0.55), b_ribs),
    "femur_l": ("DEF-thigh.L", dict(c=(0.93, 0.89, 0.78), tex="bone", rough=0.55), b_leg(1, "femur")),
    "femur_r": ("DEF-thigh.R", dict(c=(0.93, 0.89, 0.78), tex="bone", rough=0.55), b_leg(-1, "femur")),
    "tibia_l": ("DEF-shin.L", dict(c=(0.93, 0.89, 0.78), tex="bone", rough=0.55), b_leg(1, "tibia")),
    "tibia_r": ("DEF-shin.R", dict(c=(0.93, 0.89, 0.78), tex="bone", rough=0.55), b_leg(-1, "tibia")),
    "fibula_l": ("DEF-shin.L", dict(c=(0.90, 0.86, 0.75), tex="bone", rough=0.55), b_leg(1, "fibula")),
    "fibula_r": ("DEF-shin.R", dict(c=(0.90, 0.86, 0.75), tex="bone", rough=0.55), b_leg(-1, "fibula")),
}
GROUPS = {
    "brain": ["brain_l", "brain_r", "cerebellum", "brainstem"], "lungs": ["lung_l", "lung_r"], "heart": ["heart", "aorta", "vena_cava"],
    "kidneys": ["kidney_l", "kidney_r"], "urinary": ["kidney_l", "kidney_r", "bladder"],
    "digestive": ["esophagus", "stomach", "liver", "gallbladder", "pancreas", "spleen", "intestine_small", "intestine_large"],
    "leg_bones": ["femur_l", "femur_r", "tibia_l", "tibia_r", "fibula_l", "fibula_r"],
    "skeleton": ["skull", "spine", "ribs", "femur_l", "femur_r", "tibia_l", "tibia_r", "fibula_l", "fibula_r"],
    "torso": ["heart", "aorta", "vena_cava", "lung_l", "lung_r", "trachea", "esophagus", "stomach", "liver", "gallbladder", "pancreas", "spleen",
              "kidney_l", "kidney_r", "bladder", "intestine_small", "intestine_large"],
}
GROUPS["all"] = sorted(ORGANS)

def resolve(names):
    out = []
    for n in names:
        out += GROUPS.get(n, [n])
    bad = [n for n in out if n not in ORGANS]
    if bad:
        raise ValueError(f"unknown organs {bad}; known: {sorted(ORGANS)} groups: {sorted(GROUPS)}")
    return out

TEX = {
    "gyri": ("wave", 150, dict(distortion=9.0, detail=2.5), 0.50, 0.9),
    "stripes": ("wave", 260, dict(distortion=2.0, detail=1.0), 0.78, 0.35),
    "rugae": ("wave", 190, dict(distortion=4.0, detail=1.5), 0.68, 0.7),
    "spongy": ("voronoi", 450, {}, 0.82, 0.35),
    "lobules": ("voronoi", 140, {}, 0.80, 0.22),
    "bone": ("noise", 260, {}, 0.86, 0.15),
    "smooth": ("noise", 70, {}, 0.93, 0.12),
}

def organ_material(bpy, name, spec):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    kind, scale, extra, floor, bump = TEX[spec.get("tex", "smooth")]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    if kind == "wave":
        t = nt.nodes.new("ShaderNodeTexWave")
        t.wave_type = "BANDS"
        t.bands_direction = "DIAGONAL"
        t.inputs["Distortion"].default_value = extra["distortion"]
        t.inputs["Detail"].default_value = extra["detail"]
        t.inputs["Scale"].default_value = scale
        fac = t.outputs["Fac"]
    elif kind == "voronoi":
        t = nt.nodes.new("ShaderNodeTexVoronoi")
        t.inputs["Scale"].default_value = scale
        fac = t.outputs["Distance"]
    else:
        t = nt.nodes.new("ShaderNodeTexNoise")
        t.inputs["Scale"].default_value = scale
        t.inputs["Detail"].default_value = 6.0
        fac = t.outputs["Fac"]
    nt.links.new(tc.outputs["Object"], t.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = floor
    mr.inputs["To Max"].default_value = 1.0
    nt.links.new(fac, mr.inputs["Value"])
    g1 = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(mr.outputs["Result"], g1.inputs[i])
    mix1 = nt.nodes.new("ShaderNodeMix")
    mix1.data_type = "RGBA"
    mix1.blend_type = "MULTIPLY"
    mix1.inputs[0].default_value = 1.0
    mix1.inputs[6].default_value = tuple(spec["c"]) + (1,)
    nt.links.new(g1.outputs[0], mix1.inputs[7])
    dim = nt.nodes.new("ShaderNodeValue")
    dim.name = "DIM"
    dim.outputs[0].default_value = 1.0
    g2 = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(dim.outputs[0], g2.inputs[i])
    mix2 = nt.nodes.new("ShaderNodeMix")
    mix2.data_type = "RGBA"
    mix2.blend_type = "MULTIPLY"
    mix2.inputs[0].default_value = 1.0
    nt.links.new(mix1.outputs[2], mix2.inputs[6])
    nt.links.new(g2.outputs[0], mix2.inputs[7])
    nt.links.new(mix2.outputs[2], b.inputs["Base Color"])
    em = nt.nodes.new("ShaderNodeMix")
    em.data_type = "RGBA"
    em.blend_type = "MULTIPLY"
    em.inputs[0].default_value = 1.0
    em.inputs[7].default_value = (0.55, 0.55, 0.55, 1)
    nt.links.new(mix1.outputs[2], em.inputs[6])
    nt.links.new(em.outputs[2], b.inputs["Emission Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.004
    nt.links.new(fac, bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Emission Strength"].default_value = 0.0
    b.inputs["Roughness"].default_value = spec.get("rough", 0.4)
    b.inputs["Subsurface Weight"].default_value = spec.get("sss", 0.0)
    b.inputs["Coat Weight"].default_value = spec.get("coat", 0.0)
    return m

def make_body_xray(bpy, mat):
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    xr = nt.nodes.new("ShaderNodeValue")
    xr.name = "XR"
    xr.outputs[0].default_value = 1.0
    nt.links.new(xr.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(src, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat

def build_anatomy(bpy, arm, prefix):
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    out = {}
    for name, (bone, spec, builder) in ORGANS.items():
        mat = organ_material(bpy, f"{prefix}_{name}", spec)
        objs = builder(bpy)
        for i, o in enumerate(objs):
            o.name = f"{prefix}_{name}_{i}"
            o.data.materials.clear()
            o.data.materials.append(mat)
            ctr = sum((Vector(v) for v in o.bound_box), Vector()) / 8
            o.data.transform(Matrix.Translation(-ctr))
            o.location = ctr
            bpy.context.view_layer.update()
            o.parent, o.parent_type, o.parent_bone = arm, "BONE", bone
            o.matrix_parent_inverse = Matrix.Identity(4)
            bpy.context.view_layer.update()
            P = o.matrix_world @ o.matrix_basis.inverted()
            o.matrix_parent_inverse = P.inverted()
            bpy.context.view_layer.update()
        out[name] = objs
    return out
