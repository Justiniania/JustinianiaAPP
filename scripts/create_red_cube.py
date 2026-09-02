"""Create a Blender scene with one red cube."""

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "red_cube_scene.blend"

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
cube = bpy.context.object
cube.name = "Red Cube"

material = bpy.data.materials.new("Red Material")
material.diffuse_color = (1.0, 0.0, 0.0, 1.0)
material.use_nodes = True
principled = material.node_tree.nodes.get("Principled BSDF")
principled.inputs["Base Color"].default_value = (1.0, 0.0, 0.0, 1.0)
principled.inputs["Roughness"].default_value = 0.4
cube.data.materials.append(material)

bpy.context.scene.unit_settings.system = "METRIC"
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
