#!/usr/bin/env python3
"""Verify duck.fbx / ground.fbx re-import cleanly with animation intact."""
import bpy, os, sys

HOME = os.path.expanduser("~")
DUCK = os.path.join(HOME, "workspace", "unity-duck-game", "Assets", "Duck", "duck.fbx")
GROUND = os.path.join(HOME, "workspace", "unity-duck-game", "Assets", "Duck", "ground.fbx")

ok = True

def check(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        ok = False

# ---- duck ----
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=DUCK)
arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
check(len(arms) == 1, f"exactly 1 armature (got {len(arms)})")
check(len(meshes) == 1, f"exactly 1 mesh (got {len(meshes)})")
arm, mesh = arms[0], meshes[0]
print(f"mesh name: {mesh.name}  verts: {len(mesh.data.vertices)}")
check(len(arm.data.bones) == 45, f"45 bones (got {len(arm.data.bones)})")
check(any(m.type == "ARMATURE" for m in mesh.modifiers), "mesh has armature modifier")
acts = [(a.name, tuple(a.frame_range)) for a in bpy.data.actions]
print("actions:", acts)
anim_acts = [a for a in acts if a[1][1] - a[1][0] > 1]
check(len(anim_acts) >= 1, f"at least one multi-frame action (got {anim_acts})")
# world-space sanity: duck near origin, POSED feet ~0 (the walk clip plays always)
ws = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
check(max(abs(v.x) for v in ws) < 3 and max(abs(v.y) for v in ws) < 3, "duck near origin")
scene = bpy.context.scene
gmin = None
for f in range(1, 21, 5):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    oe = mesh.evaluated_get(dg)
    tmp = oe.to_mesh()
    m2w = oe.matrix_world
    for v in tmp.vertices:
        z = (m2w @ v.co).z
        gmin = z if gmin is None else min(gmin, z)
    oe.to_mesh_clear()
check(gmin is not None and abs(gmin) < 0.05, f"posed feet near z=0 (min z={gmin:.3f})")

# ---- ground ----
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=GROUND)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
check(len(meshes) == 1, f"ground: 1 mesh (got {len(meshes)})")
if meshes:
    g = meshes[0]
    ws = [g.matrix_world @ v.co for v in g.data.vertices]
    top = max(v.z for v in ws)
    check(abs(top) < 0.01, f"ground top at z=0 (got {top:.3f})")
    check(len(g.data.materials) == 1, "ground has 1 material")

print("ALL OK" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
