#!/usr/bin/env python3
"""
generate_project.py -- scaffolds the Unity project around the converted duck FBX.

Reads:  Tools/duck_rig.json   (bone rest transforms, AABB, action range)
        Tools/convert_duck.py outputs (Assets/Duck/duck.fbx, ground.fbx, duck_basecolor.png)
Writes: every other project file (scene YAML, .meta files, scripts,
        ProjectSettings, Packages, workflows, README, .gitignore).

Run:  python3 Tools/generate_project.py
Re-runs reuse stable GUIDs from Tools/guids.json.
"""
import json
import math
import os
import uuid

HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "workspace", "unity-duck-game")
TOOLS = os.path.join(PROJ, "Tools")
RIG_JSON = os.path.join(TOOLS, "duck_rig.json")
GUIDS_JSON = os.path.join(TOOLS, "guids.json")

UNITY_VERSION = "2022.3.76f1"
UNITY_REVISION = "ca34391b97"
COMPANY = "progranimator"
PRODUCT = "Duck Walk"
PKG = "com.progranimation.duckwalk"

ATTRIBUTION = ("This work is based on \u201cDuck_Walk (Free)\u201d by Nyilonelycompany, "
               "licensed under CC-BY-4.0.")


# ----------------------------------------------------------------------------
# GUIDs (stable across re-runs)
# ----------------------------------------------------------------------------
GUID_KEYS = ["duck_fbx", "ground_fbx", "duck_tex", "scene", "duckwalker",
             "credits", "product"]
if os.path.exists(GUIDS_JSON):
    with open(GUIDS_JSON) as fh:
        GUIDS = json.load(fh)
else:
    GUIDS = {k: uuid.uuid4().hex for k in GUID_KEYS}
    with open(GUIDS_JSON, "w") as fh:
        json.dump(GUIDS, fh, indent=1)


