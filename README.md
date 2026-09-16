# Duck Walk

A tiny Android game: an animated duck walks across the screen and wraps around.
Built with Unity 2022.3.76f1, built in CI with [game-ci](https://game.ci).

This work is based on “Duck_Walk (Free)” by Nyilonelycompany, licensed under CC-BY-4.0.

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

- Build config: Unity 2022.3.76f1, IL2CPP, ARM64 only, min API 24,
  target API 34, `androidVersionCode` = the GitHub run number, APK output.
- The duck model source (`duck_walk_free.zip`) is not in this repo; the
  conversion script `Tools/convert_duck.py` documents the full glTF → FBX
  pipeline for reproducibility.
