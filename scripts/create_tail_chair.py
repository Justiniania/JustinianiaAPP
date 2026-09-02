import bpy
import math
from pathlib import Path
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "tail_friendly_wooden_chair.blend"
PREVIEW_PATH = ROOT / "tail_friendly_wooden_chair_preview.png"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.materials, bpy.data.curves, bpy.data.meshes, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def wood_material(name, base, roughness=0.3):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    noise = nodes.new("ShaderNodeTexNoise")
    mapping = nodes.new("ShaderNodeMapping")
    texcoord = nodes.new("ShaderNodeTexCoord")
    ramp = nodes.new("ShaderNodeValToRGB")
    bump = nodes.new("ShaderNodeBump")
    noise.inputs["Scale"].default_value = 4.2
    noise.inputs["Detail"].default_value = 3.5
    noise.inputs["Roughness"].default_value = 0.65
    noise.inputs["Distortion"].default_value = 0.18
    mapping.inputs["Scale"].default_value = (1.2, 7.0, 1.2)
    ramp.color_ramp.elements[0].color = (*[v * 0.28 for v in base], 1)
    ramp.color_ramp.elements[1].color = (*base, 1)
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[1].position = 0.78
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["IOR"].default_value = 1.48
    bump.inputs["Strength"].default_value = 0.16
    bump.inputs["Distance"].default_value = 0.025
    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def rounded_box(name, location, scale, material, bevel=0.035, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = tuple(v / 2 for v in scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel_mod = obj.modifiers.new("Soft handcrafted edges", "BEVEL")
    bevel_mod.width = bevel
    bevel_mod.segments = 5
    obj.data.materials.append(material)
    return obj


def tapered_leg(name, x, y, z, height, material, splay_x=0.0, splay_y=0.0):
    leg = rounded_box(name, (x, y, z), (0.105, 0.105, height), material, 0.025)
    leg.rotation_euler = (splay_y, splay_x, 0)
    return leg


def curved_rail(name, points, bevel, material):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 16
    curve.bevel_depth = bevel
    curve.bevel_resolution = 5
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for bp, co in zip(spline.bezier_points, points):
        bp.co = co
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def point_camera(camera, target):
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


clear_scene()
oak = wood_material("Warm quarter-sawn oak", (0.64, 0.29, 0.085), 0.26)
dark_oak = wood_material("Dark end-grain accents", (0.25, 0.075, 0.022), 0.34)

# Seat: 88 cm wide and 72 cm deep. The rear-centre opening is 38 cm wide,
# giving a large tail a direct, pressure-free path behind the sitter.
rounded_box("Seat front bridge", (0, -0.12, 0.475), (0.88, 0.46, 0.105), oak, 0.045)
rounded_box("Seat rear left wing", (-0.315, 0.235, 0.475), (0.25, 0.25, 0.105), oak, 0.045)
rounded_box("Seat rear right wing", (0.315, 0.235, 0.475), (0.25, 0.25, 0.105), oak, 0.045)

# Subtle inner guides round off and visually frame the tail opening.
rounded_box("Tail guide left", (-0.208, 0.235, 0.505), (0.045, 0.245, 0.07), dark_oak, 0.022)
rounded_box("Tail guide right", (0.208, 0.235, 0.505), (0.045, 0.245, 0.07), dark_oak, 0.022)

for name, x, y, sx, sy in (
    ("Front left leg", -0.35, -0.27, -0.045, 0.035),
    ("Front right leg", 0.35, -0.27, 0.045, 0.035),
    ("Rear left leg", -0.35, 0.27, -0.035, -0.035),
    ("Rear right leg", 0.35, 0.27, 0.035, -0.035),
):
    tapered_leg(name, x, y, 0.245, 0.49, oak, sx, sy)

# Stretchers add structural plausibility without obstructing the rear opening.
rounded_box("Front stretcher", (0, -0.29, 0.235), (0.68, 0.065, 0.075), dark_oak, 0.025)
rounded_box("Left stretcher", (-0.35, 0, 0.235), (0.065, 0.47, 0.075), dark_oak, 0.025)
rounded_box("Right stretcher", (0.35, 0, 0.235), (0.065, 0.47, 0.075), dark_oak, 0.025)

# Open-backed frame: no centre splat, preserving tail clearance above the notch.
rounded_box("Back left post", (-0.39, 0.31, 0.96), (0.105, 0.105, 1.02), oak, 0.035, (math.radians(-6), 0, 0))
rounded_box("Back right post", (0.39, 0.31, 0.96), (0.105, 0.105, 1.02), oak, 0.035, (math.radians(-6), 0, 0))
curved_rail("Crest rail", [(-0.39, 0.40, 1.38), (0, 0.47, 1.46), (0.39, 0.40, 1.38)], 0.065, oak)
curved_rail("Lumbar rail", [(-0.37, 0.36, 0.93), (0, 0.42, 0.98), (0.37, 0.36, 0.93)], 0.052, oak)
curved_rail("Shoulder rail", [(-0.38, 0.39, 1.18), (0, 0.46, 1.24), (0.38, 0.39, 1.18)], 0.055, oak)

# Broad arm rests, slightly flared for a relaxed posture.
rounded_box("Left arm", (-0.49, -0.01, 0.79), (0.115, 0.68, 0.09), oak, 0.04, (0, 0, math.radians(-2)))
rounded_box("Right arm", (0.49, -0.01, 0.79), (0.115, 0.68, 0.09), oak, 0.04, (0, 0, math.radians(2)))
for side, x in (("Left", -0.49), ("Right", 0.49)):
    rounded_box(f"{side} front arm support", (x, -0.26, 0.65), (0.08, 0.08, 0.32), dark_oak, 0.025)

# Floor and warm sunlight make the wood grain and rounded highlights legible.
floor_mat = bpy.data.materials.new("Warm neutral floor")
floor_mat.diffuse_color = (0.16, 0.14, 0.11, 1)
floor_mat.roughness = 0.55
rounded_box("Studio floor", (0, 0, -0.045), (5.5, 5.5, 0.08), floor_mat, 0.015)

bpy.ops.object.light_add(type="SUN", location=(-3, -4, 6))
sun = bpy.context.object
sun.name = "Late afternoon sun"
sun.data.energy = 2.2
sun.data.angle = math.radians(18)
sun.rotation_euler = (math.radians(28), math.radians(-24), math.radians(-32))
bpy.ops.object.light_add(type="AREA", location=(2.8, -3.2, 3.8))
area = bpy.context.object
area.name = "Soft window fill"
area.data.energy = 700
area.data.shape = "DISK"
area.data.size = 3.0
point_camera(area, (0, 0, 0.7))

bpy.ops.object.camera_add(location=(2.55, -3.15, 2.05))
camera = bpy.context.object
camera.name = "Chair presentation camera"
camera.data.lens = 54
point_camera(camera, (0, 0.02, 0.72))
bpy.context.scene.camera = camera

world = bpy.context.scene.world
world.color = (0.035, 0.045, 0.065)
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.045, 0.06, 0.09, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.32

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16
scene.render.resolution_x = 800
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(PREVIEW_PATH)
scene.render.film_transparent = False
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.look = "AgX - Medium High Contrast"
scene["design_dimensions"] = "0.88m W x 0.72m D x 1.46m H; seat height 0.53m"
scene["tail_clearance"] = "0.38m wide rear-centre opening, open through chair back"
scene["design_note"] = "Concept furniture: verify ergonomics and structure before fabrication"

bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
bpy.ops.render.render(write_still=True)
print(f"Saved {BLEND_PATH}")
print(f"Rendered {PREVIEW_PATH}")
