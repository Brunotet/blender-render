"""Acrobat demo: tuck backflip, corkscrew layout, double backflip, 720 spin, victory pose.

Fully procedural (primitives + joint hierarchy, no external assets).
Character faces -Y (toward the camera). A backflip is a NEGATIVE rotation about X.
Every rotation is a whole number of turns, so the character always lands facing the camera
and the keyframed angles stay continuous (no wrap jumps, safe for motion blur).
"""
import math

TAU = math.tau
G = 9.8
THIGH, SHIN = 0.45, 0.43
STAND_Z = 0.98                      # pelvis height with straight legs, feet on the floor
WIND, PUSH, ABSORB, RECOVER = 0.46, 0.24, 0.20, 0.40
PHI_DEEP, PHI_LAND = 0.95, 0.85     # crouch depth (hip flexion, rad) before takeoff / after landing
START_X, START_Y = 0.0, -1.6
LEAD_IN = 0.7
DURATION = 22.0                     # seconds; total frames = DURATION * fps
PUSH_N, PUSH_PERIOD, GET_DOWN = 4, 1.15, 1.1     # pushups: reps, seconds per rep, drop-to-plank time
TWERK_IN, TWERK_HOLD, TWERK_HZ = 0.5, 3.2, 4.6   # twerk: ease in, duration, bounce frequency
TH_UP, TH_DN = 1.27, 1.47           # plank body pitch from vertical (arms straight / chest low)
A_UP, A_LO = 0.30, 0.29             # upper-arm / forearm+hand length
PUSH_PERIOD_SAFE = PUSH_PERIOD

MOVES = [
    dict(kind="tuck", T=0.95, flips=1, twist=0.0, dx=0.0, dy=0.9),
    dict(kind="layout", T=1.00, flips=1, twist=1.0, dx=0.8, dy=0.6),
    dict(kind="tuck", T=1.30, flips=2, twist=0.0, dx=-1.3, dy=0.9),
    dict(kind="spin", T=0.95, flips=0, twist=2.0, dx=0.5, dy=0.0),
]

ARM_STAND = dict(sx=0.05, sy=0.14, el=-0.2)
ARM_BACK = dict(sx=0.9, sy=0.2, el=-0.1)
ARM_UP = dict(sx=-2.9, sy=0.18, el=0.0)
ARM_TUCK = dict(sx=-2.0, sy=0.12, el=-0.6)
ARM_BAL = dict(sx=-0.9, sy=0.55, el=-0.5)
ARM_TWIST = dict(sx=-0.35, sy=0.05, el=-1.9)
ARM_OUT = dict(sx=0.0, sy=1.45, el=-0.1)
ARM_V = dict(sx=-2.5, sy=0.65, el=0.0)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def smoother(x):
    x = clamp(x)
    return x * x * x * (x * (x * 6 - 15) + 10)


def lerp(a, b, k):
    return a + (b - a) * k


def blend(a, b, k):
    return {key: lerp(a[key], b[key], k) for key in a}


def ground_z(phi):
    """Pelvis height and shin angle for a squat that keeps the feet under the hips."""
    s = math.asin(min(1.0, THIGH * math.sin(phi) / SHIN))
    return 0.10 + THIGH * math.cos(phi) + SHIN * math.cos(s), s


def schedule():
    cur, x, y, acc_f, acc_t = LEAD_IN, START_X, START_Y, 0.0, 0.0
    out = []
    for m in MOVES:
        s = dict(m)
        s["w0"] = cur
        s["take"] = cur + WIND
        s["land"] = s["take"] + m["T"]
        s["end"] = s["land"] + ABSORB + RECOVER
        s["x0"], s["y0"], s["x1"], s["y1"] = x, y, x + m["dx"], y + m["dy"]
        s["f0"], s["t0"] = acc_f, acc_t
        out.append(s)
        cur, x, y = s["end"], s["x1"], s["y1"]
        acc_f += m["flips"]
        acc_t += m["twist"]
    if cur > DURATION - 0.8:
        raise ValueError(f"routine ends at {cur:.2f}s, DURATION {DURATION}s leaves no victory pose")
    return out


def crouch(P, phi):
    z, s = ground_z(phi)
    P["z"], P["hipF"], P["kneeF"], P["ankle"] = z, phi, phi + s, -s


