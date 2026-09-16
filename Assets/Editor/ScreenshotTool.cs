using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// CI visual verification: renders the rebuilt Main scene from the Main
/// Camera to Screenshots/scene.png, so a human can confirm the scene looks
/// right without installing the APK on a phone.
/// Invoked from GitHub Actions via:
///   -executeMethod ScreenshotTool.Capture
/// Must run WITHOUT -nographics (needs a GL context; the workflow wraps it
/// in xvfb-run with Mesa software rendering).
/// </summary>
public static class ScreenshotTool
{
    public static void Capture()
    {
        // Rebuild exactly as the build does, so the screenshot matches the APK.
        SceneRebuild.Rebuild();

        var scene = SceneManager.GetActiveScene();
        Debug.Log("ScreenshotTool: active scene = " + scene.path);

        var camGo = GameObject.Find("Main Camera");
        if (camGo == null)
        {
            Debug.LogError("ScreenshotTool: Main Camera not found.");
            EditorApplication.Exit(1);
            return;
        }
        var cam = camGo.GetComponent<Camera>();
        if (cam == null)
        {
            Debug.LogError("ScreenshotTool: Main Camera has no Camera component.");
            EditorApplication.Exit(1);
            return;
        }

        // ~2.22:1, close to Tyler's phone screenshot aspect.
        const int w = 1280;
        const int h = 576;
        var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32);
        cam.targetTexture = rt;
        cam.Render();
        RenderTexture.active = rt;
        var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        tex.Apply();
        cam.targetTexture = null;
        RenderTexture.active = null;
        Object.DestroyImmediate(rt);

        Directory.CreateDirectory("Screenshots");
        var path = Path.Combine("Screenshots", "scene.png");
        File.WriteAllBytes(path, tex.EncodeToPNG());
        Object.DestroyImmediate(tex);
        Debug.Log("ScreenshotTool: saved " + path);
    }
}
