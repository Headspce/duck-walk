#!/usr/bin/env python3
"""
convert_duck.py -- durable glTF -> Unity-ready FBX conversion for the Duck Walk game.

Reads:  ~/workspace/duck_walk/extracted/scene.gltf (+ textures)
Writes: Assets/Duck/duck.fbx        (FBX 7.4 binary, baked walk animation, embedded texture)
        Assets/Duck/ground.fbx      (20x20m ground slab, top at y=0 in Unity)
        Assets/Duck/duck_basecolor.png (texture copied alongside, per project spec)
        Tools/duck_rig.json         (bone rest transforms / AABB / action range for scene generation)

Pipeline:
  1. Import the glTF, keep only the duck mesh + its armature, delete everything else.
  2. Neutralise wrapper transforms (bake into data), verify the armature modifier.
  3. Rotate the duck to face Blender +Y (= Unity +Z after FBX axis conversion),
     snapped to 90 degrees, and flatten any root motion on _rootJoint.
  4. Drop the duck so its lowest animated foot point sits at z=0 (Unity y=0).
  5. Export binary FBX with baked animation; build a grey ground slab; copy texture.

Run headless:
  blender --background --python Tools/convert_duck.py
"""
import bpy
import math
import json
import os
import shutil
from mathutils import Vector, Matrix

HOME = os.path.expanduser("~")
WS = os.path.join(HOME, "workspace")
SRC_GLTF = os.path.join(WS, "duck_walk", "extracted", "scene.gltf")
SRC_TEX = os.path.join(WS, "duck_walk", "extracted", "textures", "Material_0_baseColor.png")
OUT_DIR = os.path.join(WS, "unity-duck-game")
DUCK_FBX = os.path.join(OUT_DIR, "Assets", "Duck", "duck.fbx")
GROUND_FBX = os.path.join(OUT_DIR, "Assets", "Duck", "ground.fbx")
TEX_DST = os.path.join(OUT_DIR, "Assets", "Duck", "duck_basecolor.png")
RIG_JSON = os.path.join(OUT_DIR, "Tools", "duck_rig.json")

