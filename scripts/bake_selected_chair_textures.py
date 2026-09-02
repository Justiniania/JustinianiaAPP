"""Bake selected mesh objects into one texture-atlased Blender asset.

Run from a terminal:
  blender chair.blend --background --python scripts/bake_selected_chair_textures.py -- \
    --resolution 2048 --output-dir baked_chair

Select only the parts belonging to one chair before saving the source file. If
nothing is selected, the script uses every visible mesh object in the scene.
The source objects are preserved; baking happens on joined duplicates.
"""

import argparse
import sys
from pathlib import Path

import bpy


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", type=int, default=2048)
    parser.add_argument("--output-dir", default="baked_chair")
    parser.add_argument("--margin", type=int, default=16)
    parser.add_argument("--dry-run", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def source_meshes():
    selected = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    meshes = selected or [
        obj for obj in bpy.context.scene.objects if obj.type == "MESH" and not obj.hide_render
    ]
    if not meshes:
        raise RuntimeError("No selected or visible mesh objects were found")
    return meshes


def duplicate_and_join(objects):
    bpy.ops.object.select_all(action="DESELECT")
    copies = []
    for source in objects:
        copy = source.copy()
        copy.data = source.data.copy()
        source.users_collection[0].objects.link(copy)
        copy.select_set(True)
        copies.append(copy)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.join()
    target = bpy.context.object
    target.name = "Baked_Chair"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return target


def unwrap(target):
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    if not target.data.uv_layers:
        target.data.uv_layers.new(name="BakedUV")
    target.data.uv_layers.active.name = "BakedUV"
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def ensure_materials(target):
    if not target.material_slots:
        material = bpy.data.materials.new("Bake Source")
        material.use_nodes = True
        target.data.materials.append(material)
    for slot in target.material_slots:
        if slot.material is None:
            slot.material = bpy.data.materials.new("Bake Source")
        slot.material.use_nodes = True


def image_target(target, name, resolution, colorspace):
    image = bpy.data.images.new(name, width=resolution, height=resolution, alpha=False)
    image.colorspace_settings.name = colorspace
    for slot in target.material_slots:
        nodes = slot.material.node_tree.nodes
        for node in nodes:
            node.select = False
        node = nodes.new("ShaderNodeTexImage")
        node.name = f"BAKE_TARGET_{name}"
        node.label = f"Bake target: {name}"
        node.image = image
        node.select = True
        nodes.active = node
    return image


def bake_map(target, bake_type, image, output, margin):
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    scene = bpy.context.scene
    scene.render.bake.margin = margin
    if bake_type == "DIFFUSE":
        scene.render.bake.use_pass_direct = False
        scene.render.bake.use_pass_indirect = False
        scene.render.bake.use_pass_color = True
    bpy.ops.object.bake(type=bake_type)
    image.filepath_raw = str(output)
    image.file_format = "PNG"
    image.save()
    print(f"Baked {bake_type}: {output}")


def baked_material(target, images):
    material = bpy.data.materials.new("Chair_Baked_Material")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")

    color = nodes.new("ShaderNodeTexImage")
    color.name = "Baked Base Color"
    color.image = images["BaseColor"]
    links.new(color.outputs["Color"], bsdf.inputs["Base Color"])

    rough = nodes.new("ShaderNodeTexImage")
    rough.name = "Baked Roughness"
    rough.image = images["Roughness"]
    links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])

    normal_tex = nodes.new("ShaderNodeTexImage")
    normal_tex.name = "Baked Normal"
    normal_tex.image = images["Normal"]
    normal = nodes.new("ShaderNodeNormalMap")
    links.new(normal_tex.outputs["Color"], normal.inputs["Color"])
    links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])

    target.data.materials.clear()
    target.data.materials.append(material)


def main():
    args = arguments()
    if args.resolution < 64 or args.resolution > 16384:
        raise ValueError("Resolution must be between 64 and 16384")
    sources = source_meshes()
    print("Source meshes:", ", ".join(obj.name for obj in sources))
    if args.dry_run:
        print(f"Dry run: would bake {len(sources)} meshes at {args.resolution}px")
        return

    blend_dir = Path(bpy.data.filepath).resolve().parent if bpy.data.filepath else Path.cwd()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = blend_dir / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    target = duplicate_and_join(sources)
    unwrap(target)
    ensure_materials(target)
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.device = "CPU"

    specs = {
        "BaseColor": ("DIFFUSE", "sRGB"),
        "Roughness": ("ROUGHNESS", "Non-Color"),
        "Normal": ("NORMAL", "Non-Color"),
        "AO": ("AO", "Non-Color"),
    }
    images = {}
    for name, (bake_type, colorspace) in specs.items():
        image = image_target(target, f"Chair_{name}", args.resolution, colorspace)
        bake_map(target, bake_type, image, output_dir / f"Chair_{name}.png", args.margin)
        images[name] = image

    baked_material(target, images)
    for source in sources:
        source.hide_render = True
        source.hide_set(True)
    output_blend = output_dir / "chair_baked.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    print(f"Saved baked chair: {output_blend}")


if __name__ == "__main__":
    main()
