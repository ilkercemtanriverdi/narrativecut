# FluxEngine Video Studio

Local-first, deterministic documentary video compilation core.

The v0.1 core accepts a JSON brief, script, and local assets with sidecar
rights metadata. It produces a timeline, subtitles, asset/license report,
revision manifest, and—when FFmpeg and narration are available—a 16:9 MP4.

```sh
python -m fluxengine_video_studio --brief examples/minimal/brief.json \
  --script examples/minimal/script.txt \
  --assets examples/minimal/assets \
  --output outputs/example
```

This repository intentionally excludes provider credentials, publishing,
commercial channel strategy, user data, model weights, and supplied media.
Rights metadata is an input contract, not a legal warranty.

## Status

v0.1.0 is a small OSS core extracted from the larger private FluxEngine Video
Studio workspace. Rendering is local and optional; no network provider is
required for planning or validation.