def floor_times(S):
    """Timeline of the floor routine that follows the last flip."""
    a = S[-1]["end"]
    d = dict(A=a, R0=a + GET_DOWN)
    d["R1"] = d["R0"] + PUSH_N * PUSH_PERIOD
    d["B"] = d["R1"] + GET_DOWN                      # back on feet
    d["T0"] = d["B"]
    d["T1"] = d["T0"] + TWERK_IN + TWERK_HOLD + TWERK_IN
    d["C"] = d["T1"]
    return d


def arm_ik(theta, root_y, root_z, y_h):
    """2-link planar IK (sagittal plane): shoulder rot_x and elbow rot_x that put the hand on the floor at y_h."""
    sy_ = root_y - 0.55 * math.sin(theta)
    sz_ = root_z + 0.55 * math.cos(theta)
    dy, dz = y_h - sy_, 0.065 - sz_
    D = min(max(math.hypot(dy, dz), 0.12), A_UP + A_LO - 0.01)
    phi = math.atan2(dy, -dz)
    ac = lambda v: math.acos(min(1.0, max(-1.0, v)))
    delta = ac((A_UP ** 2 + D ** 2 - A_LO ** 2) / (2 * A_UP * D))
    gamma = ac((A_LO ** 2 + D ** 2 - A_UP ** 2) / (2 * A_LO * D))
    alpha, beta = phi + delta, phi - gamma
    return alpha - theta, beta - alpha


def plank(P, theta, y_toe, y_h, hands=1.0):
    """Toes planted at y_toe, hands planted at y_h; weight `hands` blends the arms from standing to the IK solution."""
    P["rx"] = theta
    P["y"] = y_toe - 0.93 * math.sin(theta)
    P["z"] = 0.195 * math.sin(theta) + 0.03 + 0.93 * math.cos(theta) + 0.03 * math.cos(theta) ** 2
    sx, el = arm_ik(theta, P["y"], P["z"], y_h)
    P["sx"], P["el"] = lerp(ARM_STAND["sx"], sx, hands), lerp(ARM_STAND["el"], el, hands)
    P["sy"] = lerp(ARM_STAND["sy"], 0.12, hands)
    P["head"] = -0.55 * smooth(theta / TH_UP)
    P["hipF"] = P["kneeF"] = P["torso"] = 0.0


def floor_pose(t, P, F, x, y, rz):
    """Pushups then twerk. P already holds the standing defaults."""
    P["x"], P["rz"] = x, rz
    y_toe = y
    y_h = y_toe - 1.48 * math.sin(TH_UP)
    if t < F["R0"]:                                   # drop to plank
        k = smooth((t - F["A"]) / GET_DOWN)
        plank(P, TH_UP * k, y_toe, y_h, hands=smooth((k - 0.35) / 0.5))
    elif t < F["R1"]:                                 # pushup reps
        u = (t - F["R0"]) / PUSH_PERIOD
        th = TH_UP + (TH_DN - TH_UP) * (0.5 - 0.5 * math.cos(TAU * u))
        plank(P, th, y_toe, y_h)
    elif t < F["B"]:                                  # back to standing
        k = 1 - smooth((t - F["R1"]) / GET_DOWN)
        plank(P, TH_UP * k, y_toe, y_h, hands=smooth((k - 0.35) / 0.5))
    elif t < F["T1"]:                                 # twerk
        tt = t - F["T0"]
        w = smooth(tt / TWERK_IN) * (1 - smooth((tt - TWERK_IN - TWERK_HOLD) / TWERK_IN))
        osc = math.sin(TAU * TWERK_HZ * tt)
        tilt = 0.30 * w * osc
        crouch(P, 0.95 * w)
        P["z"] += 0.035 * w * math.sin(TAU * TWERK_HZ * tt + 1.57)
        P["rx"] = tilt
        P["hipF"] += tilt                              # counter-rotate so thighs, torso stay put
        P["torso"] = 1.0 * w - tilt
        P["split"] = 0.35 * w
        P["head"] = -0.5 * w
        P["sx"], P["el"], P["sy"] = -1.0 * w + 0.05 * (1 - w) - 0.0, -0.3 * w - 0.2 * (1 - w), 0.14
        P["sx"] -= 0.0
        P["rz"] = rz + 0.12 * w * math.sin(TAU * TWERK_HZ * 0.5 * tt)
    else:                                             # victory
        k = smooth((t - F["C"]) / 0.35)
        P.update(blend(ARM_STAND, ARM_V, k))
        P["head"] = -0.2 * k
    return P


