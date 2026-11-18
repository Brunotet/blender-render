# blender-render

Headless Blender (`bpy` Python module, Cycles CPU) rendered in parallel on GitHub Actions, stitched with ffmpeg.

## How it works
1. `plan` job splits `total_frames` into up to 20 chunks (aligned to `step`).
2. `render` matrix: each job runs `render.py` on its frame range, then encodes its PNGs into `seg_XXXX.mp4`.
3. `stitch` job verifies the segment count (hard-fails if any is missing), joins them into `final.mp4`.

## Run
Actions tab -> `render` -> Run workflow (or `gh workflow run render.yml -f total_frames=7200 -f step=2`).
Download `final-video` from the run's artifacts.

## Notes
- Repo must be public for unlimited free minutes (private = 2,000 min/month).
- `step=2` renders every 2nd frame and holds it (animation on twos), halving render time.
- Scenes live in `scenes/*.py` and expose `build(bpy, fps)`. Pass with `-f scene=scenes/yours.py`.
- Local test: `pip install bpy==5.3.0 && python render.py --start 1 --end 3 --out frames --samples 16`
- Measured here on 2 CPU cores, demo scene: ~25 s/frame at 1280x720, 24 samples; ~13 s at 960x540.
