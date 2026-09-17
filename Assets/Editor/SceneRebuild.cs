using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// Rebuilds Assets/Scenes/Main.unity programmatically from the actual imported
/// assets, so every renderer reference points at Unity's real imported mesh /
/// material / clip subassets instead of hand-typed file IDs in the scene YAML.
/// Also logs every subasset (type, name, local file ID) for both FBX files so
/// the build log shows exactly what Unity imported.
/// Invoked by BuildScript before BuildPipeline.BuildPlayer.
/// </summary>
public static class SceneRebuild
{
    private const string DuckFbx = "Assets/Duck/duck.fbx";
    private const string ScenePath = "Assets/Scenes/Main.unity";

    public static void Rebuild()
    {
        LogImportedSubassets(DuckFbx);

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // --- Duck: instantiate the real imported model prefab. ---
        var duckPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(DuckFbx);
        if (duckPrefab == null)
        {
            Debug.LogError("SceneRebuild: failed to load " + DuckFbx + " as GameObject.");
            EditorApplication.Exit(1);
            return;
        }
        var duck = (GameObject)Object.Instantiate(duckPrefab);
        duck.name = "Duck";
        // Duck origin at y=0.07; lowest mesh vertex sits ~0.065 below the
        // duck origin, so the feet hover just above y=0.
        duck.transform.SetPositionAndRotation(new Vector3(0f, 0.07f, 0f), Quaternion.Euler(0f, 90f, 0f));
        SceneManager.MoveGameObjectToScene(duck, scene);

        // --- Duck material: make sure the base color texture is assigned. ---
        var baseTex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Duck/duck_basecolor.png");
        if (baseTex == null)
            Debug.LogWarning("SceneRebuild: Assets/Duck/duck_basecolor.png not found.");
        foreach (var smr in duck.GetComponentsInChildren<SkinnedMeshRenderer>(true))
        {
            var mat = smr.sharedMaterial;
            Debug.Log("SceneRebuild: SkinnedMeshRenderer on '" + smr.gameObject.name +
                      "' material='" + (mat != null ? mat.name : "null") +
                      "' texture=" + (mat != null && mat.mainTexture != null ? mat.mainTexture.name : "null"));
            if (mat != null && mat.mainTexture == null && baseTex != null)
            {
                var fixedMat = new Material(Shader.Find("Standard"));
                fixedMat.name = mat.name + "_Textured";
                fixedMat.mainTexture = baseTex;
                smr.sharedMaterial = fixedMat;
                Debug.Log("SceneRebuild: assigned duck_basecolor.png to '" + fixedMat.name + "'.");
            }
        }

        // --- Walk animation: the real take inside the FBX. Unity's importer also
        // generates a '__preview__*' clip for the model preview window; never
        // attach that one, it may not contain the real curves. ---
        var clips = AssetDatabase.LoadAllAssetsAtPath(DuckFbx).OfType<AnimationClip>().ToList();
        var clip = clips.FirstOrDefault(c => !c.name.StartsWith("__preview"))
                   ?? clips.FirstOrDefault();
        var anim = duck.AddComponent<Animation>();
        if (clip != null)
        {
            clip.legacy = true;
            anim.AddClip(clip, clip.name);
            anim.clip = clip;
            anim.playAutomatically = true;
            anim.wrapMode = WrapMode.Loop;
            Debug.Log("SceneRebuild: walk clip '" + clip.name + "' attached.");
        }
        else
        {
            Debug.LogError("SceneRebuild: no AnimationClip subasset found in " + DuckFbx);
        }

        var walker = duck.AddComponent<DuckWalker>();
        walker.speed = 1.2f;
        walker.minX = -5f;
        walker.maxX = 5f;
        duck.AddComponent<Credits>();
        duck.AddComponent<TouchControls>();

        // --- No ground plane (removed in v1.6.0): the cloud background fills
        // the entire screen, so the duck walks against pure sky. ---

        // --- Background: Tyler's cloud photo fills the entire screen (v1.6.0:
        // the gray ground plane is gone, so the sky plane is enlarged to
        // cover the whole camera view). Tyler's verified recipe: plane
        // rotated 90 about X, new material with the texture. Unlit/Texture
        // so the photo renders full-bright like a skybox -- a lit Standard
        // material goes black here because the scene's directional light
        // shines from behind the plane.
        // V is flipped so the image isn't upside down after the X rotation. ---
        var bgTex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Duck/cloud_bg.jpg");
        if (bgTex != null)
        {
            var bg = GameObject.CreatePrimitive(PrimitiveType.Plane);
            bg.name = "Background";
            Object.DestroyImmediate(bg.GetComponent<MeshCollider>());
            var bgMat = new Material(Shader.Find("Unlit/Texture"));
            bgMat.name = "CloudBackground";
            bgMat.mainTexture = bgTex;
            bgMat.mainTextureScale = new Vector2(1f, -1f);
            bgMat.mainTextureOffset = new Vector2(0f, 1f);
            bg.GetComponent<MeshRenderer>().sharedMaterial = bgMat;
            bg.transform.SetPositionAndRotation(
                new Vector3(0f, 2f, -12f), Quaternion.Euler(90f, 0f, 0f));
            // Plane is 10x10 in local XZ; after the X rotation local Z maps
            // to world Y, so scale Z for height. 60x40 comfortably covers the
            // full camera frustum at this distance (FOV 40, plane ~15 units
            // out needs ~+/-13 wide, ~+/-6 tall).
            bg.transform.localScale = new Vector3(6f, 1f, 4f);
            SceneManager.MoveGameObjectToScene(bg, scene);
            Debug.Log("SceneRebuild: cloud photo background (plane) attached.");
        }
        else
        {
            Debug.LogWarning("SceneRebuild: Assets/Duck/cloud_bg.jpg not found; no photo background.");
        }

        // --- Camera: guaranteed to face the duck via LookAt. ---
        var camGo = new GameObject("Main Camera");
        camGo.tag = "MainCamera";
        var camera = camGo.AddComponent<Camera>();
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.55f, 0.78f, 0.95f);
        camera.fieldOfView = 40f;
        camera.nearClipPlane = 0.1f;
        camera.farClipPlane = 100f;
        camGo.transform.position = new Vector3(0f, 1.15f, 3f);
        camGo.transform.LookAt(new Vector3(0f, 0.3f, 0f));
        SceneManager.MoveGameObjectToScene(camGo, scene);
        Debug.Log("SceneRebuild: camera forward = " + camGo.transform.forward);

