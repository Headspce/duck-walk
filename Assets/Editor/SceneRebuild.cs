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
    private const string GroundFbx = "Assets/Duck/ground.fbx";
    private const string ScenePath = "Assets/Scenes/Main.unity";

    public static void Rebuild()
    {
        LogImportedSubassets(DuckFbx);
        LogImportedSubassets(GroundFbx);

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
        duck.transform.SetPositionAndRotation(Vector3.zero, Quaternion.Euler(0f, 90f, 0f));
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

        // --- Ground: instantiate the imported ground, or a plane fallback. ---
        GameObject ground;
        var groundPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(GroundFbx);
        if (groundPrefab != null)
        {
            ground = (GameObject)Object.Instantiate(groundPrefab);
            Debug.Log("SceneRebuild: ground instantiated from " + GroundFbx);
        }
        else
        {
            Debug.LogWarning("SceneRebuild: " + GroundFbx + " did not load; using a procedural plane.");
            ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.transform.localScale = new Vector3(2f, 1f, 2f);
        }
        ground.name = "Ground";
        ground.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
        SceneManager.MoveGameObjectToScene(ground, scene);
        foreach (var mr in ground.GetComponentsInChildren<MeshRenderer>(true))
        {
            var mf = mr.GetComponent<MeshFilter>();
            Debug.Log("SceneRebuild: ground renderer mesh=" +
                      (mf != null && mf.sharedMesh != null ? "'" + mf.sharedMesh.name + "'" : "null") +
                      " material=" + (mr.sharedMaterial != null ? "'" + mr.sharedMaterial.name + "'" : "null"));
        }

        // --- Background: Tyler's cloud photo on a big unlit quad far behind
        // the scene, sized generously so it fills the view on any phone
        // aspect ratio. Unlit so scene lighting doesn't dim it. ---
        var bgTex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Duck/cloud_bg.jpg");
        if (bgTex != null)
        {
            var bg = GameObject.CreatePrimitive(PrimitiveType.Quad);
            bg.name = "Background";
            Object.DestroyImmediate(bg.GetComponent<MeshCollider>());
            var bgMat = new Material(Shader.Find("Unlit/Texture"));
            bgMat.name = "CloudBackground";
            bgMat.mainTexture = bgTex;
            bg.GetComponent<MeshRenderer>().sharedMaterial = bgMat;
            bg.transform.SetPositionAndRotation(new Vector3(0f, -1f, -18f), Quaternion.identity);
            bg.transform.localScale = new Vector3(44f, 24f, 1f);
            SceneManager.MoveGameObjectToScene(bg, scene);
            Debug.Log("SceneRebuild: cloud photo background attached.");
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

        EditorSceneManager.SaveScene(scene, ScenePath);
        AssetDatabase.SaveAssets();
        Debug.Log("SceneRebuild: scene rebuilt and saved to " + ScenePath);
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
