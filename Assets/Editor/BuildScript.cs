using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Command-line build entry point for CI.
/// Invoked from GitHub Actions via:
///   -executeMethod BuildScript.BuildAndroid
/// Builds every enabled scene in the Build Settings into Builds/Android/DuckWalk.apk.
/// All Android player settings (package id, ARM64, API levels, IL2CPP, landscape)
/// come from ProjectSettings/ProjectSettings.asset.
/// </summary>
public static class BuildScript
{
    public static void BuildAndroid()
    {
        var scenes = EditorBuildSettings.scenes
            .Where(s => s.enabled)
            .Select(s => s.path)
            .ToArray();

        if (scenes.Length == 0)
        {
            Debug.LogError("BuildScript: no enabled scenes in Build Settings.");
            EditorApplication.Exit(1);
            return;
        }

        // Stamp the version code from the CI run number when available.
        var runNumber = System.Environment.GetEnvironmentVariable("GITHUB_RUN_NUMBER");
        if (int.TryParse(runNumber, out var versionCode) && versionCode > 0)
        {
            PlayerSettings.Android.bundleVersionCode = versionCode;
            Debug.Log($"BuildScript: bundleVersionCode set to {versionCode}");
        }

        var outputDir = Path.Combine(Directory.GetCurrentDirectory(), "Builds", "Android");
        Directory.CreateDirectory(outputDir);
        var outputPath = Path.Combine(outputDir, "DuckWalk.apk");

        var options = new BuildPlayerOptions
        {
            scenes = scenes,
            locationPathName = outputPath,
            target = BuildTarget.Android,
            options = BuildOptions.None,
        };

        Debug.Log($"BuildScript: building {scenes.Length} scene(s) to {outputPath}");
        var report = BuildPipeline.BuildPlayer(options);
        var result = report.summary.result;
        Debug.Log($"BuildScript: build finished with result {result}");

        if (result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
        {
            EditorApplication.Exit(1);
        }
    }
}