def pose(t, S):
    P = dict(x=START_X, y=START_Y, z=STAND_Z, rx=0.0, rz=0.0, hipF=0.0, kneeF=0.0, ankle=0.0,
             split=0.0, torso=0.0, head=0.0, **ARM_STAND)
    mv = None
    for s in S:
        if t >= s["w0"]:
            mv = s
    if mv is None:                                   # lead-in idle
        P["z"] += 0.006 * math.sin(TAU * 0.9 * t)
        P["torso"] = 0.02 * math.sin(TAU * 0.9 * t)
        return P

    P["x"], P["y"] = mv["x0"], mv["y0"]
    P["rx"], P["rz"] = -TAU * mv["f0"], TAU * mv["t0"]
    take, land, T = mv["take"], mv["land"], mv["T"]
    end_x, end_y = mv["x1"], mv["y1"]
    end_rx = -TAU * (mv["f0"] + mv["flips"])
    end_rz = TAU * (mv["t0"] + mv["twist"])

    if t >= mv["end"]:                               # floor routine + victory pose after the last move
        P = floor_pose(t, P, floor_times(S), end_x, end_y, end_rz)
        P["rx"] += end_rx                            # keep the Euler angle continuous (whole turns)
        return P

    if t < take - PUSH:                              # wind-up crouch, arms swing back
        k = smooth((t - mv["w0"]) / (WIND - PUSH))
        crouch(P, PHI_DEEP * k)
        P.update(blend(ARM_STAND, ARM_BACK, k))
        P["torso"] = 0.35 * k
    elif t < take:                                   # explosive push, arms swing up
        k = smoother((t - (take - PUSH)) / PUSH)
        crouch(P, PHI_DEEP * (1 - k))
        P.update(blend(ARM_BACK, ARM_UP, k))
        P["torso"] = 0.35 * (1 - k)
    elif t < land:                                   # flight
        u = (t - take) / T
        tau = u * T
        P["z"] = STAND_Z + G * T * tau / 2 - 0.5 * G * tau * tau
        P["x"], P["y"] = lerp(mv["x0"], end_x, u), lerp(mv["y0"], end_y, u)
        kind = mv["kind"]
        pt = smooth(u / 0.15) * (1 - smooth((u - 0.88) / 0.1))      # pointed toes
        P["ankle"] = 0.5 * pt
        P.update(ARM_UP)
        if kind in ("tuck", "layout"):
            fl = smoother((u - 0.04) / 0.86)
            P["rx"] = -TAU * (mv["f0"] + mv["flips"] * fl)
        if kind == "tuck":
            hold_end = 0.72 if mv["flips"] == 1 else 0.80
            tk = smooth((u - 0.04) / 0.22) * (1 - smooth((u - hold_end) / 0.13))
            P["hipF"], P["kneeF"] = 1.75 * tk, 2.35 * tk
            P["torso"], P["head"] = 0.85 * tk, 0.3 * tk
            P.update(blend(ARM_UP, ARM_TUCK, tk))
        elif kind == "layout":
            arch = smooth(u / 0.2) * (1 - smooth((u - 0.8) / 0.15))
            P["torso"], P["hipF"] = -0.12 * arch, -0.12 * arch
            tw = smoother((u - 0.22) / 0.56)
            P["rz"] = TAU * (mv["t0"] + mv["twist"] * tw)
            aw = smooth((u - 0.2) / 0.12) * (1 - smooth((u - 0.78) / 0.1))
            P.update(blend(ARM_UP, ARM_TWIST, aw))
        elif kind == "spin":
            P["rz"] = TAU * (mv["t0"] + mv["twist"] * smoother((u - 0.06) / 0.84))
            ap = smooth((u - 0.06) / 0.2)
            sp = ap * (1 - smooth((u - 0.9) / 0.08))
            P.update(blend(ARM_UP, ARM_OUT, ap))
            P["split"], P["kneeF"], P["hipF"] = 0.5 * sp, 0.5 * sp, 0.35 * sp
    elif t < land + ABSORB:                          # landing absorb
        x = (t - land) / ABSORB
        e = 1 - (1 - x) ** 2
        P["x"], P["y"], P["rx"], P["rz"] = end_x, end_y, end_rx, end_rz
        crouch(P, PHI_LAND * e)
        P.update(blend(ARM_OUT if mv["kind"] == "spin" else ARM_UP, ARM_BAL, e))
        P["torso"] = 0.3 * e
    else:                                            # recover to standing
        x = smooth((t - land - ABSORB) / RECOVER)
        P["x"], P["y"], P["rx"], P["rz"] = end_x, end_y, end_rx, end_rz
        crouch(P, PHI_LAND * (1 - x))
        P.update(blend(ARM_BAL, ARM_STAND, x))
        P["torso"] = 0.3 * (1 - x)
    return P


