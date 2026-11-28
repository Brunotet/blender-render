"""Swap hand-built organs for GPU-generated GLBs (gen/organs/manifest.json). Hard-fails on any problem.
The procedural organ is built only to measure the target box (never rendered), then the GLB is fitted into it."""
import json, os, math
from mathutils import Vector, Matrix

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GEN = os.environ.get("ORGAN_GLB_DIR", os.path.join(ROOT, "gen", "organs"))

def _box(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi

def _drop(bpy, objs):
    for o in objs:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)

def _import(bpy, path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"{path}: no mesh in GLB")
    for o in meshes:
        o.parent = None
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active

def glb_builder(path, protos, rot):
    def build(bpy):
        proxies = [o for p in protos for o in p(bpy)]
        lo, hi = _box(proxies)
        _drop(bpy, proxies)
        o = _import(bpy, path)
        me = o.data
        me.transform(o.matrix_world)          # bake import transform (Y-up -> Z-up already applied by importer)
        o.matrix_world = Matrix.Identity(4)
        if any(rot):
            me.transform(Matrix.Rotation(math.radians(rot[2]), 4, "Z") @ Matrix.Rotation(math.radians(rot[1]), 4, "Y") @ Matrix.Rotation(math.radians(rot[0]), 4, "X"))
        vs = [v.co for v in me.vertices]
        glo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        ghi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        k = max((hi - lo)) / max(ghi - glo)
        print('[gen]', os.path.basename(path), 'target', tuple(lo), tuple(hi), 'glb', tuple(glo), tuple(ghi), 'k', k, flush=True)
        ctr_g, ctr_t = (glo + ghi) / 2, (lo + hi) / 2
        me.transform(Matrix.Translation(ctr_t) @ Matrix.Scale(k, 4) @ Matrix.Translation(-ctr_g))
        for p in me.polygons:
            p.use_smooth = True
        o.name = os.path.basename(path)
        print('[gen] fitted', o.name, len(me.vertices), tuple(o.location), tuple(o.rotation_euler), tuple(o.scale), flush=True)
        return [o]
    return build

def apply(an):
    mf = os.path.join(GEN, "manifest.json")
    if not os.path.exists(mf):
        return []
    man = json.load(open(mf))
    done = []
    orig_mat = an.organ_material
    an.organ_material = lambda bpy, name, spec: glb_material(bpy, name, spec) if spec.get("glb") else orig_mat(bpy, name, spec)
    for name, ent in man.items():
        path = os.path.join(GEN, ent["file"])
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            raise RuntimeError(f"generated organ {name}: {path} missing/empty")
        rot = ent.get("rot", [0, 0, 0])
        if name == "brain":
            bone, spec, b0 = an.ORGANS["brain_l"]
            protos = [an.ORGANS[n][2] for n in ("brain_l", "brain_r", "cerebellum", "brainstem")]
            for n in ("brain_r", "cerebellum", "brainstem"):
                an.ORGANS.pop(n)
            an.ORGANS["brain_l"] = (bone, dict(spec, glb=True), glb_builder(path, protos, rot))
            an.GROUPS["brain"] = ["brain_l"]
        elif name == "heart":
            bone, spec, b0 = an.ORGANS["heart"]
            protos = [an.ORGANS[n][2] for n in ("heart", "aorta", "vena_cava")]
            for n in ("aorta", "vena_cava"):
                an.ORGANS.pop(n)
            an.ORGANS["heart"] = (bone, dict(spec, glb=True), glb_builder(path, protos, rot))
            an.GROUPS["heart"] = ["heart"]
        else:
            if name not in an.ORGANS:
                raise RuntimeError(f"generated organ {name}: unknown organ")
            bone, spec, b0 = an.ORGANS[name]
            an.ORGANS[name] = (bone, dict(spec, glb=True), glb_builder(path, [b0], rot))
        done.append(name)
    for g, lst in list(an.GROUPS.items()):
        an.GROUPS[g] = [n for n in lst if n in an.ORGANS]
    an.GROUPS["all"] = sorted(an.ORGANS)
    return done

def glb_material(bpy, name, spec):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    vc = nt.nodes.new("ShaderNodeVertexColor")
    dim = nt.nodes.new("ShaderNodeValue"); dim.name = "DIM"; dim.outputs[0].default_value = 1.0
    g = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(dim.outputs[0], g.inputs[i])
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs[0].default_value = 1.0
    nt.links.new(vc.outputs["Color"], mx.inputs[6]); nt.links.new(g.outputs[0], mx.inputs[7])
    nt.links.new(mx.outputs[2], b.inputs["Base Color"])
    em = nt.nodes.new("ShaderNodeMix"); em.data_type = "RGBA"; em.blend_type = "MULTIPLY"; em.inputs[0].default_value = 1.0
    em.inputs[7].default_value = (0.55, 0.55, 0.55, 1)
    nt.links.new(vc.outputs["Color"], em.inputs[6]); nt.links.new(em.outputs[2], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.0
    b.inputs["Roughness"].default_value = spec.get("rough", 0.4)
    b.inputs["Subsurface Weight"].default_value = spec.get("sss", 0.0)
    b.inputs["Coat Weight"].default_value = spec.get("coat", 0.0)
    return m
