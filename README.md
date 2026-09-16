# Duck Walk

A tiny Android game: an animated duck walks across the screen and wraps around.
Built with Unity 2022.3.62f1, built in CI with
[Buildalon](https://www.buildalon.com) GitHub Actions.

This work is based on “Duck_Walk (Free)” by Nyilonelycompany, licensed under CC-BY-4.0.

## Project layout

- `Assets/Duck/duck.fbx` — duck mesh + 45-bone rig + baked 20-frame walk cycle
  (converted from the glTF source with `Tools/convert_duck.py`)
- `Assets/Duck/ground.fbx` — ground slab
- `Assets/Scenes/Main.unity` — duck (legacy `Animation` component, walk on loop),
  ground, directional light, camera, `DuckWalker` + `Credits` scripts
- `Assets/Editor/BuildScript.cs` — command-line entry point that builds the APK
- `.github/workflows/build.yml` — CI pipeline: install Unity, activate a
  Personal license, build, upload the APK

## Build the APK (GitHub Actions)

The project builds itself in the cloud — no local Unity install needed.

1. Push this project to the `main` branch of your repo.
2. One-time setup — save your Unity ID as repository secrets
   (repo → Settings → Secrets and variables → Actions → New repository secret):
   - `UNITY_USERNAME` — the email address of your Unity ID
   - `UNITY_PASSWORD` — your Unity ID password
   (These activate a free Personal license on the CI runner at build time.
   Remove them when you're done shipping builds.)
3. Run the **Build Android APK** workflow (Actions tab → Run workflow),
   or just push to `main`.
4. Download the `duckwalk-apk` artifact — inside is `DuckWalk.apk`, ready to
   install on an ARM64 Android device (Android 7.0+, API 24+).

## Notes

- Build config: Unity 2022.3.62f1, IL2CPP, ARM64 only, min API 24,
  target API 34, `androidVersionCode` = the GitHub run number, APK output.
- The duck model source (`duck_walk_free.zip`) is not in this repo; the
  conversion script `Tools/convert_duck.py` documents the full glTF → FBX
  pipeline for reproducibility.
