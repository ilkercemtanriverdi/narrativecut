# NarrativeCut

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

The command writes `timeline.json`, `subtitles.srt`, and `asset-license-report.json`. Assets are discovered only when accompanied by a sidecar file such as `clip.png.json` containing `source`, `rights`, and `subject`.

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

This repository intentionally excludes provider credentials, publishing,
commercial channel strategy, user data, model weights, and supplied media.
Rights metadata is an input contract, not a legal warranty.

## Status

v0.1.0 is a small OSS core extracted from a larger private workspace. Rendering is local and optional; no network provider is required for planning or validation.

## Limitations and roadmap

- Rights metadata is an input contract, not a legal warranty.
- Rendering requires local FFmpeg, narration, and decodable media.
- The planner does not download media or call model/provider APIs.
- Future work may add more media validators and platform-neutral render adapters.