        // --- Directional light (same orientation as the previous scene). ---
        var lightGo = new GameObject("Directional Light");
        var light = lightGo.AddComponent<Light>();
        light.type = LightType.Directional;
        lightGo.transform.position = new Vector3(0f, 3f, 0f);
        lightGo.transform.rotation = new Quaternion(0.523711f, 0.254884f, -0.167831f, 0.795357f);
        SceneManager.MoveGameObjectToScene(lightGo, scene);

        LogSceneContents();

        EditorSceneManager.SaveScene(scene, ScenePath);
        AssetDatabase.SaveAssets();
        Debug.Log("SceneRebuild: scene rebuilt and saved to " + ScenePath);
    }

    // Dumps every camera and renderer in the built scene so the build log
    // shows exactly what will render on the phone.
    private static void LogSceneContents()
    {
        Debug.Log("SceneRebuild: === scene contents ===");
        foreach (var cam in Object.FindObjectsOfType<Camera>())
        {
            Debug.Log("SceneRebuild: CAMERA '" + cam.name +
                      "' pos=" + cam.transform.position +
                      " fwd=" + cam.transform.forward +
                      " clearFlags=" + cam.clearFlags +
                      " bg=" + cam.backgroundColor +
                      " depth=" + cam.depth +
                      " enabled=" + cam.enabled +
                      " cullingMask=" + cam.cullingMask);
        }
        foreach (var r in Object.FindObjectsOfType<Renderer>())
        {
            var mat = r.sharedMaterial;
            Debug.Log("SceneRebuild: RENDERER '" + r.gameObject.name +
                      "' (" + r.GetType().Name + ")" +
                      " mat=" + (mat != null ? "'" + mat.name + "'" : "null") +
                      " shader=" + (mat != null && mat.shader != null ? "'" + mat.shader.name + "'" : "null") +
                      " tex=" + (mat != null && mat.mainTexture != null ? "'" + mat.mainTexture.name + "'" : "null") +
                      " boundsCenter=" + r.bounds.center +
                      " boundsSize=" + r.bounds.size);
        }
    }

    private static void LogImportedSubassets(string assetPath)
    {
        var assets = AssetDatabase.LoadAllAssetsAtPath(assetPath);
        Debug.Log("SceneRebuild: " + assetPath + " -> " + assets.Length + " subasset(s).");
        foreach (var a in assets)
        {
            if (a == null) continue;
            AssetDatabase.TryGetGUIDAndLocalFileIdentifier(a, out var guid, out long localId);
            Debug.Log("SceneRebuild:   [" + a.GetType().Name + "] '" + a.name + "' localId=" + localId);
        }
    }
}
