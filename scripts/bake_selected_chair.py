"""Bake the active mesh object's materials to one PBR texture set.

Usage in Blender:
  1. Select exactly one chair mesh and make it the active object.
  2. Open this file in Blender's Text Editor and press Run Script.

The script keeps existing materials intact and writes 2048px PNG files to
``//baked_<object_name>/`` beside the current .blend file.
"""

import re
from pathlib import Path

import bpy


# Conservative defaults keep the bake usable on machines with modest RAM.
# A 4096px RGBA bake buffer is four times larger than a 2048px one, and Blender
# may keep several such buffers resident while the script runs.
TEXTURE_SIZE = 2048
BAKE_MARGIN = 16
BAKE_SAMPLES = 16


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "object"


def active_mesh():
    obj = bpy.context.view_layer.objects.active
    if obj is None or obj.type != "MESH":
        raise RuntimeError("Make one chair mesh the active object before running the script.")
    if not obj.data.materials:
        raise RuntimeError("The active chair has no material slots to bake.")
    return obj


def ensure_unique_uv(obj):
    """Create a non-overlapping atlas only when the object has no UV map."""
    if obj.data.uv_layers:
        obj.data.uv_layers.active = obj.data.uv_layers[0]
        return
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.data.uv_layers.active.name = "BakeUV"


def image_for(label, output_dir, non_color=False):
    image = bpy.data.images.new(
        name=f"BAKE_{label}",
        width=TEXTURE_SIZE,
        height=TEXTURE_SIZE,
        alpha=False,
        float_buffer=False,
    )
    image.file_format = "PNG"
    image.filepath_raw = str(output_dir / f"{label}.png")
    if non_color:
        image.colorspace_settings.name = "Non-Color"
    return image


def activate_image_in_all_materials(obj, image, label):
    """Cycles bakes to the active Image Texture node in every material."""
    targets = []
    for material in {slot.material for slot in obj.material_slots if slot.material}:
        material.use_nodes = True
        nodes = material.node_tree.nodes
        node = nodes.new("ShaderNodeTexImage")
        node.name = f"BAKE_TARGET_{label}"
        node.label = f"Bake target: {label}"
        node.image = image
        node.select = True
        nodes.active = node
        targets.append((nodes, node))
    return targets


def remove_bake_targets(targets):
    """Discard temporary nodes after each pass to keep the scene lightweight."""
    for nodes, node in targets:
        nodes.remove(node)


def bake_standard(obj, image, bake_type):
    targets = activate_image_in_all_materials(obj, image, image.name)
    try:
        bpy.ops.object.bake(type=bake_type, margin=BAKE_MARGIN, use_clear=True)
        image.save()
    finally:
        remove_bake_targets(targets)


def bake_base_color(obj, image):
    targets = activate_image_in_all_materials(obj, image, image.name)
    scene = bpy.context.scene
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    try:
        bpy.ops.object.bake(type="DIFFUSE", margin=BAKE_MARGIN, use_clear=True)
        image.save()
    finally:
        remove_bake_targets(targets)


def metallic_source(material):
    """Return the connected/default Metallic source from a Principled shader."""
    nodes = material.node_tree.nodes
    principled = next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)
    if principled is None:
        return None, 0.0
    socket = principled.inputs.get("Metallic")
    if socket and socket.is_linked:
        return socket.links[0].from_socket, 0.0
    return None, float(socket.default_value) if socket else 0.0


def bake_metallic(obj, image):
    """Temporarily route Metallic through Emission, bake it, then restore output."""
    restorations = []
    for material in {slot.material for slot in obj.material_slots if slot.material}:
        material.use_nodes = True
        tree = material.node_tree
        output = next((node for node in tree.nodes if node.type == "OUTPUT_MATERIAL" and node.is_active_output), None)
        if output is None:
            output = tree.nodes.new("ShaderNodeOutputMaterial")
        surface = output.inputs["Surface"]
        old_links = [(link.from_socket, link.to_socket) for link in list(surface.links)]
        for link in list(surface.links):
            tree.links.remove(link)

        emission = tree.nodes.new("ShaderNodeEmission")
        emission.name = "TEMP_METALLIC_BAKE"
        source, default = metallic_source(material)
        if source:
            tree.links.new(source, emission.inputs["Color"])
        else:
            emission.inputs["Color"].default_value = (default, default, default, 1.0)
        tree.links.new(emission.outputs["Emission"], surface)
        restorations.append((tree, emission, old_links))

    targets = []
    try:
        targets = activate_image_in_all_materials(obj, image, image.name)
        bpy.ops.object.bake(type="EMIT", margin=BAKE_MARGIN, use_clear=True)
        image.save()
    finally:
        remove_bake_targets(targets)
        for tree, emission, old_links in restorations:
            for link in list(emission.outputs["Emission"].links):
                tree.links.remove(link)
            tree.nodes.remove(emission)
            for from_socket, to_socket in old_links:
                tree.links.new(from_socket, to_socket)


def main():
    if not bpy.data.filepath:
        raise RuntimeError("Save the .blend file before baking so output paths are predictable.")

    obj = active_mesh()
    bpy.ops.object.mode_set(mode="OBJECT") if obj.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    ensure_unique_uv(obj)

    output_dir = Path(bpy.path.abspath("//")) / f"baked_{safe_name(obj.name)}"
    output_dir.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = BAKE_SAMPLES
    scene.render.bake.target = "IMAGE_TEXTURES"
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.margin = BAKE_MARGIN

    # Process one map at a time and release its pixel buffer immediately after
    # saving. This avoids holding four full-resolution bake buffers in RAM.
    bake_jobs = (
        ("BaseColor", False, bake_base_color, None),
        ("Roughness", True, bake_standard, "ROUGHNESS"),
        ("Metallic", True, bake_metallic, None),
        ("Normal", True, bake_standard, "NORMAL"),
    )
    for label, non_color, bake_function, bake_type in bake_jobs:
        image = image_for(label, output_dir, non_color=non_color)
        if bake_type is None:
            bake_function(obj, image)
        else:
            bake_function(obj, image, bake_type)
        image.buffers_free()

    print(f"Finished baking {obj.name} to {output_dir}")


if __name__ == "__main__":
    main()
