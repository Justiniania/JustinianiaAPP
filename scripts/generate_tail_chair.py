"""Generate a life-size, tail-friendly wooden chair as a Blender scene."""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "tail_friendly_wooden_chair.blend"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.materials, bpy.data.curves, bpy.data.meshes, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def wood_material(name, dark=(0.22, 0.055, 0.018, 1), light=(0.62, 0.24, 0.055, 1)):
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

    noise.inputs["Scale"].default_value = 3.2
    noise.inputs["Detail"].default_value = 5.0
    noise.inputs["Roughness"].default_value = 0.7
    noise.inputs["Distortion"].default_value = 0.18
    mapping.inputs["Scale"].default_value = (1.0, 7.0, 1.0)
    ramp.color_ramp.elements[0].color = dark
    ramp.color_ramp.elements[1].color = light
    ramp.color_ramp.elements[0].position = 0.30
    ramp.color_ramp.elements[1].position = 0.72
    bsdf.inputs["Roughness"].default_value = 0.28
    bsdf.inputs["Coat Weight"].default_value = 0.24
    bsdf.inputs["Coat Roughness"].default_value = 0.18
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.025

    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def simple_material(name, color, roughness=0.5):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def box(name, location, scale, material, bevel=0.025, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (scale[0] / 2, scale[1] / 2, scale[2] / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel_mod = obj.modifiers.new("Soft handcrafted edges", "BEVEL")
    bevel_mod.width = bevel
    bevel_mod.segments = 4
    obj.data.materials.append(material)
    return obj


def cylinder(name, location, radius, depth, material, rotation=(0, 0, 0), vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    bevel_mod = obj.modifiers.new("Rounded ends", "BEVEL")
    bevel_mod.width = min(radius * 0.20, 0.012)
    bevel_mod.segments = 3
    obj.data.materials.append(material)
    return obj


def beam_between(name, start, end, radius, material):
    start, end = Vector(start), Vector(end)
    delta = end - start
    obj = cylinder(name, (start + end) / 2, radius, delta.length, material)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    return obj


def add_text_label():
    bpy.ops.object.text_add(location=(-0.63, 0.36, 0.025), rotation=(0, 0, 0))
    label = bpy.context.object
    label.name = "Design note"
    label.data.body = "TAIL-FRIENDLY\nSOLID WOOD CHAIR"
    label.data.align_x = "CENTER"
    label.data.size = 0.055
    label.data.extrude = 0.002
    label.data.materials.append(bpy.data.materials["Brass"])


def point_camera(camera, target):
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def build_scene():
    clear_scene()
    wood = wood_material("Warm oiled walnut")
    accent = wood_material("Dark walnut accents", (0.07, 0.014, 0.006, 1), (0.32, 0.07, 0.016, 1))
    floor_mat = simple_material("Warm limestone", (0.30, 0.25, 0.19, 1), 0.72)
    brass = simple_material("Brass", (0.42, 0.19, 0.035, 1), 0.24)
    brass.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.82

    # Broad U-shaped seat: front bridge supports the sitter, rear opening gives a
    # large tail a natural path down and behind without being pinned.
    box("Seat front bridge", (0, -0.17, 0.47), (0.82, 0.38, 0.075), wood, 0.035)
    box("Seat left wing", (-0.265, 0.155, 0.47), (0.29, 0.27, 0.075), wood, 0.035)
    box("Seat right wing", (0.265, 0.155, 0.47), (0.29, 0.27, 0.075), wood, 0.035)
    # Rounded rails frame the tail channel without closing its rear exit.
    cylinder("Tail channel left rim", (-0.128, 0.155, 0.515), 0.022, 0.26, accent, (math.pi / 2, 0, 0))
    cylinder("Tail channel right rim", (0.128, 0.155, 0.515), 0.022, 0.26, accent, (math.pi / 2, 0, 0))

    # Splayed legs, set wide for stability.
    for side, x in (("L", -0.34), ("R", 0.34)):
        beam_between(f"{side} front leg", (x * 0.96, -0.24, 0.45), (x * 1.08, -0.29, 0.04), 0.038, accent)
        beam_between(f"{side} rear leg", (x * 0.96, 0.20, 0.45), (x * 1.08, 0.27, 0.04), 0.038, accent)
        beam_between(f"{side} side stretcher", (x * 1.045, -0.25, 0.17), (x * 1.045, 0.235, 0.17), 0.021, wood)
    beam_between("Front stretcher", (-0.35, -0.275, 0.18), (0.35, -0.275, 0.18), 0.023, wood)

    # Back uprights lean rearward. Central slats stop above the tail exit.
    beam_between("Left back post", (-0.35, 0.22, 0.47), (-0.39, 0.35, 1.15), 0.042, accent)
    beam_between("Right back post", (0.35, 0.22, 0.47), (0.39, 0.35, 1.15), 0.042, accent)
    box("Back crest", (0, 0.34, 1.10), (0.77, 0.075, 0.095), wood, 0.038, (math.radians(-8), 0, 0))
    for index, x in enumerate((-0.24, -0.12, 0.0, 0.12, 0.24), 1):
        beam_between(f"Back slat {index}", (x, 0.275, 0.67), (x * 1.10, 0.335, 1.065), 0.027, wood)
    box("Lumbar rail", (0, 0.285, 0.72), (0.68, 0.055, 0.075), wood, 0.025, (math.radians(-8), 0, 0))

    # Open, gently rising arms leave generous hip room.
    for side, x in (("Left", -0.39), ("Right", 0.39)):
        beam_between(f"{side} arm support", (x, -0.17, 0.47), (x, -0.15, 0.70), 0.032, accent)
        beam_between(f"{side} arm", (x, -0.25, 0.70), (x, 0.25, 0.78), 0.047, wood)

    # Floor and small design plaque.
    box("Studio floor", (0, 0, -0.035), (5.0, 5.0, 0.07), floor_mat, 0.01)
    add_text_label()

    bpy.ops.object.light_add(type="SUN", location=(2.5, -3.0, 4.0))
    sun = bpy.context.object
    sun.name = "Warm afternoon sun"
    sun.rotation_euler = (math.radians(28), math.radians(-22), math.radians(-32))
    sun.data.energy = 2.1
    sun.data.angle = math.radians(12)
    sun.data.color = (1.0, 0.72, 0.48)
    bpy.ops.object.light_add(type="AREA", location=(-2.2, -1.5, 2.8))
    fill = bpy.context.object
    fill.name = "Soft sky fill"
    fill.data.energy = 650
    fill.data.shape = "DISK"
    fill.data.size = 3.0
    fill.data.color = (0.55, 0.70, 1.0)
    fill.rotation_euler = (math.radians(22), 0, math.radians(-38))

    bpy.ops.object.camera_add(location=(2.15, -2.45, 1.55))
    camera = bpy.context.object
    camera.name = "Presentation camera"
    camera.data.lens = 54
    point_camera(camera, (0, 0.02, 0.58))
    bpy.context.scene.camera = camera

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(ROOT / "assets" / "tail_friendly_wooden_chair_preview.png")
    scene.world.color = (0.035, 0.045, 0.065)
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0
    scene["design_note"] = "Life-size wide chair with a 24 cm rear tail channel for a large tail."
    scene["dimensions_m"] = "0.82 W x 0.65 D x 1.15 H; seat height 0.47"

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
    if "--render-preview" in sys.argv:
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build_scene()
