# NarrativeCut

[![CI](https://github.com/ilkercemtanriverdi/narrativecut/actions/workflows/ci.yml/badge.svg)](https://github.com/ilkercemtanriverdi/narrativecut/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Latest release](https://img.shields.io/github/v/release/ilkercemtanriverdi/narrativecut)](https://github.com/ilkercemtanriverdi/narrativecut/releases/latest)

Turn a script, a JSON brief, and rights-described local assets into a deterministic documentary plan: timeline, subtitles, asset-license report, and optional 16:9 MP4 rendering.

## Quickstart

Requires Python 3.11+. The planning core has no runtime dependency outside the standard library.

```sh
python -m venv .venv && . .venv/bin/activate
python -m pip install -e . pytest
python -m narrativecut \
  --brief examples/minimal/brief.json \
  --script examples/minimal/script.txt \
  --assets examples/minimal/assets \
  --output outputs/example
python -m pytest
```

### Versioned project files

Legacy `--brief` JSON remains supported (with optional `title`). For explicit schema validation, use `--project` with a JSON file containing `schema_version: "1.0"`, a `brief` object, non-empty `script`, and an `assets` directory path. YAML uses the same contract and is optional because Python's standard library has no YAML parser:

```sh
python -m pip install 'narrativecut[yaml]'
python -m narrativecut --project examples/project.yaml --output outputs/example
```

The JSON path has no runtime dependencies. Unsupported schema versions and invalid fields produce field-specific CLI errors. Version 1.0 accepts the existing brief shape and does not change generated timeline output.

The command writes `timeline.json`, `subtitles.srt`, and `asset-license-report.json`. Assets are discovered only when accompanied by a sidecar file such as `clip.png.json` containing `source`, `rights`, and `subject`.

### Local rendering and QC

Rendering requires both `ffmpeg` and `ffprobe` on `PATH`, plus decodable local visual assets and narration audio. `python -m narrativecut --assemble` returns a non-zero exit code and a clear error when tools, media, or narration are missing or cannot be decoded. QC checks the video and audio streams, full-decode success, 1920×1080 resolution, the timeline FPS, decoded frame count, audio sample rate/channels and measured loudness. The video, audio and container durations must each be within **0.1 seconds** of the planned duration in either direction; decoded frames may differ from the planned count by at most two frames or 10% of the FPS, whichever is greater. Silent or undecodable audio fails QC. QC failures are written to `qc-report.json` and return a non-zero exit code.

The renderer accepts video and raster-image assets when the installed FFmpeg can decode them. SVG input currently requires rasterization before rendering.

Run the synthetic FFmpeg render and QC integration test with `python -m pytest tests/test_render.py`. It creates its own media fixtures and needs no credentials or supplied media.

Validate an asset directory before planning with `python -m narrativecut --validate-assets --assets path/to/assets`. Each asset needs an adjacent `<filename>.<extension>.json` sidecar with non-empty string values for `source`, `rights`, and `subject`. Optional `id` values must be unique; an optional `path` must resolve to that asset. The validator reports missing files, malformed metadata, invalid references, and duplicate or conflicting IDs. It validates supplied metadata and paths; it does not determine whether a rights claim is legally accurate or inspect media contents.

## Architecture

`parse_script` creates timed beats; `catalog_assets` reads local asset metadata; `select` ranks deterministic matches; `build` writes planning outputs; `assemble` and `qc` are optional FFmpeg-backed render and validation steps.

```text
brief + script + local assets
              ↓
       deterministic planner
              ↓
 timeline + SRT + rights report
              ↓
       optional render + QC
```

## Sample output

```text
outputs/example/
├── asset-license-report.json
├── subtitles.srt
└── timeline.json
```

The checked-in minimal example is safe to run without media or credentials:

```sh
python -m narrativecut \
  --brief examples/minimal/brief.json \
  --script examples/minimal/script.txt \
  --assets examples/minimal/assets \
  --output outputs/example
```

It produces a deterministic planning bundle:

```text
timeline.json              # timed scenes and editorial gate
subtitles.srt              # scene-aligned subtitles
asset-license-report.json  # admitted assets and rights basis
```

With the sample asset directory intentionally empty, the report records unmatched scenes instead of inventing media. Add local assets only with the required rights sidecars before rendering.

This repository intentionally excludes provider credentials, publishing,
commercial channel strategy, user data, model weights, and supplied media.
Rights metadata is an input contract, not a legal warranty.

## Status

v0.2.0 is a small OSS core extracted from a larger private workspace. Rendering is local and optional; no network provider is required for planning or validation.

## Limitations and roadmap

- Rights metadata is an input contract, not a legal warranty.
- Rendering requires local FFmpeg, narration, and decodable media.
- The planner does not download media or call model/provider APIs.
- Future work may add more media validators and platform-neutral render adapters.

Roadmap discussions live in [GitHub Issues](https://github.com/ilkercemtanriverdi/narrativecut/issues).