def w(path, content):
    full = os.path.join(PROJ, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as fh:
        fh.write(content)
    print("wrote", path)


# ----------------------------------------------------------------------------
# math helpers
# ----------------------------------------------------------------------------
def _norm(v):
    l = math.sqrt(sum(c * c for c in v))
    return tuple(c / l for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def look_rotation(fwd, up=(0, 1, 0)):
    """Quaternion rotating +Z to fwd (Unity camera/light convention)."""
    f = _norm(fwd)
    r = _norm(_cross(up, f))
    u = _cross(f, r)
    # columns r,u,f
    m = [[r[0], u[0], f[0]],
         [r[1], u[1], f[1]],
         [r[2], u[2], f[2]]]
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        qw, qx, qy, qz = 0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        qw, qx, qy, qz = (m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        qw, qx, qy, qz = (m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        qw, qx, qy, qz = (m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s
    return (qx, qy, qz, qw)


def qstr(q):
    q = tuple(q)
    return "{x: %.6f, y: %.6f, z: %.6f, w: %.6f}" % q


def vstr(v):
    return "{x: %.4f, y: %.4f, z: %.4f}" % tuple(v)


# ----------------------------------------------------------------------------
# .meta files
# ----------------------------------------------------------------------------
def meta_fbx(guid):
    # m_AnimationType: 1 = Legacy (None=0, Legacy=1, Generic=2, Humanoid=3).
    # DuckWalker.cs additionally forces clip.legacy at runtime as a safety net.
    return (f"fileFormatVersion: 2\nguid: {guid}\n"
            "ModelImporter:\n"
            "  serializedVersion: 26\n"
            "  m_AnimationType: 1\n")


def meta_tex(guid):
    return (f"fileFormatVersion: 2\nguid: {guid}\n"
            "TextureImporter:\n"
            "  serializedVersion: 10\n")


def meta_script(guid):
    return (f"fileFormatVersion: 2\nguid: {guid}\n"
            "MonoImporter:\n"
            "  externalObjects: {}\n"
            "  serializedVersion: 2\n"
            "  defaultReferences: []\n"
            "  executionOrder: 0\n"
            "  icon: {instanceID: 0}\n"
            "  userData: \n"
            "  assetBundleName: \n"
            "  assetBundleVariant: \n")


def meta_scene(guid):
    return f"fileFormatVersion: 2\nguid: {guid}\n"


# ----------------------------------------------------------------------------
# C# scripts
# ----------------------------------------------------------------------------
DUCKWALKER_CS = """using UnityEngine;

// Moves the duck across the screen and wraps it around.
// Also guarantees the imported walk clip loops: the FBX .meta requests the
// Legacy animation type, and as a safety net we force the legacy flag and
// loop wrap mode here in case the .meta was not honoured on import.
[RequireComponent(typeof(Animation))]
public class DuckWalker : MonoBehaviour
{
    public float speed = 1.2f;
    public float minX = -5f;
    public float maxX = 5f;

    private Animation anim;

    void Start()
    {
        anim = GetComponent<Animation>();
        foreach (AnimationState s in anim)
        {
            if (s.clip != null)
            {
                s.clip.legacy = true;   // safety net for the .meta's Legacy flag
                s.wrapMode = WrapMode.Loop;
            }
        }
        anim.wrapMode = WrapMode.Loop;
        if (anim.clip != null && !anim.isPlaying)
            anim.Play();
    }

    void Update()
    {
        transform.position += Vector3.right * speed * Time.deltaTime;
        if (transform.position.x > maxX)
        {
            Vector3 p = transform.position;
            p.x = minX;
            transform.position = p;
        }
        if (anim != null && anim.clip != null && !anim.isPlaying)
            anim.Play();
    }
}
"""

CREDITS_CS = """using UnityEngine;

// In-game attribution for the CC-BY-4.0 duck model (OnGUI: no UI package needed).
public class Credits : MonoBehaviour
{
    void OnGUI()
    {
        GUI.Label(new Rect(12, Screen.height - 34, Screen.width - 24, 28),
            "Duck_Walk (Free) by Nyilonelycompany, licensed under CC-BY-4.0");
    }
}
"""


# ----------------------------------------------------------------------------
# scene
# ----------------------------------------------------------------------------
def game_object(fid, name, components, tag="Untagged", layer=0):
    comps = "\n".join(f"  - component: {{fileID: {c}}}" for c in components)
    return (f"--- !u!1 &{fid}\nGameObject:\n"
            "  m_ObjectHideFlags: 0\n"
            "  m_CorrespondingSourceObject: {fileID: 0}\n"
            "  m_PrefabInstance: {fileID: 0}\n"
            "  m_PrefabAsset: {fileID: 0}\n"
            "  serializedVersion: 6\n"
            "  m_Component:\n" + comps + "\n"
            f"  m_Layer: {layer}\n"
            f"  m_Name: {name}\n"
            f"  m_TagString: {tag}\n"
            "  m_Icon: {fileID: 0}\n"
            "  m_NavMeshLayer: 0\n"
            "  m_StaticEditorFlags: 0\n"
            "  m_IsActive: 1\n")


def transform(fid, go, pos, rot, children=(), father=0):
    ch = "\n".join(f"  - {c}" for c in children)
    ch_block = ("  m_Children:\n" + ch + "\n") if children else "  m_Children: []\n"
    return (f"--- !u!4 &{fid}\nTransform:\n"
            "  m_ObjectHideFlags: 0\n"
            "  m_CorrespondingSourceObject: {fileID: 0}\n"
            "  m_PrefabInstance: {fileID: 0}\n"
            "  m_PrefabAsset: {fileID: 0}\n"
            f"  m_GameObject: {{fileID: {go}}}\n"
            "  serializedVersion: 10\n"
            f"  m_LocalRotation: {qstr(rot)}\n"
            f"  m_LocalPosition: {vstr(pos)}\n"
            "  m_LocalScale: {x: 1, y: 1, z: 1}\n"
            "  m_ConstrainProportionsScale: 0\n" + ch_block +
            f"  m_Father: {{fileID: {father}}}\n")


def mono_behaviour(fid, go, guid, classname, fields=""):
    return (f"--- !u!114 &{fid}\nMonoBehaviour:\n"
            "  m_ObjectHideFlags: 0\n"
            "  m_CorrespondingSourceObject: {fileID: 0}\n"
            "  m_PrefabInstance: {fileID: 0}\n"
            "  m_PrefabAsset: {fileID: 0}\n"
            f"  m_GameObject: {{fileID: {go}}}\n"
            "  m_Enabled: 1\n"
            "  m_EditorHideFlags: 0\n"
            f"  m_Script: {{fileID: 11500000, guid: {guid}, type: 3}}\n"
            f"  m_Name: {classname}\n"
            "  m_EditorClassIdentifier: \n" + fields)


def build_scene(rig):
    bones = rig["bones"]
    n = len(bones)
    idx = {b["name"]: i for i, b in enumerate(bones)}
    go_of = [100 + i for i in range(n)]
    tr_of = [200 + i for i in range(n)]
    kids = {i: [] for i in range(n)}
    root_i = None
    for i, b in enumerate(bones):
        p = b["parent"]
        if p is None:
            root_i = i
        else:
            kids[idx[p]].append(tr_of[i])

    DUCK = GUIDS["duck_fbx"]
    parts = ["%YAML 1.1", "%TAG !u! tag:unity3d.com,2011:"]

    # -- settings boilerplate -------------------------------------------------
    parts.append("""--- !u!29 &9002
OcclusionCullingSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 2
  m_OcclusionBakeSettings:
    smallestOccluder: 5
    smallestHole: 0.25
    backfaceThreshold: 100
  m_SceneGUID: 00000000000000000000000000000000
  m_OcclusionCullingData: {fileID: 0}
--- !u!104 &9001
RenderSettings:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  serializedVersion: 9
  m_Fog: 0
  m_FogColor: {r: 0.5, g: 0.5, b: 0.5, a: 1}
  m_FogMode: 3
  m_FogDensity: 0.01
  m_LinearFogStart: 0
  m_LinearFogEnd: 300
  m_AmbientSkyColor: {r: 0.212, g: 0.227, b: 0.259, a: 1}
  m_AmbientEquatorColor: {r: 0.114, g: 0.125, b: 0.133, a: 1}
  m_AmbientGroundColor: {r: 0.047, g: 0.043, b: 0.035, a: 1}
  m_AmbientIntensity: 1
  m_AmbientMode: 0
  m_SubtractiveShadowColor: {r: 0.42, g: 0.478, b: 0.627, a: 1}
  m_SkyboxMaterial: {fileID: 0}
  m_HaloStrength: 0.5
  m_FlareStrength: 1
  m_FlareFadeSpeed: 3
  m_HaloTexture: {fileID: 0}
  m_SpotCookie: {fileID: 0}
  m_DefaultReflectionMode: 0
  m_DefaultReflectionResolution: 128
  m_ReflectionBounces: 1
  m_ReflectionIntensity: 1
  m_CustomReflection: {fileID: 0}
  m_Sun: {fileID: 0}
  m_IndirectSpecularColor: {r: 0, g: 0, b: 0, a: 1}
  m_UseRadianceAmbientProbe: 0
--- !u!157 &9003
LightmapSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 12
  m_GIWorkflowMode: 1
  m_GISettings:
    serializedVersion: 2
    m_BounceScale: 1
    m_IndirectOutputScale: 1
    m_AlbedoBoost: 1
    m_EnvironmentLighting: 1
    m_EnableBakedLightmaps: 0
    m_EnableRealtimeLightmaps: 0
  m_LightingDataAsset: {fileID: 0}
  m_LightingSettings: {fileID: 0}
--- !u!196 &9004
NavMeshSettings:
  serializedVersion: 2
  m_ObjectHideFlags: 0
  m_BuildSettings:
    serializedVersion: 3
    agentTypeID: 0
    agentRadius: 0.5
    agentHeight: 2
    agentSlope: 45
    agentClimb: 0.4
    ledgeDropHeight: 0
    maxJumpAcrossDistance: 0
    minRegionArea: 2
    manualCellSize: 0
    cellSize: 0.16666667
    manualTileSize: 0
    tileSize: 256
    accuratePlacement: 0
    debug:
      m_Flags: 0
  m_NavMeshData: {fileID: 0}""")

    # -- duck root ------------------------------------------------------------
    q_duck = (0.0, math.sin(math.pi / 4), 0.0, math.cos(math.pi / 4))  # face +X
    parts.append(game_object(1, "Duck", [2, 3, 4, 5]))
    parts.append(transform(2, 1, (-5, 0, 0), q_duck, children=[11, 51]))
    clip_ref = f"{{fileID: 7400000, guid: {DUCK}, type: 3}}"
    parts.append(f"""--- !u!95 &3
Animation:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 1}}
  m_Enabled: 1
  serializedVersion: 5
  m_PlayAutomatically: 1
  m_AnimatePhysics: 0
  m_CullingType: 0
  m_Clip: {clip_ref}
  m_Animations:
  - {clip_ref}""")
    parts.append(mono_behaviour(4, 1, GUIDS["duckwalker"], "DuckWalker",
                                "  speed: 1.2\n  minX: -5\n  maxX: 5\n"))
    parts.append(mono_behaviour(5, 1, GUIDS["credits"], "Credits"))

    # -- armature + bones ------------------------------------------------------
    parts.append(game_object(10, "Armature", [11]))
    parts.append(transform(11, 10, (0, 0, 0), (0, 0, 0, 1), children=[tr_of[root_i]], father=2))
    for i, b in enumerate(bones):
        parts.append(game_object(go_of[i], b["name"], [tr_of[i]]))
        father = 11 if b["parent"] is None else tr_of[idx[b["parent"]]]
        parts.append(transform(tr_of[i], go_of[i], b["pos"], b["rot"],
                               children=kids[i], father=father))

    # -- skinned mesh -----------------------------------------------------------
    parts.append(game_object(50, "DuckMesh", [51, 52]))
    parts.append(transform(51, 50, (0, 0, 0), (0, 0, 0, 1), father=2))
    bones_yaml = "\n".join(f"  - {{fileID: {t}}}" for t in tr_of)
    c = rig["aabb"]["center"]
    e = rig["aabb"]["extent"]
    parts.append(f"""--- !u!137 &52
SkinnedMeshRenderer:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 50}}
  m_Enabled: 1
  serializedVersion: 2
  m_CastShadows: 1
  m_ReceiveShadows: 1
  m_DynamicOccludee: 1
  m_StaticShadowCaster: 0
  m_MotionVectors: 1
  m_LightProbeUsage: 1
  m_ReflectionProbeUsage: 1
  m_RayTracingMode: 2
  m_RayTraceProcedural: 0
  m_RenderingLayerMask: 1
  m_Materials:
  - {{fileID: 2100000, guid: {DUCK}, type: 3}}
  m_StaticBatchInfo:
    firstSubMesh: 0
    subMeshCount: 1
  m_AABB:
    m_Center: {{x: {c[0]:.4f}, y: {c[1]:.4f}, z: {c[2]:.4f}}}
    m_Extent: {{x: {e[0]:.4f}, y: {e[1]:.4f}, z: {e[2]:.4f}}}
  m_DirtyAABB: 0
  m_UpdateWhenOffscreen: 1
  m_SkinnedMotionVectors: 1
  m_Mesh: {{fileID: 4300000, guid: {DUCK}, type: 3}}
  m_Bones:
{bones_yaml}
  m_BlendShapeWeights: []
  m_RootBone: {{fileID: {tr_of[root_i]}}}""")

    # -- camera ------------------------------------------------------------------
    q_cam = look_rotation((0, 0.35 - 1.15, 3.0))
    parts.append(game_object(60, "Main Camera", [61, 62], tag="MainCamera"))
    parts.append(transform(61, 60, (0, 1.15, -3.0), q_cam))
    parts.append("""--- !u!20 &62
Camera:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 60}
  m_Enabled: 1
  serializedVersion: 3
  m_ClearFlags: 2
  m_BackGroundColor: {r: 0.55, g: 0.78, b: 0.95, a: 1}
  m_projection: 0
  m_GateFitMode: 2
  m_FOVAxisMode: 0
  m_SensorSize: {x: 36, y: 24}
  m_LensShift: {x: 0, y: 0}
  m_FocalLength: 50
  m_NormalizedViewPortRect:
    serializedVersion: 2
    x: 0
    y: 0
    width: 1
    height: 1
  near clip plane: 0.1
  far clip plane: 100
  m_FieldOfView: 40
  m_orthographic: 0
  m_OrthographicSize: 5
  m_Depth: -1
  m_CullingMask:
    serializedVersion: 2
    m_Bits: 4294967295
  m_RenderingPath: -1
  m_TargetTexture: {fileID: 0}
  m_TargetDisplay: 0
  m_TargetEye: 3
  m_HDR: 1
  m_AllowMSAA: 1
  m_AllowDynamicResolution: 0
  m_ForceIntoRT: 0
  m_OcclusionCulling: 1
  m_StereoConvergence: 10
  m_StereoSeparation: 0.022""")

    # -- directional light ---------------------------------------------------------
    q_light = look_rotation((0.25, -1.0, 0.35))
    parts.append(game_object(70, "Directional Light", [71, 72]))
    parts.append(transform(71, 70, (0, 3, 0), q_light))
    parts.append("""--- !u!108 &72
Light:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 70}
  m_Enabled: 1
  serializedVersion: 10
  m_Type: 1
  m_Shape: 0
  m_Color: {r: 1, g: 0.9647059, b: 0.8745098, a: 1}
  m_Intensity: 1
  m_Range: 10
  m_SpotAngle: 30
  m_CookieSize: 10
  m_Shadows:
    m_Type: 2
    m_Resolution: -1
    m_CustomResolution: -1
    m_Strength: 1
    m_Bias: 0.05
    m_NormalBias: 0.4
    m_NearPlane: 0.2
  m_Cookie: {fileID: 0}
  m_DrawHalo: 0
  m_Flare: {fileID: 0}
  m_RenderMode: 0
  m_CullingMask:
    serializedVersion: 2
    m_Bits: 4294967295
  m_RenderingLayerMask: 1
  m_Lightmapping: 4
  m_BounceIntensity: 1""")

    # -- ground ---------------------------------------------------------------------
    G = GUIDS["ground_fbx"]
    parts.append(game_object(80, "Ground", [81, 82, 83]))
    parts.append(transform(81, 80, (0, 0, 0), (0, 0, 0, 1)))
    parts.append(f"""--- !u!33 &82
MeshFilter:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 80}}
  m_Enabled: 1
  serializedVersion: 3
  m_Mesh: {{fileID: 4300000, guid: {G}, type: 3}}""")
    parts.append(f"""--- !u!23 &83
MeshRenderer:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 80}}
  m_Enabled: 1
  serializedVersion: 2
  m_CastShadows: 0
  m_ReceiveShadows: 1
  m_DynamicOccludee: 1
  m_StaticShadowCaster: 0
  m_MotionVectors: 1
  m_LightProbeUsage: 1
  m_ReflectionProbeUsage: 1
  m_RayTracingMode: 2
  m_RayTraceProcedural: 0
  m_RenderingLayerMask: 1
  m_Materials:
  - {{fileID: 2100000, guid: {G}, type: 3}}
  m_StaticBatchInfo:
    firstSubMesh: 0
    subMeshCount: 1""")

    return "\n".join(parts) + "\n"


# ----------------------------------------------------------------------------
# project settings
# ----------------------------------------------------------------------------
PROJECT_SETTINGS = f"""%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!129 &1
PlayerSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 23
  productGUID: {GUIDS['product']}
  companyName: {COMPANY}
  productName: {PRODUCT}
  defaultScreenWidth: 1920
  defaultScreenHeight: 1080
  m_BundleVersion: 1.0
  applicationIdentifier:
    Android: {PKG}
    Standalone: {PKG}
  AndroidBundleVersionCode: 1
  AndroidMinSdkVersion: 24
  AndroidTargetSdkVersion: 34
  AndroidTargetArchitectures: 2
  scriptingBackend:
    Android: 1
  allowedAutorotateToPortrait: 0
  allowedAutorotateToPortraitUpsideDown: 0
  allowedAutorotateToLandscapeRight: 1
  allowedAutorotateToLandscapeLeft: 1
"""

PROJECT_VERSION = f"""m_EditorVersion: {UNITY_VERSION}
m_EditorVersionWithRevision: {UNITY_VERSION} ({UNITY_REVISION})
"""

EDITOR_BUILD_SETTINGS = f"""%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1045 &1
EditorBuildSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 2
  m_Scenes:
  - enabled: 1
    path: Assets/Scenes/Main.unity
    guid: {GUIDS['scene']}
  m_configObjects: {{}}
"""

MANIFEST = """{
  "dependencies": {}
}
"""

GITIGNORE = """# Unity
[Ll]ibrary/
[Tt]emp/
[Oo]bj/
[Bb]uild/
[Bb]uilds/
[Ll]ogs/
[Uu]ser[Ss]ettings/
[Mm]emoryCaptures/
*.apk
*.aab
# this repo's build output
build/
"""

BUILD_YML = """name: Build Android APK

on:
  workflow_dispatch:
  push:
    branches: [main]

jobs:
  build:
    name: Build DuckWalk APK
    runs-on: ubuntu-22.04
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Cache Unity Library
        uses: actions/cache@v4
        with:
          path: Library
          key: Library-Android-${{ hashFiles('Assets/**', 'Packages/**', 'ProjectSettings/**') }}
          restore-keys: |
            Library-Android-
            Library-

      - name: Build Unity project
        uses: game-ci/unity-builder@v4
        env:
          UNITY_LICENSE: ${{ secrets.UNITY_LICENSE }}
          UNITY_EMAIL: ${{ secrets.UNITY_EMAIL }}
          UNITY_PASSWORD: ${{ secrets.UNITY_PASSWORD }}
        with:
          targetPlatform: Android
          unityVersion: '2022.3.76f1'
          # v4's equivalent of "AAB off / APK on"
          androidExportType: androidPackage
          androidVersionCode: ${{ github.run_number }}
          buildName: DuckWalk

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: duckwalk-apk
          path: build/Android
"""

ACTIVATE_YML = """name: Request Unity activation file

on:
  workflow_dispatch:

jobs:
  activate:
    name: Generate .alf activation file
    runs-on: ubuntu-latest
    steps:
      - name: Request activation file
        id: getManualLicenseFile
        uses: game-ci/unity-request-activation-file@v2
        with:
          unityVersion: '2022.3.76f1'

      - name: Upload .alf artifact
        uses: actions/upload-artifact@v4
        with:
          name: manual-activation-file
          path: ${{ steps.getManualLicenseFile.outputs.filePath }}
"""

README = f"""# Duck Walk

A tiny Android game: an animated duck walks across the screen and wraps around.
Built with Unity {UNITY_VERSION}, built in CI with [game-ci](https://game.ci).

{ATTRIBUTION}

## Project layout

- `Assets/Duck/duck.fbx` — duck mesh + 45-bone rig + baked 20-frame walk cycle
  (converted from the glTF source with `Tools/convert_duck.py`)
- `Assets/Duck/ground.fbx` — ground slab
- `Assets/Scenes/Main.unity` — duck (legacy `Animation` component, walk on loop),
  ground, directional light, camera, `DuckWalker` + `Credits` scripts
- `.github/workflows/build.yml` — CI build producing the APK
- `.github/workflows/activate.yml` — generates the Unity manual activation file

## Build the APK (GitHub Actions)

The project builds itself in the cloud — no local Unity install needed.

1. Create a repo (e.g. `github.com/progranimation/duck-walk`) and push this project
   to the `main` branch.
2. Activate Unity for CI (one-time setup):
   1. Run the **Request Unity activation file** workflow (Actions tab).
   2. Download the `.alf` artifact it uploads.
   3. While signed into your Unity ID, upload the `.alf` at
      <https://license.unity3d.com/manual> and download the resulting license.
   4. Save the **contents of the license file** as a repository secret named
      `UNITY_LICENSE` (Settings → Secrets and variables → Actions).
3. Run the **Build Android APK** workflow (or just push to `main`).
4. Download the `duckwalk-apk` artifact — inside is `DuckWalk.apk`, ready to
   install on an ARM64 Android device (Android 7.0+, API 24+).

## Notes

- Build config: Unity {UNITY_VERSION}, IL2CPP, ARM64 only, min API 24,
  target API 34, `androidVersionCode` = the GitHub run number, APK output.
- The duck model source (`duck_walk_free.zip`) is not in this repo; the
  conversion script `Tools/convert_duck.py` documents the full glTF → FBX
  pipeline for reproducibility.
"""


def main():
    with open(RIG_JSON) as fh:
        rig = json.load(fh)

    # scripts
    w("Assets/Scripts/DuckWalker.cs", DUCKWALKER_CS)
    w("Assets/Scripts/DuckWalker.cs.meta", meta_script(GUIDS["duckwalker"]))
    w("Assets/Scripts/Credits.cs", CREDITS_CS)
    w("Assets/Scripts/Credits.cs.meta", meta_script(GUIDS["credits"]))

    # art assets' .meta files (fbx/png already produced by convert_duck.py)
    w("Assets/Duck/duck.fbx.meta", meta_fbx(GUIDS["duck_fbx"]))
    w("Assets/Duck/ground.fbx.meta", meta_fbx(GUIDS["ground_fbx"]))
    w("Assets/Duck/duck_basecolor.png.meta", meta_tex(GUIDS["duck_tex"]))

    # scene
    w("Assets/Scenes/Main.unity", build_scene(rig))
    w("Assets/Scenes/Main.unity.meta", meta_scene(GUIDS["scene"]))

    # project settings / packages
    w("ProjectSettings/ProjectSettings.asset", PROJECT_SETTINGS)
    w("ProjectSettings/ProjectVersion.txt", PROJECT_VERSION)
    w("ProjectSettings/EditorBuildSettings.asset", EDITOR_BUILD_SETTINGS)
    w("Packages/manifest.json", MANIFEST)

    # repo plumbing
    w(".github/workflows/build.yml", BUILD_YML)
    w(".github/workflows/activate.yml", ACTIVATE_YML)
    w(".gitignore", GITIGNORE)
    w("README.md", README)
    print("done.")


if __name__ == "__main__":
    main()
