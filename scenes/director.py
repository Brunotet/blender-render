import difflib, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GLB = os.path.join(HERE, "..", "assets", "ual", "Animation Library[Standard]", "Godot", "AnimationLibrary_Godot_Standard.glb")
DEFAULT_SHOTS = os.path.join(HERE, "shots", "demo.json")

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x

def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)

def lerp(a, b, k):
    return a + (b - a) * k

def load_spec():
    path = os.environ.get("SHOTS", DEFAULT_SHOTS)
    if not os.path.isabs(path) and not os.path.exists(path):
        path = os.path.join(HERE, "..", path)
    with open(path) as f:
        return json.load(f), path

def validate(spec, clips):
    errs = []
    ids = [c.get("id") for c in spec.get("characters", [])]
    if not ids or len(set(ids)) != len(ids):
        errs.append("characters: need at least one, unique ids")
    if not spec.get("shots"):
        errs.append("shots: empty")
    for i, sh in enumerate(spec.get("shots", [])):
        if not (0.2 <= sh.get("dur", 0) <= 120):
            errs.append(f"shot {i}: dur must be 0.2..120 s")
        cam = sh.get("camera", {})
        tg = cam.get("target", {})
        if "organ" in tg:
            if not next((c for c in spec.get("characters", []) if c.get("id") == tg.get("char") and c.get("anatomy")), None):
                errs.append(f"shot {i}: organ target needs a character with \"anatomy\": true")
            else:
                try:
                    from anatomy import resolve; resolve([tg["organ"]])
                except ValueError as e:
                    errs.append(f"shot {i}: {e}")
        elif tg.get("char") not in ids and "point" not in tg:
            errs.append(f"shot {i}: camera.target needs a valid char or point")
        for a in sh.get("actions", []):
            if a.get("char") not in ids:
                errs.append(f"shot {i}: action char {a.get('char')!r} unknown")
            if a.get("clip") not in clips:
                near = difflib.get_close_matches(str(a.get("clip")), clips, n=3)
                errs.append(f"shot {i}: clip {a.get('clip')!r} is not in the library (closest: {near}) - needs a generator")
            if a.get("at", 0) < 0 or a.get("at", 0) >= sh.get("dur", 0):
                errs.append(f"shot {i}: action 'at' outside the shot")
    if errs:
        raise ValueError("Shot list rejected:\n  " + "\n  ".join(errs))

def total_seconds(spec):
    return sum(s["dur"] for s in spec["shots"])

