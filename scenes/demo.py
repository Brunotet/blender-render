"""Demo scene: a simple stylized crab sidestepping on sand. Replace with your own scenes."""
import math


def build(bpy, fps):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start = 1
    sc.frame_end = fps * 10
    sc.view_settings.view_transform = "Standard"   # punchy colors, no AgX wash-out

    def mat(name, color, rough=0.6):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = color
        b.inputs["Roughness"].default_value = rough
        return m

    sand = mat("sand", (0.62, 0.45, 0.24, 1), 0.9)
    shell = mat("shell", (0.80, 0.10, 0.04, 1), 0.35)
    white = mat("white", (1, 1, 1, 1), 0.2)
    black = mat("black", (0.01, 0.01, 0.01, 1), 0.1)

    bpy.ops.mesh.primitive_plane_add(size=30)
    bpy.context.object.data.materials.append(sand)

    # unscaled rig parent so child parts are not distorted by the squashed body
    rig = bpy.data.objects.new("rig", None)
    sc.collection.objects.link(rig)

    def part(kind, loc, scale, m, rot=(0, 0, 0)):
        if kind == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=loc)
        else:
            bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=1, location=loc)
        o = bpy.context.object
        o.scale = scale
        o.rotation_euler = rot
        o.data.materials.append(m)
        if kind == "sphere":
            bpy.ops.object.shade_smooth()
        o.parent = rig
        return o

    part("sphere", (0, 0, 0.7), (1.3, 1.0, 0.6), shell)            # body
    for sx in (-0.45, 0.45):
        part("sphere", (sx, -0.7, 1.35), (0.22, 0.22, 0.22), white)  # eye
        part("sphere", (sx, -0.88, 1.35), (0.1, 0.1, 0.1), black)    # pupil
    for side in (-1, 1):
        for k in range(3):
            part("cyl", (side * 1.55, -0.3 + k * 0.4, 0.32),
                 (0.07, 0.07, 0.9), shell, rot=(0, -side * math.radians(55), 0))
        part("sphere", (side * 1.7, -0.95, 0.75), (0.4, 0.3, 0.3), shell)  # claw

    end = sc.frame_end
    for f in range(1, end + 1, 3):
        t = f / end
        rig.location = (math.sin(t * math.tau) * 1.8, 0, abs(math.sin(f * 0.5)) * 0.06)
        rig.keyframe_insert("location", frame=f)

    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), 0, math.radians(30)))
    bpy.context.object.data.energy = 4
    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    cam.location = (0, -9, 3.2)
    cam.rotation_euler = (math.radians(75), 0, 0)
    sc.camera = cam

    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.7, 0.85, 1)
    sc.world = w