def camera(t, P, F, S):
    """Orbit during flips, swing to the side for pushups, behind-3/4 for the twerk, back to front for the finish."""
    a0 = lerp(-0.45, 0.45, clamp(t / F["A"]))
    wf = smooth((t - F["A"]) / 1.2)                                   # floor-phase weight
    side = smooth((F["R0"] - 0.6 - t) / -1.0) * (1 - smooth((t - (F["B"] - 0.3)) / 1.0))
    back = smooth((t - (F["T0"] - 0.3)) / 0.9) * (1 - smooth((t - (F["C"] - 0.2)) / 1.0))
    az = a0 * (1 - wf) + wf * (0.0 + 1.15 * side + 2.6 * back + 0.3 * (1 - side - back if side + back < 1 else 0))
    dist = lerp(6.4, 6.0, wf)
    ch = lerp(1.9, 1.4, wf)
    tz = lerp(1.15 + 0.7 * (P["z"] - STAND_Z), 0.55 + 0.4 * P["z"], wf)
    return az, dist, ch, tz, wf


def build(bpy, fps):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    sc = bpy.context.scene
    n_frames = int(round(fps * DURATION))
    sc.frame_start, sc.frame_end = 1, n_frames
    sc.render.fps = fps
    sc.view_settings.view_transform = "Standard"
    S = schedule()

    def mat(name, color, rough=0.5):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = color
        b.inputs["Roughness"].default_value = rough
        return m

    skin = mat("skin", (0.80, 0.48, 0.30, 1), 0.55)
    shirt = mat("shirt", (0.03, 0.50, 0.70, 1), 0.6)
    pants = mat("pants", (0.05, 0.06, 0.16, 1), 0.7)
    shoe = mat("shoe", (0.9, 0.9, 0.9, 1), 0.4)
    hair = mat("hair", (0.02, 0.015, 0.015, 1), 0.6)
    band = mat("band", (0.85, 0.05, 0.05, 1), 0.5)
    white = mat("eyewhite", (1, 1, 1, 1), 0.2)
    black = mat("pupil", (0.01, 0.01, 0.01, 1), 0.1)

    def joint(name, parent, loc):
        j = bpy.data.objects.new(name, None)
        j.empty_display_size = 0.05
        j.rotation_mode = "ZYX"
        sc.collection.objects.link(j)
        j.parent = parent
        j.location = loc
        return j

    def blob(parent, name, loc, scale, m):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=24, ring_count=12, location=(0, 0, 0))
        o = bpy.context.object
        o.name = name
        o.scale = scale
        o.data.materials.append(m)
        for p in o.data.polygons:
            p.use_smooth = True
        o.parent = parent
        o.location = loc
        return o

    root = joint("root", None, (START_X, START_Y, STAND_Z))
    blob(root, "hips", (0, 0, 0), (0.185, 0.115, 0.13), pants)
    torso = joint("torso", root, (0, 0, 0.10))
    blob(torso, "chest", (0, 0, 0.25), (0.20, 0.125, 0.27), shirt)
    head = joint("head", torso, (0, 0, 0.52))
    blob(head, "skull", (0, 0, 0.15), (0.115, 0.125, 0.135), skin)
    blob(head, "hair", (0, 0.03, 0.20), (0.125, 0.135, 0.12), hair)
    for sx in (-1, 1):
        blob(head, "eye", (sx * 0.045, -0.105, 0.17), (0.032, 0.032, 0.032), white)
        blob(head, "pupil", (sx * 0.045, -0.133, 0.17), (0.016, 0.016, 0.016), black)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.128, minor_radius=0.014, location=(0, 0, 0))
    hb = bpy.context.object
    hb.data.materials.append(band)
    hb.scale = (1.0, 1.06, 1.0)
    hb.parent = head
    hb.location = (0, 0.005, 0.19)

    sides = []
    for side in (1, -1):                              # +1 = +X (character's left)
        sh = joint("shoulder", torso, (side * 0.255, 0, 0.45))
        blob(sh, "upperarm", (0, 0, -0.14), (0.06, 0.06, 0.17), shirt)
        el = joint("elbow", sh, (0, 0, -0.30))
        blob(el, "forearm", (0, 0, -0.13), (0.048, 0.048, 0.15), skin)
        blob(el, "hand", (0, 0, -0.29), (0.058, 0.05, 0.065), skin)
        hip = joint("hip", root, (side * 0.095, 0, -0.05))
        blob(hip, "thigh", (0, 0, -0.22), (0.085, 0.085, 0.25), pants)
        knee = joint("knee", hip, (0, 0, -0.45))
        blob(knee, "shin", (0, 0, -0.215), (0.065, 0.065, 0.24), pants)
        ank = joint("ankle", knee, (0, 0, -0.43))
        blob(ank, "shoe", (0, -0.055, -0.01), (0.062, 0.14, 0.04), shoe)
        sides.append((side, sh, el, hip, knee, ank))

    # stage: checker floor, background pillars
    bpy.ops.mesh.primitive_plane_add(size=80)
    fl = mat("floor", (0.5, 0.5, 0.5, 1), 0.8)
    nt = fl.node_tree
    chk = nt.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 40
    chk.inputs["Color1"].default_value = (0.30, 0.32, 0.38, 1)
    chk.inputs["Color2"].default_value = (0.17, 0.18, 0.23, 1)
    nt.links.new(chk.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    bpy.context.object.data.materials.append(fl)
    pillars = [(-9, 9, 1.6, (0.9, 0.25, 0.2)), (-5.5, 12, 3.0, (0.95, 0.7, 0.15)),
               (-2, 10, 2.0, (0.2, 0.7, 0.4)), (2.5, 13, 3.6, (0.3, 0.4, 0.9)),
               (6, 10, 2.4, (0.85, 0.3, 0.6)), (9.5, 12, 1.8, (0.2, 0.75, 0.8)),
               (13, 9, 3.2, (0.9, 0.5, 0.2)), (-13, 11, 2.8, (0.5, 0.35, 0.85))]
    for i, (px, py, ph, col) in enumerate(pillars):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(px, py, ph / 2))
        pl = bpy.context.object
        pl.scale = (1.4, 1.4, ph)
        pl.data.materials.append(mat(f"pillar{i}", col + (1,), 0.5))

    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), 0, math.radians(30)))
    sun = bpy.context.object
    sun.data.energy = 3
    sun.data.angle = math.radians(4)
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.7, 0.85, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    sc.world = w

    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 38
    cam_data.clip_end = 300
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.camera = cam
    tgt = bpy.data.objects.new("tgt", None)
    sc.collection.objects.link(tgt)
    tc = cam.constraints.new("TRACK_TO")
    tc.target = tgt
    tc.track_axis = "TRACK_NEGATIVE_Z"
    tc.up_axis = "UP_Y"

    F = floor_times(S)
    if F["C"] + 1.0 > DURATION:
        raise ValueError(f"floor routine ends at {F['C']:.2f}s, DURATION {DURATION}s too short")
    for f in range(1, n_frames + 1):
        t = (f - 1) / fps
        P = pose(t, S)
        root.location = (P["x"], P["y"], P["z"])
        root.rotation_euler = (P["rx"], 0.0, P["rz"])
        torso.rotation_euler = (P["torso"], 0.0, 0.0)
        head.rotation_euler = (P["head"], 0.0, 0.0)
        for side, sh, el, hip, knee, ank in sides:
            sh.rotation_euler = (P["sx"], -side * P["sy"], 0.0)
            el.rotation_euler = (P["el"], 0.0, 0.0)
            hip.rotation_euler = (-P["hipF"], -side * P["split"], 0.0)
            knee.rotation_euler = (P["kneeF"], 0.0, 0.0)
            ank.rotation_euler = (P["ankle"], 0.0, 0.0)
        az, dist, ch, tz, wf = camera(t, P, F, S)
        tgt.location = (P["x"], P["y"], tz)
        cam.location = (dist * math.sin(az) + P["x"] * 0.3, -dist * math.cos(az) + P["y"] * 0.3, ch)
        root.keyframe_insert("location", frame=f)
        root.keyframe_insert("rotation_euler", frame=f)
        tgt.keyframe_insert("location", frame=f)
        cam.keyframe_insert("location", frame=f)
        for o in [torso, head] + [j for s in sides for j in s[1:]]:
            o.keyframe_insert("rotation_euler", frame=f)