def build(bpy, fps):
    import mathutils
    spec, spec_path = load_spec()
    fps = spec.get("fps", fps)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    sc = bpy.context.scene
    sc.render.fps = fps
    sc.view_settings.view_transform = "Standard"
    if not os.path.exists(GLB):
        raise FileNotFoundError(f"character pack missing: {GLB}")

    chars, clip_actions = {}, None
    for n, c in enumerate(spec["characters"]):
        before = set(bpy.data.objects)
        before_actions = set(bpy.data.actions)
        bpy.ops.import_scene.gltf(filepath=GLB)
        new = [o for o in bpy.data.objects if o not in before]
        for o in [o for o in new if o.name.startswith("Icosphere")]:
            bpy.data.objects.remove(o, do_unlink=True)
        new = [o for o in bpy.data.objects if o not in before]
        arm = next(o for o in new if o.type == "ARMATURE")
        mesh = next(o for o in new if o.type == "MESH")
        if clip_actions is None:
            clip_actions = {a.name: a for a in bpy.data.actions if a not in before_actions}
        else:
            for a in [a for a in bpy.data.actions if a not in before_actions]:
                bpy.data.actions.remove(a)
        arm.animation_data_create()
        arm.animation_data.action = None
        for t_ in list(arm.animation_data.nla_tracks):
            arm.animation_data.nla_tracks.remove(t_)
        root = bpy.data.objects.new(f"char_{c['id']}", None)
        sc.collection.objects.link(root)
        root.rotation_mode = "ZYX"
        for o in new:
            if o.parent is None:
                o.parent = root
        if "color" in c:
            mat = mesh.active_material.copy()
            for nd in mat.node_tree.nodes:
                if nd.type == "BSDF_PRINCIPLED":
                    nd.inputs["Base Color"].default_value = tuple(c["color"]) + (1,)
            mesh.active_material = mat
        chars[c["id"]] = dict(root=root, arm=arm, mesh=mesh, cfg=c)
    sys.path.insert(0, HERE)
    import anatomy
    for cid, ch in chars.items():
        if ch["cfg"].get("anatomy"):
            ms = ch["mesh"]
            ch["xr"] = []
            for si, m0_ in enumerate(ms.data.materials):
                m2 = m0_.copy(); ms.data.materials[si] = m2
                anatomy.make_body_xray(bpy, m2)
                ch["xr"].append(m2.node_tree.nodes["XR"])
            ch["organs"] = anatomy.build_anatomy(bpy, ch["arm"], f"{cid}")
    clips = sorted(k for k in clip_actions if k != "A_TPose")
    validate(spec, clips)

    n_frames = int(round(total_seconds(spec) * fps))
    sc.frame_start, sc.frame_end = 1, n_frames

    for cid, ch in chars.items():
        ad = ch["arm"].animation_data
        idle = clip_actions["Idle_Loop"]
        tr = ad.nla_tracks.new()
        tr.name = "base_idle"
        st = tr.strips.new("idle", 1, idle)
        ln = max(idle.frame_range[1] - idle.frame_range[0], 1)
        st.repeat = max(1.0, (n_frames) / ln)
        st.extrapolation = "HOLD"
    t0 = 0.0
    bounds = set()
    moves = {cid: [] for cid in chars}
    for sh in spec["shots"]:
        for a in sh.get("actions", []):
            ch = chars[a["char"]]
            act = clip_actions[a["clip"]]
            start_f = 1 + int(round((t0 + a.get("at", 0)) * fps))
            dur_s = a.get("dur", sh["dur"] - a.get("at", 0))
            dur_f = max(2, int(round(dur_s * fps)))
            ln = max(act.frame_range[1] - act.frame_range[0], 1) / a.get("speed", 1.0)
            tr = ch["arm"].animation_data.nla_tracks.new()
            tr.name = a["clip"]
            st = tr.strips.new(a["clip"], start_f, act)
            st.scale = 1.0 / a.get("speed", 1.0)
            loop = a.get("loop", a["clip"].endswith("_Loop"))
            st.repeat = max(1.0, dur_f / ln) if loop else 1.0
            st.blend_in, st.blend_out = 0, 0
            bounds.add(start_f); bounds.add(start_f + dur_f)
            st.extrapolation = "NOTHING"
            if "move" in a:
                moves[a["char"]].append((t0 + a.get("at", 0), t0 + a.get("at", 0) + dur_s, a["move"]))
        t0 += sh["dur"]

    sc["clip_boundaries"] = sorted(bounds)

    def mat(name, color, rough=0.8):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = color
        b.inputs["Roughness"].default_value = rough
        return m
    bpy.ops.mesh.primitive_plane_add(size=120)
    fl = mat("floor", (0.5, 0.5, 0.5, 1))
    nt = fl.node_tree
    chk = nt.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 60
    chk.inputs["Color1"].default_value = (0.30, 0.32, 0.38, 1)
    chk.inputs["Color2"].default_value = (0.17, 0.18, 0.23, 1)
    nt.links.new(chk.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    bpy.context.object.data.materials.append(fl)
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), 0, math.radians(30)))
    bpy.context.object.data.energy = 3
    bpy.context.object.data.angle = math.radians(4)
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.7, 0.85, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    sc.world = w
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5

    for cid, ch in chars.items():
        cfg = ch["cfg"]
        px, py, pz = cfg.get("pos", [0, 0, 0])
        yaw = math.radians(cfg.get("rot_z", 0))
        segs = moves[cid]
        pts = [(0.0, px, py, yaw)]
        for (ta, tb, mv) in segs:
            _, x0, y0, yw0 = pts[-1]
            if ta > pts[-1][0]:
                pts.append((ta, x0, y0, yw0))
            tx, ty = mv["to"][:2]
            dx, dy = tx - x0, ty - y0
            yw1 = math.atan2(dx, -dy) if (mv.get("face", True) and math.hypot(dx, dy) > 1e-3) else yw0
            while yw1 - yw0 > math.pi: yw1 -= 2 * math.pi
            while yw1 - yw0 < -math.pi: yw1 += 2 * math.pi
            turn = min(0.4, 0.3 * (tb - ta)) if abs(yw1 - yw0) > 0.05 else 0.0
            pts.append((ta + turn + 1e-6, x0, y0, yw1))
            pts.append((tb, tx, ty, yw1))
        for f in range(1, n_frames + 1):
            t = (f - 1) / fps
            x, y, yw = pts[-1][1:]
            for i in range(len(pts) - 1):
                if pts[i][0] <= t <= pts[i + 1][0]:
                    a_, b_ = pts[i], pts[i + 1]
                    k = (t - a_[0]) / max(b_[0] - a_[0], 1e-9)
                    turning = abs(b_[1] - a_[1]) + abs(b_[2] - a_[2]) < 1e-6
                    x, y, yw = lerp(a_[1], b_[1], k), lerp(a_[2], b_[2], k), lerp(a_[3], b_[3], smooth(k) if turning else k)
                    break
            ch["root"].location = (x, y, pz)
            ch["root"].rotation_euler = (0, 0, yw)
            ch["root"].keyframe_insert("location", frame=f)
            ch["root"].keyframe_insert("rotation_euler", frame=f)

    t_ = 0.0
    for sh in spec["shots"]:
        fa = 1 + int(round(t_ * fps)); fb = min(n_frames, int(round((t_ + sh["dur"]) * fps)))
        t_ += sh["dur"]
        for cid, ch in chars.items():
            if "organs" not in ch:
                continue
            xs = sh.get("xray", {}).get(cid, sh.get("xray", {})) if sh.get("xray") else {}
            body = xs.get("body", [1.0, 1.0]); body = body if isinstance(body, list) else [body, body]
            show = set(anatomy.resolve(xs.get("show", []))); hl = set(anatomy.resolve(xs.get("highlight", [])))
            show |= hl
            dim = xs.get("dim", 0.35)
            for name, objs in ch["organs"].items():
                m0 = objs[0].active_material
                vis = name in show
                for o in objs:
                    o.hide_render = not vis; o.keyframe_insert("hide_render", frame=fa); o.keyframe_insert("hide_render", frame=fb)
                nt = m0.node_tree
                gl = 1.0 if name in hl else 0.0
                dv = 1.0 if (name in hl or not hl) else dim
                for f in (fa, fb):
                    nt.nodes["DIM"].outputs[0].default_value = dv
                    nt.nodes["DIM"].outputs[0].keyframe_insert("default_value", frame=f)
                    nt.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = gl
                    nt.nodes["Principled BSDF"].inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
            for f, bv in ((fa, body[0]), (fb, body[1])):
                for xn in ch["xr"]:
                    xn.outputs[0].default_value = bv
                    xn.outputs[0].keyframe_insert("default_value", frame=f)

    def target_pos(tg):
        if "point" in tg:
            return mathutils.Vector(tg["point"])
        ch = chars[tg["char"]]
        off = mathutils.Vector(tg.get("offset", [0, 0, 0]))
        if "organ" in tg:
            objs = [o for n_ in anatomy.resolve([tg["organ"]]) for o in ch["organs"][n_]]
            return sum((o.matrix_world.translation for o in objs), mathutils.Vector()) / len(objs) + off
        if "bone" in tg:
            pb = ch["arm"].pose.bones[tg["bone"]]
            return ch["arm"].matrix_world @ pb.head + off
        return ch["root"].matrix_world.translation + mathutils.Vector((0, 0, 1.0)) + off

    shot_t0 = 0.0
    cams = []
    for i, sh in enumerate(spec["shots"]):
        cd = bpy.data.cameras.new(f"cam{i}")
        cd.clip_end = 400
        co = bpy.data.objects.new(f"cam{i}", cd)
        sc.collection.objects.link(co)
        te = bpy.data.objects.new(f"tgt{i}", None)
        sc.collection.objects.link(te)
        tc = co.constraints.new("TRACK_TO")
        tc.target, tc.track_axis, tc.up_axis = te, "TRACK_NEGATIVE_Z", "UP_Y"
        f0 = 1 + int(round(shot_t0 * fps))
        f1 = min(n_frames, int(round((shot_t0 + sh["dur"]) * fps)))
        m = sc.timeline_markers.new(f"shot{i}", frame=f0)
        m.camera = co
        cams.append((co, te, sh, f0, f1))
        shot_t0 += sh["dur"]
    if cams:
        sc.camera = cams[0][0]
    for co, te, sh, f0, f1 in cams:
        cam = sh["camera"]
        a0 = dict(az=0, dist=6, h=1.5, lens=38); a0.update(cam.get("from", {}))
        a1 = dict(a0); a1.update(cam.get("to", {}))
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            u = smooth((f - f0) / max(f1 - f0, 1))
            tp = target_pos(cam["target"])
            az = math.radians(lerp(a0["az"], a1["az"], u))
            d, h = lerp(a0["dist"], a1["dist"], u), lerp(a0["h"], a1["h"], u)
            co.data.lens = lerp(a0["lens"], a1["lens"], u)
            co.data.keyframe_insert("lens", frame=f)
            te.location = tp
            co.location = (tp.x + d * math.sin(az), tp.y - d * math.cos(az), h)
            te.keyframe_insert("location", frame=f)
            co.keyframe_insert("location", frame=f)
    sc.frame_set(1)
    return spec