WALK_ACTION = "walk"
ROOT_BONE = "_rootJoint"
BEAK_BONE = "Bone01_032_033"


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def bake_world_transform(obj):
    """Bake the object's full world transform into its data, leaving it at identity.

    Does NOT use parent_clear (which mishandles parent_inverse): the world
    matrix is captured explicitly, the object is unparented, the matrix is
    re-applied, then baked with transform_apply.
    """
    mw = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = mw
    select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def main():
    for p in (os.path.dirname(DUCK_FBX), os.path.dirname(RIG_JSON)):
        os.makedirs(p, exist_ok=True)

    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC_GLTF)
    bpy.context.view_layer.update()

    # ---- isolate the duck mesh + armature ---------------------------------
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name != "Icosphere"]
    duck_mesh, arm = None, None
    for m in meshes:
        p = m.parent
        while p is not None:
            if p.type == "ARMATURE":
                duck_mesh, arm = m, p
                break
            p = p.parent
        if duck_mesh:
            break
    if duck_mesh is None or arm is None:
        raise RuntimeError("Could not find armature-deformed duck mesh in glTF")
    arm.name = "Armature"
    duck_mesh.name = "DuckMesh"
    print(f"kept mesh={duck_mesh.name} armature={arm.name}")

    # ---- armature modifier -------------------------------------------------
    if not any(m.type == "ARMATURE" and m.object == arm for m in duck_mesh.modifiers):
        mod = duck_mesh.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        print("added missing armature modifier")
    for m in duck_mesh.modifiers:
        if m.type == "ARMATURE":
            m.use_vertex_groups = True

    # ---- neutralise wrapper transforms -------------------------------------
    # The glTF nests the duck under wrapper nodes (0.802 * 0.01 unit scale plus
    # a small offset). Bake the FULL world matrix into the data now, while the
    # wrappers still exist; deleting them first would silently drop their
    # transforms (and parent_clear mishandles parent_inverse, so we do it
    # manually via bake_world_transform).
    wrap_scale = arm.matrix_world.to_scale()
    assert abs(wrap_scale.x - wrap_scale.y) < 1e-6 and abs(wrap_scale.x - wrap_scale.z) < 1e-6, \
        f"non-uniform wrapper scale {tuple(wrap_scale)}"
    unit = wrap_scale.x
    print(f"wrapper world scale={unit}, loc={tuple(round(v, 3) for v in arm.matrix_world.translation)}")
    bake_world_transform(duck_mesh)
    bake_world_transform(arm)
    # Now safe to drop the wrappers.
    for o in [o for o in bpy.data.objects if o not in (duck_mesh, arm)]:
        bpy.data.objects.remove(o, do_unlink=True)

    # The baked scale shrinks the rest pose but the walk action's location
    # fcurves are still in the old units -> scale them to match.
    act = bpy.data.actions.get(WALK_ACTION)
    if act is None:
        raise RuntimeError(f"action '{WALK_ACTION}' not found")
    if abs(unit - 1.0) > 1e-9:
        n = 0
        for layer in act.layers:
            for strip in layer.strips:
                for slot in act.slots:
                    try:
                        bag = strip.channelbag(slot)
                    except Exception:
                        continue
                    for fc in bag.fcurves:
                        if fc.data_path.startswith('pose.bones[') and fc.data_path.endswith('.location'):
                            for kp in fc.keyframe_points:
                                kp.co[1] *= unit
                                kp.handle_left[1] *= unit
                                kp.handle_right[1] *= unit
                            fc.update()
                            n += 1
        for pb in arm.pose.bones:
            pb.location *= unit
        print(f"scaled {n} location fcurves by {unit}")

    # ---- action ------------------------------------------------------------
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    f_start, f_end = int(act.frame_range[0]), int(act.frame_range[1])
    print(f"action '{act.name}' frames {f_start}..{f_end}")

    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = f_start, f_end

    # ---- root motion check on _rootJoint ------------------------------------
    def root_pos(frame):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        arm_e = arm.evaluated_get(dg)
        pb = arm_e.pose.bones.get(ROOT_BONE)
        return (arm.matrix_world @ pb.matrix).translation.copy()

    p0, p1 = root_pos(f_start), root_pos(f_end)
    drift = (p1 - p0).copy()
    drift.z = 0.0
    has_root_motion = drift.length > 0.01
    print(f"root drift over cycle: {drift.length:.4f} -> "
          f"{'FLATTENING' if has_root_motion else 'in place, ok'}")
    if has_root_motion:
        # Flatten horizontal root motion via the action's fcurves (Blender 5 slot API).
        n = 0
        for layer in act.layers:
            for strip in layer.strips:
                for slot in act.slots:
                    try:
                        bag = strip.channelbag(slot)
                    except Exception:
                        continue
                    for fc in bag.fcurves:
                        if fc.data_path == f'pose.bones["{ROOT_BONE}"].location' \
                                and fc.array_index in (0, 1):
                            v0 = fc.evaluate(f_start)
                            for kp in fc.keyframe_points:
                                kp.co[1] = v0
                                kp.handle_left[1] = v0
                                kp.handle_right[1] = v0
                            fc.update()
                            n += 1
        print(f"flattened {n} root-motion fcurves")

    # ---- face Blender +Y (= Unity +Z), snapped to 90 deg --------------------
    beak = arm.data.bones.get(BEAK_BONE)
    if beak is None:
        raise RuntimeError(f"beak bone '{BEAK_BONE}' not found")
    d = beak.tail_local - beak.head_local
    ang = math.atan2(d.x, d.y)  # angle from +Y
    snap = round(ang / (math.pi / 2)) * (math.pi / 2)
    arm.rotation_euler[2] = snap
    duck_mesh.rotation_euler[2] = snap
    print(f"beak dir=({d.x:.2f},{d.y:.2f}) facing angle={math.degrees(ang):.1f}deg "
          f"-> snapped {math.degrees(snap):.0f}deg")

    # ---- feet on the ground (sample across the walk cycle) ------------------
    bpy.context.view_layer.update()
    gmin = None
    for f in range(f_start, f_end + 1, max(1, (f_end - f_start) // 4)):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        me = arm.evaluated_get(dg)  # noqa: F841 (keep pattern explicit below)
        obj_e = duck_mesh.evaluated_get(dg)
        tmp = obj_e.to_mesh()
        m2w = obj_e.matrix_world
        for v in tmp.vertices:
            w = m2w @ v.co
            gmin = w.z if gmin is None else min(gmin, w.z)
        obj_e.to_mesh_clear()
    dz = -gmin
    arm.location[2] += dz
    duck_mesh.location[2] += dz
    print(f"lowest foot z={gmin:.4f} -> lifted by {dz:.4f}")

    # ---- bake the facing/ground rigid transform into the data ---------------
    for o in (arm, duck_mesh):
        select_only(o)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print("baked facing+ground transform; objects back at identity")

    # ---- export duck.fbx ----------------------------------------------------
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    duck_mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(
        filepath=DUCK_FBX,
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        use_mesh_modifiers=True,
        bake_anim=True,
        bake_anim_use_all_actions=False,
        bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        add_leaf_bones=False,
        embed_textures=True,
        path_mode="COPY",
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
    )
    print(f"wrote {DUCK_FBX} ({os.path.getsize(DUCK_FBX)} bytes)")

    # ---- rig sidecar for Unity scene generation -----------------------------
    # Blender (x,y,z) -> Unity (x,z,y); quat (x,y,z,w) -> (x,z,y,w).
    bones = []
    for b in arm.data.bones:
        M = b.matrix_local if b.parent is None \
            else b.parent.matrix_local.inverted() @ b.matrix_local
        t = M.translation
        q = M.to_quaternion()
        bones.append({
            "name": b.name,
            "parent": b.parent.name if b.parent else None,
            "pos": [t.x, t.z, t.y],
            "rot": [q.x, q.z, q.y, q.w],
        })

    scene.frame_set(f_start)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    obj_e = duck_mesh.evaluated_get(dg)
    tmp = obj_e.to_mesh()
    m2w = obj_e.matrix_world
    ws = [m2w @ v.co for v in tmp.vertices]
    obj_e.to_mesh_clear()
    xs = [v.x for v in ws]; ys = [v.z for v in ws]; zs = [v.y for v in ws]
    cx, cy, cz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2
    ex, ey, ez = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2, (max(zs) - min(zs)) / 2

    rig = {
        "mesh_name": duck_mesh.name,
        "armature_name": arm.name,
        "bone_count": len(bones),
        "bones": bones,  # armature order == FBX cluster order == Unity bone order
        "root_bone": ROOT_BONE,
        "aabb": {"center": [cx, cy, cz], "extent": [ex, ey, ez]},
        "action": {"name": act.name, "frame_start": f_start, "frame_end": f_end},
        "facing_snap_deg": math.degrees(snap),
        "root_motion_flattened": has_root_motion,
        "fbx": os.path.basename(DUCK_FBX),
    }
    with open(RIG_JSON, "w") as fh:
        json.dump(rig, fh, indent=1)
    print(f"wrote {RIG_JSON}: {len(bones)} bones, action {f_start}..{f_end}")

    # ---- ground slab ---------------------------------------------------------
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, -0.1))
    g = bpy.context.active_object
    g.name = "Ground"
    g.scale = (10, 10, 0.1)
    select_only(g)
    bpy.ops.object.transform_apply(scale=True)
    mat = bpy.data.materials.new("Ground")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.78, 0.78, 0.8, 1.0)
    g.data.materials.append(mat)
    select_only(g)
    bpy.ops.export_scene.fbx(
        filepath=GROUND_FBX,
        use_selection=True,
        object_types={"MESH"},
        bake_anim=False,
        axis_forward="-Z",
        axis_up="Y",
    )
    print(f"wrote {GROUND_FBX} ({os.path.getsize(GROUND_FBX)} bytes)")

    # ---- texture alongside ----------------------------------------------------
    shutil.copyfile(SRC_TEX, TEX_DST)
    print(f"copied texture -> {TEX_DST} ({os.path.getsize(TEX_DST)} bytes)")


if __name__ == "__main__":
    main()
